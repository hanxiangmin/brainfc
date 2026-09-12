from types import SimpleNamespace
from pathlib import Path
import numpy as np
import nibabel as nib
import pytest
from fastapi.testclient import TestClient
from brainfc import InputError, dataset_preset, dataset_presets
from brainfc.workflow import check_input, preflight, validate_guidance, check_raw_bids
from brainfc.plotting import edges_of, plot_views
from brainfc.web.app import create_app


def test_preset_scope_and_independent_copies():
    assert dataset_preset("adni", "adni3-basic")["t_r"] == 3
    assert dataset_preset("adni", "adni3-advanced")["t_r"] == 0.6
    assert dataset_preset("ppmi", "2025-mb")["t_r"] == 1
    assert dataset_preset("ppmi", "2025-alt")["t_r"] == 2.5
    assert dataset_preset("adhd200", "brown")["t_r"] == 2
    for dataset, variant in [("abide", "raw"), ("adhd200", "auto"), ("ppmi", "auto"), ("mdd", "raw")]:
        assert dataset_preset(dataset, variant)["t_r"] is None
    catalog = dataset_presets()
    catalog["datasets"].clear()
    assert len(dataset_presets()["datasets"]) == 6
    with pytest.raises(InputError):
        dataset_preset("ppmi", "adni3-basic")


@pytest.fixture
def volume(tmp_path):
    path = tmp_path / "sub-01_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
    image = nib.Nifti1Image(np.random.default_rng(4).normal(size=(4, 5, 6, 40)), np.eye(4))
    image.header.set_xyzt_units("mm", "sec")
    image.header.set_zooms((1, 1, 1, 2))
    nib.save(image, path)
    atlas = tmp_path / "atlas.nii.gz"
    nib.save(nib.Nifti1Image(np.ones((4, 5, 6), dtype="int16"), np.eye(4)), atlas)
    return {
        "source": str(path),
        "atlas": str(atlas),
        "config": {
            "preprocessed": True,
            "data_space": "MNI152NLin6Asym",
            "atlas_space": "MNI152NLin6Asym",
            "t_r": 2,
        },
    }


def test_preflight_tr_and_type_boundaries(volume, tmp_path):
    assert check_input(volume["source"])["t_r"] == 2
    assert preflight(volume)["n_frames"] == 40
    volume["config"]["t_r"] = 3
    with pytest.raises(InputError, match="TR"):
        preflight(volume)
    volume["config"]["t_r"] = 2
    volume["config"]["preprocessed"] = False
    with pytest.raises(InputError, match="预处理"):
        preflight(volume, stage="spatial")
    matrix = tmp_path / "matrix.npy"
    np.save(matrix, np.eye(10))
    with pytest.raises(InputError, match="对称方阵"):
        check_input(matrix)
    with pytest.raises(InputError, match="4D"):
        check_input(volume["atlas"])


def test_guidance_requires_explicit_skips_and_reviews(volume):
    guide = dict(
        dataset="custom",
        variant="custom",
        source_confirmed=True,
        spatial_confirmed=True,
        denoise_confirmed=True,
        review_confirmed=False,
        input_kind="volume",
    )
    volume["guidance"] = guide
    with pytest.raises(InputError, match="按顺序"):
        validate_guidance(volume)
    guide["review_confirmed"] = True
    with pytest.raises(InputError, match="混杂"):
        validate_guidance(volume)
    guide["confounds_decision"] = "skip"
    with pytest.raises(InputError, match="解剖参考"):
        validate_guidance(volume)
    guide["reference_decision"] = "skip"
    assert validate_guidance(volume)["official_preset"]["dataset"] == "custom"
    guide["input_kind"] = "raw-bids"
    with pytest.raises(InputError, match="质控"):
        validate_guidance(volume)


def test_preflight_checks_filtering_and_censoring(volume, tmp_path):
    volume["config"]["low_pass"] = 0.3
    with pytest.raises(InputError, match="Nyquist"):
        preflight(volume)
    volume["config"].pop("low_pass")
    volume["config"]["fd_threshold"] = 0.5
    with pytest.raises(InputError, match="confounds"):
        preflight(volume)
    confounds = tmp_path / "conf.tsv"
    confounds.write_text("framewise_displacement\tnoise\n" + "1\t0\n" * 40)
    volume["confounds"] = str(confounds)
    volume["config"]["confound_columns"] = ["noise"]
    with pytest.raises(InputError, match="不足"):
        preflight(volume)


