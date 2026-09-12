"""Participant-level descriptive and two-group statistics with auditable exclusions."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from .types import ValidationError


def _clean(value):
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_clean(item) for item in value]
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _numbers(values, name: str) -> pd.Series:
    try:
        original = pd.Series(values, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name} must be a one-dimensional numeric sequence.") from exc
    try:
        converted = pd.to_numeric(original, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name} contains nonnumeric values; correct or explicitly encode them.") from exc
    if np.isinf(converted.to_numpy(dtype=float)).any():
        raise ValidationError(f"{name} contains infinite values.")
    return converted.astype(float)


def describe(values) -> dict:
    """Describe finite observations; missing values are counted, never imputed."""
    numeric = _numbers(values, "values")
    selected = numeric.dropna().to_numpy()
    if not len(selected):
        raise ValidationError("No finite observations are available.")
    return _clean({
        "n": len(selected), "missing": int(numeric.isna().sum()),
        "mean": float(np.mean(selected)), "std": float(np.std(selected, ddof=1)) if len(selected) > 1 else None,
        "median": float(np.median(selected)), "min": float(np.min(selected)), "max": float(np.max(selected)),
        "q25": float(np.quantile(selected, .25)), "q75": float(np.quantile(selected, .75)),
    })


def _bh(pvalues: list[float]) -> list[float]:
    values = np.asarray(pvalues, dtype=float)
    order = np.argsort(values, kind="stable")
    ranked = values[order] * len(values) / np.arange(1, len(values) + 1)
    result = np.empty(len(values))
    result[order] = np.minimum(1, np.minimum.accumulate(ranked[::-1])[::-1])
    return result.tolist()


def compare_groups(data, group_column, subject_column, feature_columns, covariates=None) -> dict:
    """Compare exactly two groups, using group 2 minus group 1 as the effect.

    Group order is lexical by its string label and is returned explicitly.
    Missing feature/covariate values use complete cases separately per feature;
    exclusions are recorded. Group and participant IDs cannot be missing. IDs
    must be globally unique, including observations excluded for missing values.
    Numeric covariates use OLS with HC3 covariance and t inference; no covariates
    uses Welch's unequal-variance t test. Features form one BH-FDR family.
    """
    frame = pd.DataFrame(data).copy()
    if isinstance(covariates, str):
        raise ValidationError("covariates must be a list of column names, not a string.")
    covariates = list(covariates or [])
    features = list(feature_columns) if not isinstance(feature_columns, str) else []
    if frame.empty or not features:
        raise ValidationError("Provide participant rows and at least one feature column.")
    if not frame.columns.is_unique:
        raise ValidationError("Participant table column names must be unique.")
    if group_column == subject_column or len(set(features)) != len(features) or len(set(covariates)) != len(covariates):
        raise ValidationError("Group/subject columns must differ and feature/covariate lists must be unique.")
    if set(features) & set(covariates) or {group_column, subject_column} & set(features + covariates):
        raise ValidationError("Group, subject, feature and covariate columns must have distinct roles.")
    required = [subject_column, group_column, *features, *covariates]
    missing_columns = [column for column in required if column not in frame.columns]
    if missing_columns:
        raise ValidationError("Missing table columns: " + ", ".join(map(str, missing_columns)))
    for column in (subject_column, group_column):
        if frame[column].isna().any() or frame[column].map(lambda value: not str(value).strip()).any():
            raise ValidationError(f"{column} must not contain missing or blank values.")
        frame[column] = frame[column].astype(str).str.strip()
    if frame[subject_column].duplicated().any():
        raise ValidationError("Repeated subject IDs detected; select one observation per participant before comparison.")
    groups = sorted(frame[group_column].unique().tolist())
    if len(groups) != 2:
        raise ValidationError("Exactly two nonempty groups are required.")
    for column in features + covariates:
        frame[column] = _numbers(frame[column], str(column))
    rows = []
    for feature in features:
        valid = frame[[feature, *covariates]].notna().all(axis=1)
        selected = frame.loc[valid]
        group1 = selected.loc[selected[group_column] == groups[0], feature].to_numpy()
        group2 = selected.loc[selected[group_column] == groups[1], feature].to_numpy()
        n1, n2 = len(group1), len(group2)
        if min(n1, n2) < 2:
            raise ValidationError(f"{feature}: at least two complete participants per group are required.")
        effect = float(np.mean(group2) - np.mean(group1))
        pooled = math.sqrt(((n1 - 1) * np.var(group1, ddof=1) + (n2 - 1) * np.var(group2, ddof=1)) / (n1 + n2 - 2))
        d = effect / pooled if pooled > 0 else None
        hedges_g = d * (1 - 3 / (4 * (n1 + n2) - 9)) if d is not None else None
        if covariates:
            import statsmodels.api as sm
            encoded_group = (selected[group_column] == groups[1]).astype(float).to_numpy()
            cov = selected[covariates].to_numpy(dtype=float)
            design = np.column_stack([np.ones(len(selected)), encoded_group, cov])
            if len(selected) <= design.shape[1] or np.linalg.matrix_rank(design) < design.shape[1]:
                raise ValidationError(f"{feature}: covariate design is singular or lacks residual degrees of freedom.")
            leverage = np.einsum("ij,ji->i", design, np.linalg.pinv(design))
            if np.any(leverage >= 1 - 1e-10):
                raise ValidationError(f"{feature}: a participant has unit leverage; HC3 cannot be estimated.")
            fitted = sm.OLS(selected[feature].to_numpy(), design).fit(cov_type="HC3", use_t=True)
            effect = float(fitted.params[1])
            statistic = float(fitted.tvalues[1])
            p = float(fitted.pvalues[1])
            low, high = fitted.conf_int(alpha=.05)[1]
            degrees_freedom = float(fitted.df_resid)
        else:
            a, b = np.var(group1, ddof=1) / n1, np.var(group2, ddof=1) / n2
            standard_error = math.sqrt(a + b)
            if standard_error <= 0:
                raise ValidationError(f"{feature}: both groups have zero variance; a t test is undefined.")
            degrees_freedom = (a + b) ** 2 / (a * a / (n1 - 1) + b * b / (n2 - 1))
            statistic = effect / standard_error
            p = float(2 * stats.t.sf(abs(statistic), degrees_freedom))
            radius = float(stats.t.ppf(.975, degrees_freedom) * standard_error)
            low, high = effect - radius, effect + radius
        if not all(np.isfinite(value) for value in [effect, statistic, p, low, high]):
            raise ValidationError(f"{feature}: inferential statistics could not be estimated for this design.")
        rows.append({
            "feature": feature, "n": len(selected), "n_group1": n1, "n_group2": n2,
            "mean_group1": float(np.mean(group1)), "mean_group2": float(np.mean(group2)),
            "effect": effect, "effect_definition": "adjusted group2 minus group1" if covariates else "group2 minus group1",
            "ci_low": float(low), "ci_high": float(high), "confidence_level": .95,
            "statistic": statistic, "t_value": statistic, "df": degrees_freedom, "p": p,
            "cohens_d_unadjusted": d, "hedges_g_unadjusted": hedges_g,
            "excluded_missing": int((~valid).sum()),
            "excluded_subject_ids": frame.loc[~valid, subject_column].tolist(),
        })
    for row, q in zip(rows, _bh([row["p"] for row in rows])):
        row["q"] = q
    return _clean({
        "method": "OLS HC3 (t inference)" if covariates else "Welch t test",
        "group_column": group_column, "subject_column": subject_column, "group_order": groups,
        "group_counts": {group: int((frame[group_column] == group).sum()) for group in groups},
        "covariates": covariates, "n_input": len(frame),
        "missing_policy": "per-feature complete cases, without imputation",
        "multiple_comparison": "Benjamini-Hochberg across all requested features",
        "excluded_missing": {row["feature"]: row["excluded_missing"] for row in rows}, "results": rows,
    })
