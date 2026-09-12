import nibabel as nib
import numpy as np
import pytest
from brainfc import Config, InputError, extract_connectome
from nibabel.cifti2.cifti2_axes import BrainModelAxis, LabelAxis, SeriesAxis, ParcelsAxis


def test_dense_cifti_axis_alignment(tmp_path):
    rng = np.random.default_rng(1)
    time = SeriesAxis(0, 2, 50)
    brain = BrainModelAxis.from_surface([0, 2, 4, 6], 8, name="CortexLeft")
    label = LabelAxis(
        ["atlas"], [{0: ("background", (0, 0, 0, 0)), 3: ("A", (1, 0, 0, 1)), 17: ("B", (0, 1, 0, 1))}]
    )
    raw = rng.normal(size=(50, 4))
    nib.save(
        nib.Cifti2Image(raw, header=nib.Cifti2Header.from_axes((time, brain))),
        tmp_path / "input.dtseries.nii",
    )
    nib.save(
        nib.Cifti2Image(
            np.array([[3, 3, 17, 17]], dtype=np.int32), header=nib.Cifti2Header.from_axes((label, brain))
        ),
        tmp_path / "atlas.dlabel.nii",
    )
    cfg = Config(
        preprocessed=True, data_space="fsLR-left", atlas_space="fsLR-left", detrend=False, standardize=False
    )
    r = extract_connectome(tmp_path / "input.dtseries.nii", atlas=tmp_path / "atlas.dlabel.nii", config=cfg)
    np.testing.assert_allclose(
        r.timeseries, np.column_stack([raw[:, :2].mean(axis=1), raw[:, 2:].mean(axis=1)])
    )
    assert r.qc["t_r"] == 2
    wrong = BrainModelAxis.from_surface([1, 3, 5, 7], 8, name="CortexLeft")
    nib.save(
        nib.Cifti2Image(
            np.array([[3, 3, 17, 17]], dtype=np.int32), header=nib.Cifti2Header.from_axes((label, wrong))
        ),
        tmp_path / "wrong.dlabel.nii",
    )
    with pytest.raises(InputError, match="axes differ"):
        extract_connectome(tmp_path / "input.dtseries.nii", atlas=tmp_path / "wrong.dlabel.nii", config=cfg)


def test_parcellated_cifti(tmp_path):
    parcel = ParcelsAxis(["a", "b"], [np.zeros((0, 3), dtype=int)] * 2, [{}, {}])
    time = SeriesAxis(0, 1.2, 40)
    raw = np.random.default_rng(2).normal(size=(40, 2))
    p = tmp_path / "input.ptseries.nii"
    nib.save(nib.Cifti2Image(raw, header=nib.Cifti2Header.from_axes((time, parcel))), p)
    r = extract_connectome(p, config=Config(preprocessed=True, data_space="fsLR"))
    assert [r["roi_id"] for r in r.rois] == ["a", "b"]
    assert r.geometry is None


def test_gifti_pair(tmp_path):
    raw = np.random.default_rng(5).normal(size=(50, 6)).astype(np.float32)
    func = nib.gifti.GiftiImage(
        darrays=[nib.gifti.GiftiDataArray(x, intent="NIFTI_INTENT_TIME_SERIES") for x in raw]
    )
    label = nib.gifti.GiftiImage(
        darrays=[
            nib.gifti.GiftiDataArray(
                np.array([1, 1, 1, 2, 2, 2], dtype=np.int32), intent="NIFTI_INTENT_LABEL"
            )
        ]
    )
    nib.save(func, tmp_path / "left.func.gii")
    nib.save(label, tmp_path / "left.label.gii")
    r = extract_connectome(
        tmp_path / "left.func.gii",
        atlas=tmp_path / "left.label.gii",
        config=Config(
            preprocessed=True,
            data_space="surface-left",
            atlas_space="surface-left",
            detrend=False,
            standardize=False,
        ),
    )
    np.testing.assert_allclose(
        r.timeseries, np.column_stack([raw[:, :3].mean(axis=1), raw[:, 3:].mean(axis=1)]), atol=1e-7
    )
