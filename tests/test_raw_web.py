import json
from fastapi.testclient import TestClient

from brainfc.web.app import create_app
from test_raw_preprocessing import inputs


def test_native_api_blocks_unknown_timing_and_has_no_license_requirement(tmp_path):
    bold, t1 = inputs(tmp_path)
    with TestClient(create_app(tmp_path / "web")) as client:
        payload = {"bold": str(bold), "t1w": str(t1)}
        plan = client.post("/api/python/inspect", json=payload)
        assert plan.status_code == 200 and not plan.json()["ready"]
        assert client.post("/api/python/preprocess", json=payload).status_code == 422
        payload["config"] = {"slice_timing": "skip"}
        assert client.post("/api/python/inspect", json=payload).json()["ready"]
        payload["config"]["invented"] = 1
        assert client.post("/api/python/inspect", json=payload).status_code == 422
        spec = json.dumps(client.get("/openapi.json").json()["components"]["schemas"]["PythonPreprocessRequest"])
        assert "license" not in spec and "bold" in spec


def test_native_qc_route_only_exposes_allowlisted_artifacts(tmp_path):
    job = tmp_path / "jobs" / ("a"*32)
    (job / "preprocessed").mkdir(parents=True)
    (job / "preprocessed/qc.html").write_text("QC fixture")
    (job / "preprocessed/source.nii.gz").write_bytes(b"private")
    with TestClient(create_app(tmp_path)) as client:
        base = f"/api/jobs/{'a'*32}/preprocessing/"
        assert client.get(base + "qc.html").text == "QC fixture"
        assert client.get(base + "source.nii.gz").status_code == 404
        assert client.get(base + "..%2Fsource.nii.gz").status_code == 404
