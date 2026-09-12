import json

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from brainfc.network.statistics import compare_groups, describe
from brainfc.network.types import ValidationError


@pytest.fixture
def cohort():
    return pd.DataFrame({
        "subject": [f"p{i}" for i in range(12)],
        "group": ["A"] * 6 + ["B"] * 6,
        "x": [1, 2, 4, 3, 5, 7, 5, 6, 8, 7, 9, 11],
        "y": [3, 2, 4, 1, 5, 7, 3, 6, 2, 5, 9, 1],
        "age": [21, 23, 22, 32, 31, 26, 20, 24, 27, 29, 33, 28],
    })


def test_describe_counts_missing():
    result = describe([1, 2, None, 3])
    assert result["n"] == 3
    assert result["missing"] == 1
    assert result["mean"] == 2
    assert result["std"] == 1
    assert describe([4])["std"] is None
    with pytest.raises(ValidationError, match="nonnumeric"):
        describe([1, "unexpected"])
    with pytest.raises(ValidationError, match="infinite"):
        describe([1, np.inf])


def test_welch_matches_scipy_and_fdr(cohort):
    result = compare_groups(cohort, "group", "subject", ["x", "y"])
    x = result["results"][0]
    a, b = cohort.iloc[:6].x, cohort.iloc[6:].x
    expected = stats.ttest_ind(b, a, equal_var=False)
    assert x["effect"] == pytest.approx(b.mean() - a.mean())
    assert x["p"] == pytest.approx(expected.pvalue)
    assert x["statistic"] == pytest.approx(expected.statistic)
    assert x["ci_low"] < x["effect"] < x["ci_high"]
    assert x["q"] >= x["p"]
    expected_q = stats.false_discovery_control([row["p"] for row in result["results"]], method="bh")
    assert [row["q"] for row in result["results"]] == pytest.approx(expected_q)
    assert result["group_order"] == ["A", "B"]
    json.dumps(result, allow_nan=False)


def test_covariate_hc3_matches_reference(cohort):
    import statsmodels.api as sm
    result = compare_groups(cohort, "group", "subject", ["x"], covariates=["age"])
    design = np.column_stack([np.ones(len(cohort)), (cohort.group == "B").astype(float), cohort.age])
    fit = sm.OLS(cohort.x.to_numpy(), design).fit(cov_type="HC3", use_t=True)
    row = result["results"][0]
    assert row["effect"] == pytest.approx(fit.params[1])
    assert row["p"] == pytest.approx(fit.pvalues[1])
    assert [row["ci_low"], row["ci_high"]] == pytest.approx(fit.conf_int()[1])
    assert row["effect_definition"].startswith("adjusted")


def test_per_feature_missing_policy_is_recorded(cohort):
    cohort.loc[0, "x"] = np.nan
    result = compare_groups(cohort, "group", "subject", ["x", "y"])
    assert result["results"][0]["n"] == 11
    assert result["results"][1]["n"] == 12
    assert result["results"][0]["excluded_subject_ids"] == ["p0"]
    assert result["excluded_missing"] == {"x": 1, "y": 0}


def test_duplicates_rejected_before_missing_filter(cohort):
    cohort.loc[0, "x"] = np.nan
    cohort.loc[1, "subject"] = "p0"
    with pytest.raises(ValidationError, match="Repeated subject"):
        compare_groups(cohort, "group", "subject", ["x"])


@pytest.mark.parametrize("column,value,match", [
    ("subject", None, "missing"), ("group", "", "blank"),
    ("x", "oops", "nonnumeric"), ("x", np.inf, "infinite"),
])
def test_invalid_table_values(cohort, column, value, match):
    cohort[column] = cohort[column].astype(object)
    cohort.loc[0, column] = value
    with pytest.raises(ValidationError, match=match):
        compare_groups(cohort, "group", "subject", ["x"])


def test_three_groups_and_singular_covariates(cohort):
    bad_groups = cohort.copy()
    bad_groups.loc[0, "group"] = "C"
    with pytest.raises(ValidationError, match="Exactly two"):
        compare_groups(bad_groups, "group", "subject", ["x"])
    cohort["constant"] = 1
    with pytest.raises(ValidationError, match="singular"):
        compare_groups(cohort, "group", "subject", ["x"], ["constant"])
    with pytest.raises(ValidationError, match="distinct roles"):
        compare_groups(cohort, "group", "subject", ["x"], ["x"])


def test_no_variance_and_insufficient_complete_cases(cohort):
    cohort["x"] = 1
    with pytest.raises(ValidationError, match="zero variance"):
        compare_groups(cohort, "group", "subject", ["x"])
    cohort.loc[:4, "x"] = np.nan
    with pytest.raises(ValidationError, match="at least two"):
        compare_groups(cohort, "group", "subject", ["x"])


def test_subject_order_does_not_change_statistics(cohort):
    first = compare_groups(cohort, "group", "subject", ["x", "y"])
    second = compare_groups(cohort.sample(frac=1, random_state=10), "group", "subject", ["x", "y"])
    for left, right in zip(first["results"], second["results"]):
        assert left["effect"] == pytest.approx(right["effect"])
        assert left["p"] == pytest.approx(right["p"])
        assert left["q"] == pytest.approx(right["q"])
