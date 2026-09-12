import numpy as np
import pytest
from scipy.stats import spearmanr

from brainfc.network.connectivity import compute_connectivity, fisher_z, inverse_fisher_z
from brainfc.network.types import ValidationError


def test_pearson_matches_sample_correlation_and_retains_sign():
    rng = np.random.default_rng(42)
    timeseries = rng.normal(size=(35, 5))
    timeseries[:, 1] = -timeseries[:, 0]
    actual = compute_connectivity(timeseries)
    np.testing.assert_allclose(actual, np.corrcoef(timeseries, rowvar=False), atol=1e-14)
    assert actual[0, 1] == pytest.approx(-1)


def test_spearman_rank_ties_and_permutation():
    values = np.array([[1, 6, 2], [2, 5, 5], [2, 3, 5], [4, 2, 9], [8, 1, 10]])
    result = compute_connectivity(values, "spearman")
    np.testing.assert_allclose(result, spearmanr(values).statistic, atol=1e-14)
    permutation = [2, 0, 1]
    np.testing.assert_allclose(compute_connectivity(values[:, permutation], "spearman"), result[np.ix_(permutation, permutation)])


def test_partial_is_ledoit_wolf_on_standardized_channels():
    from sklearn.covariance import LedoitWolf

    timeseries = np.random.default_rng(4).normal(size=(12, 20))
    result = compute_connectivity(timeseries, "partial")
    standardized = (timeseries - timeseries.mean(axis=0)) / timeseries.std(axis=0, ddof=1)
    precision = np.linalg.inv(LedoitWolf().fit(standardized).covariance_)
    expected = -precision / np.sqrt(np.outer(np.diag(precision), np.diag(precision)))
    np.fill_diagonal(expected, 1)
    np.testing.assert_allclose(result, expected, atol=1e-12)
    assert np.isfinite(result).all()


@pytest.mark.parametrize("method", ["pearson", "spearman", "partial"])
def test_channel_permutation_and_scale_invariance(method):
    data = np.random.default_rng(8).normal(size=(80, 7))
    order = [6, 2, 0, 5, 1, 4, 3]
    expected = compute_connectivity(data, method)[np.ix_(order, order)]
    np.testing.assert_allclose(compute_connectivity(data[:, order] * np.arange(1, 8), method), expected, atol=1e-12)


def test_fisher_roundtrip_and_finite_diagonal():
    corr = np.array([[1, -0.6, 0.4], [-0.6, 1, 0.2], [0.4, 0.2, 1]])
    z = fisher_z(corr)
    assert np.isfinite(z).all()
    np.testing.assert_array_equal(np.diag(z), 0)
    np.fill_diagonal(z, np.inf)
    np.testing.assert_allclose(inverse_fisher_z(z), corr)
    with pytest.warns(RuntimeWarning, match="Perfect"):
        assert np.isfinite(fisher_z(np.ones((2, 2)))).all()


@pytest.mark.parametrize("data", [np.ones((10, 2)), [[1, 2], [3, 4]], np.array([[1, 2], [3, np.nan], [4, 6]]), np.empty((3, 0))])
def test_invalid_timeseries_is_rejected(data):
    with pytest.raises(ValidationError):
        compute_connectivity(data)


def test_fisher_rejects_invalid_offdiagonal():
    with pytest.raises(ValidationError):
        fisher_z([[1, 1.1], [1.1, 1]])
    with pytest.raises(ValidationError):
        inverse_fisher_z([[0, np.inf], [np.inf, 0]])


def test_numeric_functions_do_not_modify_input():
    data = np.random.default_rng(1).normal(size=(12, 4))
    original = data.copy()
    matrix = compute_connectivity(data)
    matrix_original = matrix.copy()
    fisher_z(matrix)
    np.testing.assert_array_equal(data, original)
    np.testing.assert_array_equal(matrix, matrix_original)
