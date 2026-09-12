import json
import nibabel as nib
import numpy as np
import pandas as pd
import pytest
from brainfc import Config, InputError, extract_connectome, inspect_input, discover_bids


@pytest.fixture
def volume(tmp_path):
    rng = np.random.default_rng(3)
    ts = rng.normal(size=(100, 3))
    ts[:, 1] = 0.7 * ts[:, 0] + 0.3 * ts[:, 1]
    ts[:, 2] = -ts[:, 0] + 0.2 * ts[:, 2]
    atlas = np.zeros((6, 6, 6), dtype=np.int16)
    atlas[:2] = 3
    atlas[2:4] = 17
    atlas[4:] = 91
    data = np.zeros((6, 6, 6, 100), dtype=np.float32)
    for j, v in enumerate([3, 17, 91]):
        data[atlas == v] = ts[:, j] + 100
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    for name, arr in [("bold.nii.gz", data), ("atlas.nii.gz", atlas)]:
        img = nib.Nifti1Image(arr, affine)
        img.header.set_xyzt_units("mm", "sec")
        if arr.ndim == 4:
            img.header.set_zooms((2, 2, 2, 2))
        nib.save(img, tmp_path / name)
    table = pd.DataFrame(
        {"label_value": [91, 3, 17], "roi_id": ["C", "A", "B"], "name": ["Cortex C", "Cortex A", "Cortex B"]}
    )
    table.to_csv(tmp_path / "rois.tsv", sep="\t", index=False)
    return tmp_path, ts


def extract(volume, **changes):
    root, _ = volume
    cfg = dict(preprocessed=True, data_space="test", atlas_space="test", detrend=False, standardize=False)
    cfg.update(changes)
    return extract_connectome(
        root / "bold.nii.gz", atlas=root / "atlas.nii.gz", rois=root / "rois.tsv", config=Config(**cfg)
    )


def test_exact_roi_means_and_signs(volume):
    result = extract(volume)
    np.testing.assert_allclose(result.timeseries, volume[1] + 100, atol=1e-5)
    np.testing.assert_allclose(result.connectivity, np.corrcoef(volume[1], rowvar=False), atol=1e-5)
    assert [r["roi_id"] for r in result.rois] == ["A", "B", "C"]
    assert result.qc["roi_voxels"] == [72, 72, 72]
    assert result.connectivity[0, 2] < -0.9
    assert result.fisher_z[0, 0] == 0
    assert np.isfinite(result.fisher_z).all()


def test_raw_images_cannot_skip_preprocessing(volume):
    with pytest.raises(InputError, match="preprocessed=True"):
        extract(volume, preprocessed=False)


def test_space_mismatch_rejected(volume):
    with pytest.raises(InputError, match="matching"):
        extract(volume, atlas_space="other")


def test_tr_conflict(volume):
    with pytest.raises(InputError, match="TR metadata conflict"):
        extract(volume, t_r=3.0)


def test_missing_roi_rejected(volume):
    p, _ = volume
    img = nib.load(p / "bold.nii.gz")
    cropped = nib.Nifti1Image(np.asarray(img.dataobj)[:3], img.affine)
    cropped.header.set_xyzt_units("mm", "sec")
    nib.save(cropped, p / "bold.nii.gz")
    with pytest.raises(InputError, match="absent"):
        extract(volume)


def test_confounds_remove_shared_signal_and_keep_original_indices(tmp_path):
    rng = np.random.default_rng(4)
    conf = rng.normal(size=(200, 6))
    ts = rng.normal(size=(200, 3)) + conf[:, [0]] * 10
    np.save(tmp_path / "ts.npy", ts)
    frame = pd.DataFrame(conf, columns=[f"trans_{a}" for a in "xyz"] + [f"rot_{a}" for a in "xyz"])
    frame["framewise_displacement"] = 0.1
    frame.loc[0, "framewise_displacement"] = np.nan
    frame.loc[20, "framewise_displacement"] = 0.9
    frame.to_csv(tmp_path / "c.tsv", sep="\t", index=False)
    result = extract_connectome(
        tmp_path / "ts.npy", confounds=tmp_path / "c.tsv", config=Config(discard=2, fd_threshold=0.5)
    )
    assert len(result.timeseries) == 197
    assert result.sample_indices[0] == 2
    assert 20 not in result.sample_indices
    assert abs(result.connectivity[0, 1]) < 0.2
    assert result.qc["n_censored"] == 3


