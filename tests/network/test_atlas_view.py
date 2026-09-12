"""Spatial identity, custom imports and view persistence; no external downloads."""

import copy
import hashlib
import json
import uuid

import nibabel as nib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from brainfc.network import AtlasRegistry, BrainDataset, ViewConfig, ValidationError, analyze
from brainfc.network.web.app import create_app


@pytest.fixture
def atlas_input(tmp_path):
    data = np.zeros((16, 16, 16), dtype=np.int16)
    data[2:6, 4:10, 3:11] = 2001
    data[10:14, 4:10, 3:11] = 2002
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    affine[:3, 3] = [-16, -16, -16]
    atlas = nib.Nifti1Image(data, affine)
    atlas.header.set_xyzt_units("mm")
    path = tmp_path / "parcellation.nii.gz"
    nib.save(atlas, path)
    reference = np.zeros(data.shape, np.float32)
    reference[1:15, 1:15, 1:15] = 1
    ref = nib.Nifti1Image(reference, affine)
    ref.header.set_xyzt_units("mm")
    refpath = tmp_path / "reference.nii.gz"
    nib.save(ref, refpath)
    table = pd.DataFrame(
        [
            {
                "label_value": 2001,
                "roi_id": "parcel-left",
                "abbreviation": "TEST.L",
                "name": "Synthetic left parcel",
                "hemisphere": "L",
            },
            {
                "label_value": 2002,
                "roi_id": "parcel-right",
                "abbreviation": "TEST.R",
                "name": "Synthetic right parcel",
                "hemisphere": "R",
            },
        ]
    )
    tablepath = tmp_path / "labels.tsv"
    table.to_csv(tablepath, sep="\t", index=False)
    return path, refpath, table, tablepath


def install(registry, fixture, **kwargs):
    path, ref, table, _ = fixture
    return registry.import_atlas(
        path,
        table,
        name="Synthetic spatial fixture",
        space="test-RAS-v1",
        reference=ref,
        space_confirmed=True,
        **kwargs,
    )


def test_anatomical_surfaces_and_nonconsecutive_labels(tmp_path, atlas_input):
    path, ref, _, _ = atlas_input
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (path, ref)]
    registry = AtlasRegistry(tmp_path / "registry")
    spec = install(registry, atlas_input)
    assert [r["label_value"] for r in spec["labels"]] == [2001, 2002]
    assert spec["labels"][0]["coordinates"][0] < 0 < spec["labels"][1]["coordinates"][0]
    geometry = json.loads(registry.asset(spec["id"], "geometry.json").read_text())
    assert geometry["space"] == "test-RAS-v1" and geometry["units"] == "mm"
    for row in spec["labels"]:
        mesh = geometry["parcels"][row["roi_id"]]
        vertices = np.asarray(mesh["positions"]).reshape(-1, 3)
        assert len(mesh["indices"]) > 0
        assert np.isfinite(vertices).all()
        # The representative coordinate must be inside the source parcel in world space.
        voxel = np.rint(
            nib.affines.apply_affine(np.linalg.inv(nib.load(path).affine), row["coordinates"])
        ).astype(int)
        assert nib.load(path).get_fdata()[tuple(voxel)] == row["label_value"]
        assert np.all(vertices.min(0) <= row["coordinates"])
        assert np.all(vertices.max(0) >= row["coordinates"])
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (path, ref)] == hashes
    assert install(registry, atlas_input)["sha256"] == spec["sha256"]
    assert registry.get(spec["id"]) == spec


@pytest.mark.parametrize(
    "problem", ["missing", "duplicate_id", "duplicate_short", "bad_number", "unknown_label", "hemisphere"]
)
def test_invalid_labels_rejected(tmp_path, atlas_input, problem):
    path, ref, table, _ = atlas_input
    if problem == "missing":
        table.loc[0, "name"] = ""
    elif problem == "duplicate_id":
        table.loc[0, "roi_id"] = table.loc[1, "roi_id"]
    elif problem == "duplicate_short":
        table.loc[0, "abbreviation"] = table.loc[1, "abbreviation"]
    elif problem == "bad_number":
        table = table.astype({"label_value": str})
        table.loc[0, "label_value"] = "oops"
    elif problem == "unknown_label":
        table.loc[0, "label_value"] = 1
    else:
        table.loc[0, "hemisphere"] = "unknown"
    with pytest.raises(ValidationError):
        AtlasRegistry(tmp_path / "registry").import_atlas(
            path, table, name="Test", space="test-v1", reference=ref, space_confirmed=True
        )