def test_same_selection_before_edge_limit_and_negative_edges(tmp_path):
    result = SimpleNamespace(
        rois=[dict(roi_id=str(i), coordinates=[i * 10, (i % 2) * 20, i * 3]) for i in range(4)],
        connectivity=np.array(
            [[1, 0.8, -0.9, 0.1], [0.8, 1, 0.7, 0.4], [-0.9, 0.7, 1, -0.6], [0.1, 0.4, -0.6, 1]]
        ),
        geometry=None,
        qc={"n_rois": 4},
    )
    # Node 3's edges must be limited AFTER the node selection, not after global top-2.
    assert edges_of(result, 0.3, 2, {"kind": "node", "id": "3"}) == [(2, 3, -0.6), (1, 3, 0.4)]
    assert edges_of(result, 0.3, 2, {"kind": "edge", "id": "1:3"}) == [(1, 3, 0.4)]
    assert edges_of(result, 0.8, 2, {"kind": "node", "id": "3"}) == []
    with pytest.raises(InputError):
        edges_of(result, selection={"kind": "node", "id": "absent"})
    plot_views(result, tmp_path / "selected.svg", selection={"kind": "node", "id": "3"})
    assert (tmp_path / "selected.svg").stat().st_size > 1000


def test_web_preflight_and_incomplete_wizard_not_queued(volume, tmp_path):
    with TestClient(create_app(tmp_path / "workspace")) as client:
        assert len(client.get("/api/presets").json()["datasets"]) == 6
        assert client.post("/api/preflight", json={**volume, "stage": "input"}).json()["t_r"] == 2
        volume["guidance"] = {"dataset": "custom", "variant": "custom"}
        assert client.post("/api/jobs", json=volume).status_code == 422
        assert client.get("/api/jobs").json() == []


def test_raw_bids_missing_modalities_are_blocked(tmp_path):
    root = tmp_path / "bids"
    root.mkdir()
    (root / "dataset_description.json").write_text("{}")
    with pytest.raises(InputError, match="BIDS"):
        check_raw_bids({"bids_dir": str(root)})
    func = root / "sub-01" / "func"
    func.mkdir(parents=True)
    nib.save(nib.Nifti1Image(np.zeros((3, 3, 3, 30)), np.eye(4)), func / "sub-01_task-rest_bold.nii.gz")
    with pytest.raises(InputError, match="T1"):
        check_raw_bids({"bids_dir": str(root)})
    anat = root / "sub-01" / "anat"
    anat.mkdir()
    nib.save(nib.Nifti1Image(np.zeros((3, 3, 3)), np.eye(4)), anat / "sub-01_T1w.nii.gz")
    assert check_raw_bids({"bids_dir": str(root)})["bold_runs"] == 1


def test_cifti_and_gifti_guidance_require_matching_atlases(tmp_path):
    from nibabel.cifti2 import SeriesAxis, BrainModelAxis, ParcelsAxis

    series = SeriesAxis(0, 1.2, 30)
    parcels = ParcelsAxis(["a", "b"], [np.zeros((0, 3), dtype=int)] * 2, [{}, {}])
    p = tmp_path / "test.ptseries.nii"
    nib.save(nib.Cifti2Image(np.ones((30, 2)), header=nib.Cifti2Header.from_axes((series, parcels))), p)
    assert check_input(p)["needs_atlas"] is False
    assert check_input(p)["t_r"] == 1.2
    brain = BrainModelAxis.from_surface([0, 1], 2, name="CortexLeft")
    nib.save(nib.Cifti2Image(np.ones((30, 2)), header=nib.Cifti2Header.from_axes((series, brain))), p)
    assert check_input(p)["needs_atlas"] is True
    payload = {"source": str(p), "config": {"preprocessed": True, "data_space": "fsLR"}}
    with pytest.raises(InputError, match="分区图谱"):
        preflight(payload, stage="spatial")


def test_input_suggestions_infer_table_headers_and_companions(tmp_path, volume):
    from brainfc.workflow import input_suggestions

    p = tmp_path / "subject_rois_cc200.1D"
    np.savetxt(p, np.random.default_rng(2).normal(size=(30, 4)))
    hints = input_suggestions(p)
    assert hints["config"]["table_header"] is False
    assert hints["info"]["n_frames"] == 30
    p = tmp_path / "signals.tsv"
    p.write_text("a\tb\n" + "1\t2\n" * 30)
    assert input_suggestions(p)["config"]["table_header"] is True
    source = Path(volume["source"])
    confound = source.parent / "sub-01_desc-confounds_timeseries.tsv"
    confound.write_text("trans_x\n" + "0\n" * 40)
    mask = source.parent / "sub-01_space-MNI152NLin6Asym_desc-brain_mask.nii.gz"
    nib.save(nib.Nifti1Image(np.ones((4, 5, 6)), np.eye(4)), mask)
    hints = input_suggestions(source)
    assert hints["paths"]["confounds"] == str(confound)
    assert hints["paths"]["reference"] == str(mask)


def test_gifti_guidance_missing_atlas(tmp_path):
    g = tmp_path / "left.func.gii"
    nib.save(
        nib.gifti.GiftiImage(
            darrays=[
                nib.gifti.GiftiDataArray(
                    np.ones((6, 30), dtype=np.float32), intent="NIFTI_INTENT_TIME_SERIES"
                )
            ]
        ),
        g,
    )
    assert check_input(g)["n_frames"] == 30
    payload = {"source": str(g), "config": {"preprocessed": True, "data_space": "fsLR"}}
    with pytest.raises(InputError, match="分区图谱"):
        preflight(payload, stage="spatial")
