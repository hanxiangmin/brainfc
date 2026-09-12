import hashlib
import json

import h5py
import numpy as np
import pytest
from scipy.io import savemat

from brainfc.network.io import inspect_file, load_data, validate_dataset
from brainfc.network.types import BrainDataset, ValidationError


def test_plain_numeric_text_preserves_first_row(tmp_path):
    path = tmp_path / "signals.tsv"
    path.write_text("0\t1\t2\n1\t3\t5\n2\t8\t9\n3\t4\t7\n", encoding="utf-8")
    dataset = load_data(path, kind="timeseries")
    assert dataset.data.shape == (4, 3)
    np.testing.assert_array_equal(dataset.data[0], [0, 1, 2])
    assert any("TR" in item for item in dataset.warnings)


def test_adhd_named_auxiliary_columns_are_removed(tmp_path):
    path = tmp_path / "adhd.1D"
    path.write_text(
        "File\tSub-brick\tMean_2001 \tMean_2002\n"
        "scan.nii.gz\t0[?]\t1\t4\n"
        "scan.nii.gz\t1[?]\t2\t3\n"
        "scan.nii.gz\t2[?]\t4\t5\n", encoding="utf-8",
    )
    info = inspect_file(path)
    assert info["variables"][0]["shape"] == [3, 2]
    assert info["discarded_columns"] == ["File", "Sub-brick"]
    dataset = load_data(path, preset="adhd")
    assert dataset.roi_ids == ["Mean_2001", "Mean_2002"]
    np.testing.assert_array_equal(dataset.data, [[1, 4], [2, 3], [4, 5]])
    assert dataset.metadata["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert str(tmp_path) not in json.dumps(dataset.metadata)


def test_commented_adhd_header_and_slice(tmp_path):
    path = tmp_path / "adhd.1D"
    path.write_text("# generated\n# File Sub-brick R1 R2 R3\nf 0 1 2 3\nf 1 2 3 4\nf 2 3 4 5\n")
    dataset = load_data(path, roi_columns="1:3")
    assert dataset.roi_ids == ["R2", "R3"]
    np.testing.assert_array_equal(dataset.data, [[2, 3], [3, 4], [4, 5]])


def test_multiple_mat_arrays_require_variable_and_fisher_kind(tmp_path):
    path = tmp_path / "arrays.mat"
    corr = np.array([[1, .7], [.7, 1.]])
    z = np.array([[0, np.arctanh(.7)], [np.arctanh(.7), 0]])
    savemat(path, {"ROICorrelation": corr, "ROICorrelation_FisherZ": z})
    info = inspect_file(path)
    assert info["suggested_variable"] is None
    with pytest.raises(ValidationError, match="Multiple"):
        load_data(path)
    dataset = load_data(path, variable="ROICorrelation_FisherZ")
    assert dataset.matrix_kind == "fisher_z"
    np.testing.assert_array_equal(dataset.data, z)
    with pytest.raises(ValidationError, match="FisherZ"):
        load_data(path, variable="ROICorrelation_FisherZ", matrix_kind="correlation")
    with pytest.raises(ValidationError, match="Unknown numeric variable"):
        load_data(path, variable="absent")


def test_mat_v73_restores_matlab_orientation(tmp_path):
    path = tmp_path / "matlab.mat"
    signals = np.arange(24, dtype=float).reshape(8, 3)
    with h5py.File(path, "w") as file:
        dataset = file.create_dataset("ROISignals", data=signals.T)
        dataset.attrs["MATLAB_class"] = np.bytes_("double")
        file["external"] = h5py.ExternalLink("not-read.mat", "/data")
    assert inspect_file(path)["variables"][0]["shape"] == [8, 3]
    np.testing.assert_array_equal(load_data(path).data, signals)


def test_mdd_requires_explicit_roi_choice(tmp_path):
    path = tmp_path / "ROISignals.mat"
    savemat(path, {"ROISignals": np.random.default_rng(3).normal(size=(20, 1833))})
    with pytest.raises(ValidationError, match="explicit ROI"):
        load_data(path, preset="mdd")
    dataset = load_data(path, preset="mdd", roi_columns="0:116", metadata={"atlas": "user verified"})
    assert dataset.data.shape == (20, 116)
    assert dataset.metadata["source_shape"] == [20, 1833]
    assert dataset.metadata["atlas"] == "user verified"


def test_connectivity_roi_subset_preserves_row_column_alignment(tmp_path):
    path = tmp_path / "fc.npy"
    matrix = np.array([[1, .2, .3], [.2, 1, .5], [.3, .5, 1]])
    np.save(path, matrix)
    dataset = load_data(path, roi_columns=[2, 0], roi_ids=["C", "A"])
    np.testing.assert_array_equal(dataset.data, matrix[np.ix_([2, 0], [2, 0])])
    assert dataset.roi_ids == ["C", "A"]


@pytest.mark.parametrize("selection", [[1, 1], [-1, 2], [True, 1], [0, 3], "0:4", "-1:2", "0:2:0", [], "2:1"])
def test_invalid_roi_selection_is_rejected(tmp_path, selection):
    path = tmp_path / "fc.npy"
    np.save(path, np.eye(3))
    with pytest.raises(ValidationError, match="ROI"):
        load_data(path, roi_columns=selection)


@pytest.mark.parametrize("array,kind,message", [
    (np.array([[1, np.nan], [np.nan, 1]]), "connectivity", "Non-finite"),
    (np.array([[1, .2], [.3, 1]]), "connectivity", "symmetric"),
    (np.ones((10, 2)), "timeseries", "Constant"),
    (np.ones((2, 3)), "connectivity", "square"),
    (np.zeros((0, 2)), "timeseries", "nonempty"),
    (np.array([[1., 2], [2, 1]]), "connectivity", "Correlation"),
])
def test_invalid_data_rejected(array, kind, message):
    with pytest.raises(ValidationError, match=message):
        validate_dataset(BrainDataset(array, kind))


def test_npz_numeric_only_and_multiple_selection(tmp_path):
    path = tmp_path / "arrays.npz"
    np.savez(path, fc=np.eye(3), timeseries=np.arange(12).reshape(4, 3))
    with pytest.raises(ValidationError, match="Multiple"):
        load_data(path)
    assert load_data(path, variable="fc").kind == "connectivity"
    unsafe = tmp_path / "objects.npy"
    np.save(unsafe, np.array([[{"secret": "not deserialized"}]], dtype=object))
    with pytest.raises(ValidationError, match="objects"):
        inspect_file(unsafe)


def test_complex_array_not_silently_cast(tmp_path):
    path = tmp_path / "complex.mat"
    savemat(path, {"data": np.eye(2, dtype=complex) * (1 + 1j)})
    with pytest.raises(ValidationError, match="complex"):
        load_data(path)


def test_header_malformed_row_and_metadata_mismatch(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("A,B\n1,2\n3,4,5\n")
    with pytest.raises(ValidationError, match="Row 3"):
        inspect_file(path)
    dataset = BrainDataset(np.eye(3), "connectivity", roi_ids=["A", "A", "C"])
    with pytest.raises(ValidationError, match="unique"):
        validate_dataset(dataset)
    dataset = BrainDataset(np.eye(3), "connectivity", coordinates=np.ones((2, 3)))
    with pytest.raises(ValidationError, match="Coordinates"):
        validate_dataset(dataset)


def test_no_atlas_invented_and_time_validation(tmp_path):
    path = tmp_path / "signals.npy"
    np.save(path, np.arange(24).reshape(8, 3))
    dataset = load_data(path, metadata={"TR": 2.0, "gsr": False, "removed_frames": []})
    assert "atlas" not in dataset.metadata
    assert not any("TR/time" in warning for warning in dataset.warnings)
    with pytest.raises(ValidationError, match="TR"):
        load_data(path, metadata={"tr": -1})
    with pytest.raises(ValidationError, match="Time vector"):
        load_data(path, metadata={"time_vector": list(range(7))})


def test_covariance_explicit_scale_and_auto_ambiguity(tmp_path):
    path = tmp_path / "covariance.npy"
    np.save(path, [[4, 2], [2, 9]])
    assert load_data(path).matrix_kind == "covariance"
    unknown = tmp_path / "unknown.npy"
    np.save(unknown, [[1, 2], [3, 4]])
    with pytest.raises(ValidationError, match="ambiguous"):
        load_data(unknown)


def test_empty_and_oversized_arrays_rejected(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.touch()
    with pytest.raises(ValidationError, match="empty"):
        inspect_file(empty)
    dataset = BrainDataset(np.ones((3, 1001)), "timeseries")
    with pytest.raises(ValidationError, match="Resource limit"):
        validate_dataset(dataset)


def test_original_filename_retains_scale_after_opaque_upload_rename(tmp_path):
    path = tmp_path / "7fa8b9.npy"
    np.save(path, [[0, 1.4], [1.4, 0]])
    info = inspect_file(path, source_name="C:\\upload\\ROICorrelation_FisherZ.npy")
    assert info["name"] == "ROICorrelation_FisherZ.npy"
    assert info["suggested_matrix_kind"] == "fisher_z"
    dataset = load_data(path, source_name="ROICorrelation_FisherZ.npy")
    assert dataset.matrix_kind == "fisher_z"
    assert dataset.metadata["source_name"] == "ROICorrelation_FisherZ.npy"


def test_fisher_z_undefined_diagonal_is_explicitly_normalized_without_source_change(tmp_path):
    path = tmp_path / "ROICorrelation_FisherZ.mat"
    savemat(path, {"ROICorrelation_FisherZ": [[np.inf, .7], [.7, np.nan]]})
    before = path.read_bytes()
    dataset = load_data(path)
    np.testing.assert_array_equal(dataset.data, [[0, .7], [.7, 0]])
    assert dataset.metadata["nonfinite_fisher_z_diagonal_replaced"] == 2
    assert any("self-connections" in item for item in dataset.warnings)
    assert path.read_bytes() == before
    assert any("self-connections" in item for item in validate_dataset(
        BrainDataset([[np.inf, .7], [.7, np.nan]], "connectivity", matrix_kind="fisher_z")
    ))
    bad = BrainDataset([[0, np.inf], [np.inf, 0]], "connectivity", matrix_kind="fisher_z")
    with pytest.raises(ValidationError, match="Non-finite"):
        validate_dataset(bad)


def test_roi_center_metadata_cannot_masquerade_as_timeseries(tmp_path):
    path = tmp_path / "ROI_CenterOfMass.mat"
    savemat(path, {"ROICenter": np.arange(348).reshape(116, 3)})
    info = inspect_file(path)
    assert info["suggested_kind"] == "auto"
    assert any("coordinate/label metadata" in message for message in info["warnings"])
    with pytest.raises(ValidationError, match="ROI coordinate/label metadata"):
        load_data(path, kind="timeseries")