@pytest.mark.parametrize(
    "problem", ["fraction", "overflow", "nan", "empty", "four_d", "units", "qform", "overlap"]
)
def test_invalid_spatial_input(tmp_path, atlas_input, problem):
    path, ref, table, _ = atlas_input
    image = nib.load(path)
    data = image.get_fdata().copy()
    affine = image.affine.copy()
    if problem == "fraction":
        data[2, 4, 3] = 2001.5
    elif problem == "overflow":
        data[2, 4, 3] = 2**32 + 2001
    elif problem == "nan":
        data[2, 4, 3] = np.nan
    elif problem == "empty":
        data[:] = 0
    elif problem == "four_d":
        data = data[..., None]
    elif problem == "overlap":
        affine[0, 3] = 5000
    altered = nib.Nifti1Image(data, affine)
    if problem != "units":
        altered.header.set_xyzt_units("mm")
    if problem == "qform":
        moved = affine.copy()
        moved[0, 3] += 20
        altered.set_qform(moved, code=1)
        altered.set_sform(affine, code=1)
    nib.save(altered, path)
    with pytest.raises(ValidationError):
        AtlasRegistry(tmp_path / "registry").import_atlas(
            path, table, name="Test", space="test-v1", reference=ref, space_confirmed=True
        )


def test_mapping_preserves_identity_and_accepts_only_explicit_order(tmp_path, atlas_input):
    registry = AtlasRegistry(tmp_path / "registry")
    atlas = install(registry, atlas_input)
    result = analyze(
        BrainDataset(np.array([[1, -0.5], [-0.5, 1]]), "connectivity", roi_ids=["original-1", "original-2"])
    )
    original = copy.deepcopy(result.to_dict())
    for mapping in (None, ["parcel-left"], ["parcel-left", "parcel-left"], [2001, 2002], [{}, {}]):
        with pytest.raises(ValidationError):
            registry.bind(result, atlas["id"], mapping, confirmed=True)
    with pytest.raises(ValidationError):
        registry.bind(result, atlas["id"], ["parcel-left", "parcel-right"])
    bound = registry.bind(result, atlas["id"], ["parcel-right", "parcel-left"], confirmed=True)
    assert bound.labels == ["TEST.R", "TEST.L"]
    assert bound.coordinates[0, 0] > 0 > bound.coordinates[1, 0]
    assert bound.graph == original["graph"] and bound.hypergraph == original["hypergraph"]
    np.testing.assert_array_equal(bound.connectivity, result.connectivity)
    assert result.to_dict() == original
    with pytest.raises(ValidationError):
        registry.bind(bound, atlas["id"], ["parcel-left", "parcel-right"], confirmed=True)


@pytest.mark.parametrize("style", ["ballstick", "envelope", "parcels"])
@pytest.mark.parametrize("theme", ["midnight", "paper"])
def test_view_six_combinations_roundtrip(style, theme):
    view = ViewConfig(
        style=style,
        theme=theme,
        layer="both",
        selection={"kind": "node", "id": "left"},
        camera={"position": [0, 350, 40], "target": [0, 0, 0], "up": [0, 0, 1]},
    )
    assert ViewConfig.from_dict(json.loads(json.dumps(view.to_dict()))) == view


@pytest.mark.parametrize(
    "settings",
    [
        {"opacity": 2},
        {"opacity": float("nan")},
        {"opacity": True},
        {"labels": "yes"},
        {"theme": "wrong"},
        {"style": "wrong"},
        {"camera": {"position": [0, 2]}},
        {"camera": {"position": [0, 2, float("inf")]}},
        {"camera": {"up": [0, 0, 0]}},
        {"camera": {"position": [1, 2, 3], "target": [1, 2, 3]}},
        {"selection": {"kind": "anchor", "id": "123"}},
    ],
)
def test_view_validation(settings):
    with pytest.raises(ValidationError):
        ViewConfig(**settings)


