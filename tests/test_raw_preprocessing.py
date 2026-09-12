"""Analytic temporal/geometry tests and real ANTs registration of a known phantom."""

import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from brainfc import InputError, PreprocessConfig, inspect_raw, discover_raw
from brainfc.raw.temporal import slice_time_correct
from brainfc.raw.pipeline import _ants, _ants_session, _motion_table, PreprocessedRun


def inputs(tmp_path):
    rng = np.random.default_rng(31)
    affine = np.diag([2., 2., 2., 1.])
    affine[:3, 3] = [-20, -24, -28]
    paths = []
    for name, shape in (("bold", (20, 24, 28, 40)), ("t1w", (20, 24, 28))):
        image = nib.Nifti1Image(rng.random(shape).astype("float32"), affine)
        image.header.set_xyzt_units("mm", "sec")
        if name == "bold":
            image.header.set_zooms((2, 2, 2, 2))
        path = tmp_path / f"{name}.nii.gz"
        nib.save(image, path)
        paths.append(path)
    return paths


def test_fourier_slice_correction_recovers_known_continuous_signal():
    n, tr = 300, 2.
    offsets = np.array([0., .5, 1., 1.5, 0., .5])  # repeated multiband timing
    def f(t):
        return np.sin(2*np.pi*.04*t) + .4*np.cos(2*np.pi*.09*t)
    data = np.stack([f(np.arange(n)*tr + t) for t in offsets])[None, None]
    corrected = slice_time_correct(data, offsets, tr)
    target = f(np.arange(n)*tr + tr*.5)
    # Compare interior independently of the documented reflected endpoints.
    raw_error = np.mean((data[..., 30:-30] - target[30:-30])**2)
    error = np.mean((corrected[..., 30:-30] - target[30:-30])**2)
    assert error < raw_error/500
    np.testing.assert_array_equal(corrected[:, :, 2], data[:, :, 2].astype("float32"))
    assert corrected.shape == data.shape


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_slice_correction_respects_spatial_axis(axis):
    rng = np.random.default_rng(4)
    x = rng.normal(size=(3, 4, 5, 40)).astype("float32")
    times = np.arange(x.shape[axis])/x.shape[axis]
    y = slice_time_correct(x, times, 2, axis=axis)
    permuted = np.moveaxis(x, axis, 2)
    expected = np.moveaxis(slice_time_correct(permuted, times, 2), 2, axis)
    np.testing.assert_allclose(y, expected)


def test_inspection_never_guesses_slice_order_and_checks_conflicts(tmp_path):
    bold, t1 = inputs(tmp_path)
    info = inspect_raw(bold, t1)
    assert not info["ready"] and len(info["missing"]) == 2
    assert inspect_raw(bold, t1, config=PreprocessConfig(slice_timing="skip"))["ready"]
    sidecar = tmp_path / "bold.json"
    sidecar.write_text(json.dumps({"RepetitionTime": 2, "SliceTiming": list(np.arange(28)/28), "SliceEncodingDirection": "k-"}))
    info = inspect_raw(bold, t1)
    assert info["ready"] and info["slice_axis"] == 2
    assert info["slice_times"] == list((np.arange(28)/28)[::-1])
    with pytest.raises(InputError, match="dimension disagrees"):
        inspect_raw(bold, t1, config=PreprocessConfig(slice_axis=1))
    with pytest.raises(InputError, match="TR disagrees"):
        inspect_raw(bold, t1, config=PreprocessConfig(t_r=3))
    sidecar.write_text(json.dumps({"SliceTiming": [10]*28, "RepetitionTime": 2}))
    with pytest.raises(InputError, match="seconds"):
        inspect_raw(bold, t1)


def test_explicit_json_is_respected_and_tr_units_are_seconds(tmp_path):
    bold, t1 = inputs(tmp_path)
    image = nib.load(bold)
    image.header.set_xyzt_units("mm", "msec")
    image.header.set_zooms((2, 2, 2, 2000))
    nib.save(image, bold)
    supplied = tmp_path / "reviewed.json"
    supplied.write_text('{"RepetitionTime": 2}')
    (tmp_path / "bold.json").write_text('{"RepetitionTime": 99}')
    assert inspect_raw(bold, t1, sidecar=supplied, config=PreprocessConfig(slice_timing="skip"))["t_r"] == 2


def test_geometry_rejects_shear_and_unknown_units(tmp_path):
    bold, t1 = inputs(tmp_path)
    image = nib.load(t1)
    affine = image.affine.copy()
    affine[0, 1] = .3
    bad = nib.Nifti1Image(image.get_fdata(), affine)
    bad.header.set_xyzt_units("mm")
    nib.save(bad, t1)
    with pytest.raises(InputError, match="Sheared"):
        inspect_raw(bold, t1)
    bad = nib.Nifti1Image(image.get_fdata(), image.affine)
    nib.save(bad, t1)
    with pytest.raises(InputError, match="millimetres"):
        inspect_raw(bold, t1)


