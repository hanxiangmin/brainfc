from __future__ import annotations

import io
import json
import time
import uuid
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

from brainfc.network import AnalysisConfig, BrainDataset, ValidationError, analyze, load_data
from brainfc.network.export import export_result
from brainfc.network.web.app import create_app
from brainfc.network.web.storage import Store


def sample():
    return np.random.default_rng(7).normal(size=(100, 8))


def wait_for_job(client, job_id):
    limit = time.monotonic() + 60
    while time.monotonic() < limit:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] not in {"queued", "running"}:
            return job
        time.sleep(.2)
    pytest.fail("Local worker did not finish within 60 seconds")


def test_analysis_preserves_data_and_roi_identity():
    data = sample()
    before = data.copy()
    ids = [f"region-{i}" for i in range(data.shape[1])]
    config = AnalysisConfig(hypergraph_method="multiscale", hypergraph_ks=[2, 3])
    result = analyze(BrainDataset(data, "timeseries", roi_ids=ids), config)
    np.testing.assert_array_equal(data, before)
    permutation = np.random.default_rng(22).permutation(len(ids))
    reordered = analyze(BrainDataset(data[:, permutation], "timeseries",
        roi_ids=[ids[i] for i in permutation]), config)
    def compare_nested(a, b):
        if isinstance(a, dict):
            assert a.keys() == b.keys()
            for key in a:
                compare_nested(a[key], b[key])
        elif isinstance(a, list):
            assert len(a) == len(b)
            for x, y in zip(a, b):
                compare_nested(x, y)
        elif isinstance(a, float):
            assert a == pytest.approx(b, abs=1e-12)
        else:
            assert a == b
    compare_nested(result.graph, reordered.graph)
    compare_nested(result.hypergraph, reordered.hypergraph)
    assert result.layouts == reordered.layouts
    assert result.layouts["graph_2d"]["coordinate_space"] == "display"
    assert {node["id"] for node in result.layouts["graph_2d"]["nodes"]} == set(ids)
    np.testing.assert_allclose(reordered.connectivity, result.connectivity[np.ix_(permutation, permutation)])


def test_direct_api_rejects_complex():
    with pytest.raises(ValidationError):
        BrainDataset(np.array([[1+2j, 1], [1, 2]]), "connectivity")


def test_report_bundle_contains_real_artifacts(tmp_path):
    result = analyze(BrainDataset(sample(), "timeseries", metadata={"source_name": "<script>alert(1)</script>"}))
    destination = export_result(result, tmp_path / "report.zip")
    with zipfile.ZipFile(destination) as archive:
        names = set(archive.namelist())
        assert {"result.json", "report.html", "figure.pdf", "figure.svg", "figure.png", "hyperedge_members.csv", "layout_coordinates.csv", "network.graphml"} <= names
        payload = json.loads(archive.read("result.json"))
        assert len(payload["connectivity"]) == 8
        report = archive.read("report.html").decode()
        assert "<script>alert(1)</script>" not in report
        assert "&lt;script&gt;" in report
        assert "data:image/png;base64," in report
        assert archive.read("figure.pdf").startswith(b"%PDF")
        assert b"hyperedge_id_type" in archive.read("hyperedge_members.csv")


