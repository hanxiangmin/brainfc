"""End-to-end contracts at the former BrainFC/Hyper-Brain boundary."""
from copy import deepcopy
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from brainfc import Config, extract_connectome
from brainfc.network import AnalysisConfig, ValidationError, load_connectome
from brainfc.web.app import create_app


def extraction(tmp_path):
    source = tmp_path / "signals.npy"
    np.save(source, np.random.default_rng(98).normal(size=(50, 6)))
    result = extract_connectome(source, config=Config(method="spearman"))
    for i, roi in enumerate(result.rois):
        roi["coordinates"] = [i * 4., 3., 2.]
    result.geometry = {"space": "test-space", "units": "mm", "orientation": "RAS+",
                       "brain": {"positions": [], "indices": []}, "parcels": {}}
    return result


def test_bridge_preserves_result_and_never_reestimates_connectivity(tmp_path, monkeypatch):
    import brainfc.network.connectivity as connectivity
    import hicbrain
    from hicbrain.types import BrainDataset as LegacyDataset
    from brainfc.network import BrainDataset

    original = extraction(tmp_path)
    before = deepcopy(original.to_dict())
    dataset = original.to_network()
    assert isinstance(dataset, hicbrain.BrainDataset)
    assert LegacyDataset is BrainDataset
    np.testing.assert_array_equal(original.to_hicbrain().data, original.connectivity)
    dataset.metadata["roi_metadata"][0]["name"] = "independent copy"
    assert original.rois[0]["name"] != "independent copy"

    def forbidden(*args, **kwargs):
        raise AssertionError("An extracted matrix must never be re-estimated")
    monkeypatch.setattr(connectivity, "compute_connectivity", forbidden)
    config = AnalysisConfig(graph_method="weighted", hypergraph_method="custom", custom_edges=[
        {"id": "H1", "members": [r["roi_id"] for r in original.rois[:3]]},
        {"id": "H2", "members": [r["roi_id"] for r in original.rois[:3]]},
    ])
    network = original.analyze_network(config)
    np.testing.assert_array_equal(network.connectivity, original.connectivity)
    assert network.roi_ids == [r["roi_id"] for r in original.rois]
    assert {e["id"] for e in network.hypergraph["edges"]} == {"H1", "H2"}
    assert network.metadata["sample_indices"] == original.sample_indices.tolist()
    assert original.to_dict() == before
    path = original.save(tmp_path / "saved", figures=False, report=False)
    np.testing.assert_array_equal(load_connectome(path).data, network.connectivity)


def test_bridge_rejects_corrupt_roi_order_and_json(tmp_path):
    result = extraction(tmp_path)
    result.rois[1]["roi_id"] = result.rois[0]["roi_id"]
    with pytest.raises(ValidationError, match="unique"):
        result.to_network()
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version":9}', encoding="utf-8")
    with pytest.raises(ValidationError, match="schema"):
        load_connectome(path)


def test_integrated_service_transfers_and_processes_without_reupload(tmp_path):
    result = extraction(tmp_path)
    workspace = tmp_path / "web"
    job_id = "a" * 32
    folder = workspace / "jobs" / job_id
    folder.mkdir(parents=True)
    (folder / "status.json").write_text(json.dumps({"id": job_id, "status": "complete", "kind": "extract"}))
    result.save(folder / "result", figures=False, report=False)
    with TestClient(create_app(workspace)) as client:
        assert client.get("/networks/").status_code == 200
        assert client.get("/networks/api/v1/health").status_code == 200
        assert client.post(f"/api/jobs/{job_id}/network-input", headers={"Origin": "http://evil.example"}).status_code == 403
        transferred = client.post(f"/api/jobs/{job_id}/network-input")
        assert transferred.status_code == 200, transferred.text
        entry = transferred.json()
        assert client.post(f"/api/jobs/{job_id}/network-input").json() == entry
        assert "brainfc_input" not in entry["file"]
        uploads = client.get("/networks/api/v1/uploads").json()["files"]
        assert "brainfc_input" not in uploads[0]
        # Wrong UI defaults cannot replace the transferred matrix semantics or ROI IDs.
        job = client.post("/networks/api/v1/jobs", json={"file_ids": [entry["file"]["id"]],
            "input": {"kind": "timeseries", "roi_ids": ["wrong"]},
            "analysis": {"graph_method": "weighted", "hypergraph_method": "knn", "k": 2}}).json()
        deadline = time.monotonic() + 45
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(.1)
            job = client.get(f"/networks/api/v1/jobs/{job['id']}").json()
        assert job["status"] == "completed", job
        data = client.get(f"/networks/api/v1/results/{job['results'][0]['id']}").json()
        np.testing.assert_array_equal(data["connectivity"], result.connectivity)
        assert data["roi_ids"] == [r["roi_id"] for r in result.rois]
        assert data["metadata"]["brainfc_geometry"] == result.geometry
        assert data["metadata"]["brainfc"]["config"]["method"] == "spearman"


def test_network_cli_accepts_saved_result_and_refuses_overwrite(tmp_path):
    from brainfc.cli import main
    original = extraction(tmp_path)
    source = original.save(tmp_path / "saved", figures=False, report=False)
    target = tmp_path / "network.json"
    assert main(["network", str(source), "--output", str(target)]) == 0
    result = json.loads(target.read_text(encoding="utf-8"))
    np.testing.assert_array_equal(result["connectivity"], original.connectivity)
    before = target.read_bytes()
    with pytest.raises(SystemExit) as exc:
        main(["network", str(source), "--output", str(target)])
    assert exc.value.code == 2
    assert target.read_bytes() == before