def test_conflicting_nifti_coordinate_forms_rejected(tmp_path):
    bold, t1 = inputs(tmp_path)
    image = nib.load(bold)
    shifted = image.affine.copy()
    shifted[0, 3] += 10
    image.set_qform(shifted, code=1)
    nib.save(image, bold)
    with pytest.raises(InputError, match="qform and sform"):
        inspect_raw(bold, t1)


def test_raw_discovery_does_not_pair_other_subjects_or_sessions(tmp_path):
    for sub, session in (("01", "a"), ("01", "b"), ("02", "a")):
        base = tmp_path / f"sub-{sub}" / f"ses-{session}"
        (base / "func").mkdir(parents=True)
        (base / "func" / f"sub-{sub}_ses-{session}_task-rest_bold.nii.gz").touch()
        if sub == "01" and session == "b":
            (base / "anat").mkdir()
            (base / "anat" / f"sub-{sub}_ses-{session}_T1w.nii.gz").touch()
    pairs = discover_raw(tmp_path)
    assert len(pairs) == 1 and "ses-b" in pairs[0]["bold"] and "ses-b" in pairs[0]["t1w"]


def test_ants_adapter_preserves_oblique_ras_landmarks(tmp_path):
    ants = _ants()
    angle = .13
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
    affine = np.eye(4)
    affine[:3, :3] = rotation @ np.diag([2., 3., 4.])
    affine[:3, 3] = [-15., 7., -32.]
    arr = np.zeros((12, 15, 18), dtype="float32")
    arr[4, 6, 9] = 1
    path = tmp_path / "oblique.nii.gz"
    nib.save(nib.Nifti1Image(arr, affine), path)
    im = ants.image_read(str(path))
    lps = np.asarray(im.origin) + im.direction @ (np.array([4, 6, 9])*im.spacing)
    np.testing.assert_allclose(lps*[-1, -1, 1], (affine @ [4, 6, 9, 1])[:3], atol=1e-5)
    ants.image_write(im, str(tmp_path / "roundtrip.nii.gz"))
    np.testing.assert_allclose(nib.load(tmp_path / "roundtrip.nii.gz").affine, affine, atol=1e-5)


def test_actual_ants_rigid_registration_recovers_translation(tmp_path):
    ants = _ants()
    grid = np.indices((40, 40, 40)).astype(float)
    arr = sum(scale*np.exp(-sum(((grid[i]-center[i])/width)**2 for i in range(3)))
              for center, width, scale in [((15, 18, 20), 8, 1), ((26, 14, 17), 4, .7), ((12, 27, 26), 3, .5)])
    fixed = ants.from_numpy(arr.astype("float32"), spacing=(2, 2, 2))
    moved = ants.from_numpy(arr.astype("float32"), spacing=(2, 2, 2), origin=(4, -2, 2))
    with _ants_session(42):
        reg = ants.registration(fixed, moved, type_of_transform="Rigid", aff_metric="meansquares",
                                aff_random_sampling_rate=1, aff_iterations=(500, 200, 50, 0),
                                outprefix=str(tmp_path / "rigid_"))
    np.testing.assert_allclose(reg["warpedmovout"].get_center_of_mass(), fixed.get_center_of_mass(), atol=.6)
    a, b = arr.ravel(), reg["warpedmovout"].numpy().ravel()
    assert np.corrcoef(a, b)[0, 1] > .995
    table = _motion_table(ants, [reg["fwdtransforms"]]*2, [0, 0])
    assert table.shape == (2, 13)
    assert np.isnan(table.framewise_displacement.iloc[0])


def test_extraction_requires_actual_qc_confirmation():
    run = PreprocessedRun(Path("unused"), {}, {}, {})
    with pytest.raises(InputError, match="qc_reviewed"):
        run.extract()


def test_seed_uses_actual_ants_configuration_and_restores_caller_state(monkeypatch, tmp_path):
    import importlib
    ants = _ants()
    module = importlib.import_module("ants.registration.registration")
    real = module.get_lib_fn
    captured = []

    def intercept(name):
        fn = real(name)
        if name != "antsRegistration":
            return fn

        def call(args):
            captured.append(args)
            return fn(args)
        return call

    monkeypatch.setattr(module, "get_lib_fn", intercept)
    previous = (ants.config._deterministic, ants.config._random_seed)
    with _ants_session(97):
        x = np.random.default_rng(7).random((16, 16, 16)).astype("float32")
        im = ants.from_numpy(x)
        ants.registration(im, im, type_of_transform="Rigid", aff_iterations=(1, 0, 0, 0),
                          outprefix=str(tmp_path / "seed_"))
    assert (ants.config._deterministic, ants.config._random_seed) == previous
    assert captured and captured[-1][captured[-1].index("--random-seed") + 1] == "97"
    with pytest.raises(RuntimeError):
        with _ants_session(1):
            raise RuntimeError("test cleanup")
    assert (ants.config._deterministic, ants.config._random_seed) == previous


@pytest.mark.parametrize("kw", [{"slice_axis": True}, {"discard": 1.2}, {"reference": 1},
                                   {"t_r": float("nan")}, {"smoothing_fwhm": -1}, {"slice_timing": "guess"}])
def test_invalid_preprocess_settings_rejected(kw):
    with pytest.raises(InputError):
        PreprocessConfig(**kw)