def test_http_custom_import_bind_and_persist(tmp_path, atlas_input):
    path, ref, _, tablepath = atlas_input
    app = create_app(tmp_path / "web")
    with TestClient(app) as client:
        files = {
            "parcellation": (path.name, path.read_bytes()),
            "reference": (ref.name, ref.read_bytes()),
            "labels": (tablepath.name, tablepath.read_bytes()),
        }
        bad = client.post("/api/v1/atlases", files=files, data={"metadata": "{}"})
        assert bad.status_code == 422
        response = client.post(
            "/api/v1/atlases",
            files=files,
            data={
                "metadata": json.dumps(
                    {"name": "Synthetic fixture", "space": "test-RAS-v1", "space_confirmed": True}
                )
            },
        )
        assert response.status_code == 200, response.text
        atlas = response.json()
        assert len(client.get("/api/v1/atlases").json()["atlases"]) == 6
        assert client.get(f"/api/v1/atlases/{atlas['id']}/assets/geometry.json").json()["parcels"]
        assert client.get(f"/api/v1/atlases/{atlas['id']}/assets/state.sqlite").status_code == 422
        result_id = uuid.uuid4().hex
        result = analyze(BrainDataset(np.array([[1, -0.5], [-0.5, 1]]), "connectivity"))
        app.state.store.put("results", {"id": result_id})
        app.state.store.result_path(result_id).write_text(json.dumps(result.to_dict()), encoding="utf-8")
        original = app.state.store.result_path(result_id).read_bytes()
        binding = {
            "atlas_id": atlas["id"],
            "ordered_roi_ids": ["parcel-left", "parcel-right"],
            "confirmed": True,
        }
        bound = client.post(f"/api/v1/results/{result_id}/atlas", json=binding)
        assert bound.status_code == 200, bound.text
        assert client.get(f"/api/v1/results/{result_id}/mapped").json() == bound.json()
        assert (
            client.post(
                f"/api/v1/results/{result_id}/atlas",
                json={**binding, "ordered_roi_ids": ["parcel-right", "parcel-left"]},
            ).status_code
            == 422
        )
        state = ViewConfig(
            style="envelope", theme="paper", layer="both", selection={"kind": "node", "id": result.roi_ids[0]}
        ).to_dict()
        assert client.put(f"/api/v1/results/{result_id}/view", json=state).status_code == 200
        assert client.get(f"/api/v1/results/{result_id}/view").json() == state
        assert app.state.store.result_path(result_id).read_bytes() == original


def test_standard_space_rejects_reversed_hemisphere_names(tmp_path, atlas_input):
    path, ref, table, _ = atlas_input
    table["hemisphere"] = ["R", "L"]
    with pytest.raises(ValidationError, match="[Hh]emisphere"):
        AtlasRegistry(tmp_path / "registry").import_atlas(
            path,
            table,
            name="Swapped hemispheres",
            space="MNIColin27",
            reference=ref,
            space_confirmed=True,
        )


def test_stable_edge_ids_after_roi_permutation():
    matrix = np.array([[1, 0.3, -0.4], [0.3, 1, 0.6], [-0.4, 0.6, 1]])
    one = analyze(BrainDataset(matrix, "connectivity", roi_ids=["a", "b", "c"]))
    order = [2, 0, 1]
    two = analyze(BrainDataset(matrix[np.ix_(order, order)], "connectivity", roi_ids=["c", "a", "b"]))
    assert one.graph["edges"] == two.graph["edges"]


def test_legacy_skeleton_migrates_without_changing_selection_or_camera():
    old = {"style": "skeleton", "selection": {"kind": "hyperedge", "id": "h1"},
           "camera": {"position": [0, 350, 40], "target": [0, 0, 0]}}
    restored = ViewConfig.from_dict(old)
    assert restored.style == "ballstick"
    assert restored.selection == old["selection"]
    assert restored.camera == old["camera"]
    assert old["style"] == "skeleton"
