"""Static connectivity without hidden preprocessing or cohort fitting.

Rows are time points and columns are ROIs. Pearson and Spearman are ordinary
sample correlations. Partial correlation uses a Ledoit-Wolf shrinkage estimate
on standardized channels, via Nilearn; it is not an unregularized inverse.
"""
from __future__ import annotations

import warnings

import numpy as np
from scipy.stats import rankdata

from .types import ValidationError


def _timeseries(value) -> np.ndarray:
    if np.iscomplexobj(value):
        raise ValidationError("Time series must be real-valued.")
    try:
        data = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Time series must contain numeric values.") from exc
    if data.ndim != 2 or data.shape[0] < 3 or not 1 <= data.shape[1] <= 1000:
        raise ValidationError("Time series require at least 3 rows and 1 to 1000 ROI columns.")
    if data.shape[0] > 100000 or data.size > 5000000:
        raise ValidationError("Time series exceed 100000 frames or 5000000 cells; select fewer ROIs/frames.")
    if not np.isfinite(data).all():
        raise ValidationError("Time series contain NaN or infinite values; correct them before analysis.")
    if np.any(np.max(data, axis=0) == np.min(data, axis=0)):
        raise ValidationError("Time series contain a constant ROI channel.")
    return data


def _standardized(data: np.ndarray) -> np.ndarray:
    # Scaling first avoids overflow for valid, unusually large numeric inputs.
    scaled = data / np.max(np.abs(data), axis=0)
    centered = scaled - scaled.mean(axis=0)
    deviations = np.sqrt(np.sum(centered * centered, axis=0) / (len(data) - 1))
    if np.any(deviations == 0):
        raise ValidationError("A time-series channel has insufficient numerical variation.")
    return centered / deviations


def compute_connectivity(timeseries, method: str = "pearson") -> np.ndarray:
    """Return an ROI by ROI correlation matrix with a unit diagonal.

    No filtering, motion regression, detrending, or temporal imputation occurs.
    ``partial`` estimates shrinkage covariance independently for this input.
    """
    data = _timeseries(timeseries)
    if method not in {"pearson", "spearman", "partial"}:
        raise ValidationError("method must be pearson, spearman, or partial.")
    if method == "spearman":
        data = rankdata(data, axis=0, method="average")
    standardized = _standardized(data)
    if method == "partial":
        from nilearn.connectome import ConnectivityMeasure
        from sklearn.covariance import LedoitWolf

        estimator = ConnectivityMeasure(
            kind="partial correlation",
            cov_estimator=LedoitWolf(store_precision=False),
            standardize="zscore_sample",
        )
        result = estimator.fit_transform([standardized])[0]
    else:
        result = standardized.T @ standardized / (len(data) - 1)
    result = np.clip((result + result.T) / 2, -1.0, 1.0)
    np.fill_diagonal(result, 1.0)
    if not np.isfinite(result).all():
        raise ValidationError("Connectivity could not be estimated as finite numbers.")
    return result


def _transform_input(matrix) -> tuple[np.ndarray, np.ndarray]:
    if np.iscomplexobj(matrix):
        raise ValidationError("Connectivity must be real-valued.")
    try:
        value = np.asarray(matrix, dtype=float).copy()
    except (TypeError, ValueError) as exc:
        raise ValidationError("Connectivity must be a numeric matrix.") from exc
    if value.ndim != 2 or value.shape[0] != value.shape[1] or not 1 <= len(value) <= 1000:
        raise ValidationError("Connectivity must be square with 1 to 1000 ROIs.")
    mask = ~np.eye(len(value), dtype=bool)
    if not np.isfinite(value[mask]).all():
        raise ValidationError("Off-diagonal connectivity contains NaN or infinity.")
    np.fill_diagonal(value, 0.0)
    if not np.allclose(value, value.T, rtol=1e-7, atol=1e-8):
        raise ValidationError("Connectivity must be symmetric.")
    return value / 2 + value.T / 2, mask


def fisher_z(matrix) -> np.ndarray:
    """Apply arctanh off-diagonal and set the unused diagonal to zero.

    Exact +/-1 coefficients are clipped to +/- (1 - machine epsilon), with a
    warning, so serialization remains finite. Diagonal values are ignored.
    """
    value, mask = _transform_input(matrix)
    if np.any(np.abs(value[mask]) > 1 + 1e-8):
        raise ValidationError("Fisher-z requires correlation coefficients between -1 and 1.")
    limit = 1.0 - np.finfo(float).eps
    if np.any(np.abs(value[mask]) > limit):
        warnings.warn("Perfect off-diagonal correlations were clipped before Fisher-z.", RuntimeWarning, stacklevel=2)
    result = np.arctanh(np.clip(value, -limit, limit))
    np.fill_diagonal(result, 0.0)
    return result


def inverse_fisher_z(matrix) -> np.ndarray:
    """Convert a Fisher-z matrix to correlations; restore a unit diagonal.

    Infinite or missing diagonal values are permitted because self-connections
    are excluded from analysis. Off-diagonal values must be finite.
    """
    value, _ = _transform_input(matrix)
    result = np.tanh(value)
    np.fill_diagonal(result, 1.0)
    return result
