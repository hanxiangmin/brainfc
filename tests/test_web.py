from fastapi.testclient import TestClient
import hashlib
from importlib.resources import files
import time

import pytest
from brainfc.web.app import create_app


def test_local_app_and_request_boundaries(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert "root" in client.get("/").text
        assert client.post("/api/jobs", json={}).status_code == 422
        assert (
            client.post(
                "/api/inspect", json={"path": "missing"}, headers={"Origin": "https://example.org"}
            ).status_code
            == 403
        )
        assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400
        assert client.get("/api/jobs/not-a-job").status_code == 404


def test_upload_bytes_and_no_overwrite(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        body = {"session": "1" * 32}
        r = client.post("/api/upload", data=body, files={"file": ("roi.tsv", b"a\tb\n1\t2\n")})
        assert r.status_code == 200
        assert client.post("/api/upload", data=body, files={"file": ("roi.tsv", b"other")}).status_code == 409


@pytest.mark.parametrize("query,kind,n_rois,n_samples", [
    ("", "rest01", 100, 145), ("?kind=synthetic", "synthetic", 12, 157),
])
def test_web_demo_identity_and_actual_inputs(tmp_path, query, kind, n_rois, n_samples):
    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/demo?kind=unknown").status_code == 422
        job = client.post("/api/demo" + query).json()
        assert job["example_kind"] == kind
        deadline = time.monotonic() + 90
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(.1)
            job = client.get(f"/api/jobs/{job['id']}").json()
        assert job["status"] == "complete", job
        result = client.get(f"/api/jobs/{job['id']}/files/result.json").json()
        assert result["qc"]["n_rois"] == n_rois
        assert len(result["sample_indices"]) == n_samples
        assert result["provenance"]["synthetic"] == (kind == "synthetic")
        if kind == "rest01":
            reference = files("brainfc").joinpath("data/rest01")
            signal = reference.joinpath("timeseries.tsv").read_bytes()
            assert result["provenance"]["inputs"]["source"]["sha256"] == hashlib.sha256(signal).hexdigest()
            assert result["provenance"]["example"]["sample_id"] == "rest01"
            assert all(w in result["qc"]["warnings"] for w in result["provenance"]["example"]["limitations"])
