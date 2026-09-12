import nibabel as nib
import numpy as np
import pandas as pd
import pytest
from scipy.io import savemat
from brainfc import Config, extract_connectome


@pytest.mark.parametrize("suffix", ["csv", "tsv", "txt", "1D", "npy", "npz", "mat"])
def test_time_series_formats_preserve_all_samples(tmp_path, suffix):
    raw = np.random.default_rng(22).normal(size=(40, 4))
    p = tmp_path / f"input.{suffix}"
    cfg = {"detrend": False, "standardize": False}
    if suffix == "npy":
        np.save(p, raw)
    elif suffix == "npz":
        np.savez(p, signal=raw)
    elif suffix == "mat":
        savemat(p, {"signal": raw})
    elif suffix in {"csv", "tsv"}:
        pd.DataFrame(raw, columns=["A", "B", "C", "D"]).to_csv(
            p, index=False, sep="," if suffix == "csv" else "\t"
        )
    else:
        np.savetxt(p, raw)
        cfg["table_header"] = False
    r = extract_connectome(p, config=Config(**cfg))
    np.testing.assert_allclose(r.timeseries, raw)
    np.testing.assert_allclose(r.connectivity, np.corrcoef(raw, rowvar=False))


@pytest.mark.parametrize("suffix", ["nii", "hdr", "mgz"])
def test_alternative_volume_containers(tmp_path, suffix):
    raw = np.random.default_rng(4).normal(size=(6, 6, 6, 30)).astype(np.float32)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    labels = np.zeros((6, 6, 6), dtype=np.int16)
    labels[:3] = 1
    labels[3:] = 2
    a = nib.Nifti1Image(labels, affine)
    a.header.set_xyzt_units("mm")
    nib.save(a, tmp_path / "atlas.nii")
    klass = {"nii": nib.Nifti1Image, "hdr": nib.Nifti1Pair, "mgz": nib.MGHImage}[suffix]
    image = klass(raw, affine)
    if hasattr(image.header, "set_xyzt_units"):
        image.header.set_xyzt_units("mm", "sec")
    p = tmp_path / f"bold.{suffix}"
    nib.save(image, p)
    r = extract_connectome(
        p,
        atlas=tmp_path / "atlas.nii",
        config=Config(
            preprocessed=True, data_space="test", atlas_space="test", detrend=False, standardize=False
        ),
    )
    expected = np.column_stack([raw[:3].reshape(-1, 30).mean(axis=0), raw[3:].reshape(-1, 30).mean(axis=0)])
    np.testing.assert_allclose(r.timeseries, expected, atol=1e-7)


def test_report_escapes_labels_and_is_self_contained(tmp_path):
    raw = np.random.default_rng(5).normal(size=(30, 2))
    p = tmp_path / "a.csv"
    pd.DataFrame(raw, columns=["</script><script>alert(1)</script>", "normal"]).to_csv(p, index=False)
    r = extract_connectome(p)
    report = r.view(tmp_path / "report.html")
    content = report.read_text(encoding="utf-8")
    assert "</script><script>alert(1)</script>" not in content
    assert "window.__FMRI_REPORT__=" in content
    assert "<script src=" not in content


def test_confounds_use_content_delimiter_not_filename(tmp_path):
    np.save(tmp_path / "ts.npy", np.random.default_rng(1).normal(size=(30, 2)))
    pd.DataFrame({"motion-x": np.arange(30), "wm": np.arange(30) ** 2}).to_csv(
        tmp_path / "c.csv", sep="\t", index=False
    )
    r = extract_connectome(
        tmp_path / "ts.npy", confounds=tmp_path / "c.csv", config=Config(confound_columns=("motion-x", "wm"))
    )
    assert r.qc["confound_columns"] == ["motion-x", "wm"]