def test_http_upload_and_python_results_match(tmp_path):
    source = tmp_path / "input.npy"
    np.save(source, sample())
    original_bytes = source.read_bytes()
    config = AnalysisConfig(k=3)
    direct = analyze(load_data(source, kind="timeseries"), config)
    with TestClient(create_app(tmp_path / "workspace")) as client:
        assert client.get("/api/v1/health").json()["local_only"]
        reference = client.get("/docs")
        assert reference.status_code == 200
        assert '<script src="http' not in reference.text
        assert "/openapi.json" in reference.text
        assert "/api/v1/jobs" in client.get("/openapi.json").json()["paths"]
        uploaded = client.post("/api/v1/uploads", files=[("files", ("input.npy", original_bytes))])
        assert uploaded.status_code == 200, uploaded.text
        record = uploaded.json()["files"][0]
        assert "source" not in record
        response = client.post("/api/v1/jobs", json={"file_ids": [record["id"]],
            "input": {"kind": "timeseries"}, "analysis": config.to_dict()})
        assert response.status_code == 200, response.text
        completed = wait_for_job(client, response.json()["id"])
        assert completed["status"] == "completed", completed
        payload = client.get("/api/v1/results/" + completed["results"][0]["id"]).json()
        np.testing.assert_allclose(payload["connectivity"], direct.connectivity)
        assert payload["graph"] == direct.to_dict()["graph"]
        assert payload["hypergraph"] == direct.to_dict()["hypergraph"]
        assert payload["layouts"] == direct.to_dict()["layouts"]
        export = client.get("/api/v1/results/" + completed["results"][0]["id"] + "/export?format=csv")
        assert export.status_code == 200
        assert zipfile.is_zipfile(io.BytesIO(export.content))
        assert client.post("/api/v1/jobs", json={"file_ids": [record["id"]],
            "input": {"path": str(source)}}).status_code == 422
        assert client.post("/api/v1/jobs", headers={"Origin": "https://attacker.invalid"}, json={}).status_code == 403
        assert client.get("/api/v1/results/not-an-id").status_code == 404
    assert source.read_bytes() == original_bytes


def test_cancel_restart_and_retry(tmp_path):
    workspace = tmp_path / "workspace"
    store = Store(workspace)
    stale_id = uuid.uuid4().hex
    store.put("jobs", {"id": stale_id, "status": "running", "progress": 10, "results": [], "errors": []})
    array = io.BytesIO()
    np.save(array, sample())
    with TestClient(create_app(workspace)) as client:
        assert client.get(f"/api/v1/jobs/{stale_id}").json()["status"] == "interrupted"
        record = client.post("/api/v1/uploads", files=[("files", ("test.npy", array.getvalue()))]).json()["files"][0]
        job = client.post("/api/v1/jobs", json={"file_ids": [record["id"]], "input": {"kind": "timeseries"}}).json()
        cancelled = client.post(f"/api/v1/jobs/{job['id']}/cancel").json()
        assert cancelled["status"] == "cancelled"
        retried = client.post(f"/api/v1/jobs/{job['id']}/retry").json()
        assert retried["id"] != job["id"]
        assert wait_for_job(client, retried["id"])["status"] == "completed"


def test_bad_upload_and_config_are_reported(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.post("/api/v1/uploads", files=[("files", ("script.py", b"print('hello')"))])
        assert response.status_code == 422
        assert list((tmp_path / "uploads").iterdir()) == []
        assert client.post("/api/v1/jobs", json={"file_ids": []}).status_code == 422
        assert client.post("/api/v1/jobs", json={"file_ids": [{}]}).status_code == 422


def test_batch_keeps_success_when_another_file_fails(tmp_path):
    valid, invalid = io.BytesIO(), io.BytesIO()
    np.save(valid, sample())
    np.save(invalid, np.ones((30, 8)))  # Constant ROI time series must fail analysis.
    with TestClient(create_app(tmp_path)) as client:
        upload = client.post("/api/v1/uploads", files=[
            ("files", ("valid.npy", valid.getvalue())),
            ("files", ("constant.npy", invalid.getvalue())),
        ]).json()
        ids = [row["id"] for row in upload["files"]]
        for bad_config in ({"threshold": []}, {"density": {}}, {"hypergraph_ks": "5"}):
            assert client.post("/api/v1/jobs", json={"file_ids": ids, "analysis": bad_config}).status_code == 422
        submitted = client.post("/api/v1/jobs", json={"file_ids": ids, "input": {"kind": "timeseries"}})
        job = wait_for_job(client, submitted.json()["id"])
        assert job["status"] == "completed"
        assert len(job["results"]) == len(job["errors"]) == 1
        assert job["errors"][0]["name"] == "constant.npy"
        assert job["results"][0]["name"] == "valid.npy"
        assert job["progress"] == 100