@pytest.mark.parametrize("method", ["pearson", "spearman", "partial"])
def test_estimators_properties(volume, method):
    result = extract(volume, method=method)
    np.testing.assert_allclose(result.connectivity, result.connectivity.T)
    np.testing.assert_allclose(np.diag(result.connectivity), 1)
    assert np.isfinite(result.connectivity).all()


def test_constant_roi_rejected(tmp_path):
    np.save(tmp_path / "constant.npy", np.ones((100, 4)))
    with pytest.raises(InputError, match="Zero-variance"):
        extract_connectome(tmp_path / "constant.npy")


def test_filter_and_censor_order_retains_indices(tmp_path):
    rng = np.random.default_rng(1)
    np.save(tmp_path / "ts.npy", rng.normal(size=(160, 3)))
    frame = pd.DataFrame(
        rng.normal(size=(160, 6)), columns=[f"trans_{a}" for a in "xyz"] + [f"rot_{a}" for a in "xyz"]
    )
    frame["framewise_displacement"] = 0.1
    frame.loc[[0, 8, 159], "framewise_displacement"] = 0.8
    frame.to_csv(tmp_path / "c.tsv", sep="\t", index=False)
    r = extract_connectome(
        tmp_path / "ts.npy",
        confounds=tmp_path / "c.tsv",
        config=Config(t_r=2, low_pass=0.08, high_pass=0.01, fd_threshold=0.5),
    )
    assert r.timeseries.shape == (157, 3)
    assert r.sample_indices.tolist() == [i for i in range(160) if i not in [0, 8, 159]]


def test_multi_variable_requires_choice(tmp_path):
    a = np.random.default_rng(1).normal(size=(30, 3))
    np.savez(tmp_path / "data.npz", a=a, b=a)
    with pytest.raises(InputError, match="Choose variable"):
        extract_connectome(tmp_path / "data.npz")
    assert extract_connectome(tmp_path / "data.npz", config=Config(variable="a")).connectivity.shape == (3, 3)


def test_nifti_nonfinite_rejected(volume):
    p, _ = volume
    img = nib.load(p / "bold.nii.gz")
    arr = np.asarray(img.dataobj)
    arr[1, 1, 1, 0] = np.nan
    nib.save(nib.Nifti1Image(arr, img.affine, img.header), p / "bold.nii.gz")
    with pytest.raises(InputError, match="Nonfinite"):
        extract(volume)


def test_discovery_run_entities(tmp_path):
    root = tmp_path / "sub-01" / "func"
    root.mkdir(parents=True)
    for run in (1, 2):
        base = f"sub-01_task-rest_run-{run}"
        (root / f"{base}_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz").touch()
        (root / f"{base}_desc-confounds_timeseries.tsv").touch()
    rows = discover_bids(tmp_path)
    assert len(rows) == 2
    assert "run-1_desc-confounds" in rows[0]["confounds"]
    assert "run-2_desc-confounds" in rows[1]["confounds"]


def test_inspect_volume(volume):
    info = inspect_input(volume[0] / "bold.nii.gz")
    assert info["shape"] == [6, 6, 6, 100]
    assert info["orientation"] == ["R", "A", "S"]


def test_export_is_complete_and_preserves_existing(volume, tmp_path):
    result = extract(volume)
    p = result.save(tmp_path / "result", figures=False, report=False)
    np.testing.assert_allclose(np.load(p / "connectivity.npy"), result.connectivity)
    qc = json.loads((p / "qc.json").read_text())
    assert qc["n_input"] == 100
    with pytest.raises(FileExistsError):
        result.save(p, figures=False, report=False)


def test_fmriprep_plan_quoting_and_separation(tmp_path):
    from brainfc.preprocessing import fmriprep_plan

    bids = tmp_path / "bids with spaces"
    bids.mkdir()
    (bids / "dataset_description.json").write_text("{}")
    (bids / "sub-01").mkdir()
    license = tmp_path / "license.txt"
    license.write_text("example")
    plan = fmriprep_plan(bids, tmp_path / "out", license, participant="01")
    assert any("bids with spaces:/data:ro" in a for a in plan.argv)
    assert plan.to_dict()["powershell"].startswith("& 'docker'")
    with pytest.raises(InputError, match="separate"):
        fmriprep_plan(bids, bids / "derivatives", license)
