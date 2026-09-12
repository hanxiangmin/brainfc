"""Behavioral contracts for the documented install/HTTP surface."""

from dataclasses import fields
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from brainfc import Config, __version__, extract_connectome
from brainfc.web.app import create_app
from brainfc.workflow import preflight


def test_mgz_preflight_does_not_assume_a_nifti_header(tmp_path):
    import nibabel as nib
    from brainfc.workflow import check_input

    path = tmp_path / "run.mgz"
    data = np.random.default_rng(9).normal(size=(4, 4, 4, 30)).astype(np.float32)
    nib.save(nib.MGHImage(data, np.eye(4)), path)
    info = check_input(path)
    assert info["format"] == "volume"
    assert info["n_frames"] == 30
    assert info["t_r"] is None


def test_preflight_uses_an_explicit_filename_space_when_config_is_unset(tmp_path):
    from brainfc.demo import create_demo

    spec = create_demo(tmp_path / "input")
    source = Path(spec["source"])
    renamed = source.with_name("sub-01_space-synthetic-demo_desc-preproc_bold.nii.gz")
    source.rename(renamed)
    spec["source"] = str(renamed)
    spec["config"].pop("data_space")
    assert preflight(spec)["validated"] is True


def test_runtime_cli_provenance_and_openapi_use_the_package_version(tmp_path):
    source = tmp_path / "signals.npy"
    np.save(source, np.random.default_rng(4).normal(size=(40, 3)))
    result = extract_connectome(source)
    assert result.provenance["version"] == __version__
    output = subprocess.check_output([sys.executable, "-m", "brainfc", "--version"], text=True)
    assert output.strip() == f"brainfc {__version__}"
    with TestClient(create_app(tmp_path / "web")) as client:
        assert client.get("/api/health").json()["version"] == __version__
        schema = client.get("/openapi.json").json()
        assert schema["info"]["version"] == __version__
        properties = schema["components"]["schemas"]["ConfigRequest"]["properties"]
        assert set(properties) == {f.name for f in fields(Config)}
        for field in fields(Config):
            # FastAPI omits explicit null defaults from JSON Schema.
            assert properties[field.name].get("default") == field.default
            assert field.name not in schema["components"]["schemas"]["ConfigRequest"].get("required", [])
            assert properties[field.name]["description"]


@pytest.mark.parametrize(
    "route,body",
    [
        ("/api/dicom/plan", {"source": "missing"}),
        ("/api/preprocess/plan", {"bids_dir": "missing"}),
        ("/api/jobs", {"source": "missing", "typo": True}),
        ("/api/preflight", {"source": "missing", "stage": "unknown"}),
        ("/api/jobs", {"source": "missing", "config": {"detrned": False}}),
    ],
)
def test_request_shape_errors_are_422_not_internal_errors(tmp_path, route, body):
    with TestClient(create_app(tmp_path)) as client:
        assert client.post(route, json=body).status_code == 422
        assert client.get("/api/jobs").json() == []


def test_suggestions_do_not_override_inference_with_model_defaults(tmp_path):
    path = tmp_path / "signals.1D"
    np.savetxt(path, np.random.default_rng(3).normal(size=(50, 3)))
    with TestClient(create_app(tmp_path / "web")) as client:
        response = client.post(
            "/api/input-suggestions", json={"source": str(path), "overrides": {"transpose": False}}
        )
        assert response.status_code == 200
        assert response.json()["info"]["n_frames"] == 50
        assert response.json()["config"]["table_header"] is False


def test_documented_numeric_artifacts_and_rejected_view_settings(tmp_path):
    signals = np.random.default_rng(32).normal(size=(50, 3))
    source = tmp_path / "signals.npy"
    np.save(source, signals)
    with TestClient(create_app(tmp_path / "web")) as client:
        response = client.post(
            "/api/jobs", json={"source": str(source), "config": {"detrend": False, "standardize": False}}
        )
        assert response.status_code == 200
        job = response.json()
        deadline = time.monotonic() + 30
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.1)
            job = client.get("/api/jobs/" + job["id"]).json()
        assert job["status"] == "complete", job
        for name in ("fisher_z.npy", "timeseries.npy", "manifest.json"):
            artifact = client.get(f"/api/jobs/{job['id']}/files/{name}")
            assert artifact.status_code == 200, name
        result = client.get(f"/api/jobs/{job['id']}/files/result.json").json()
        np.testing.assert_allclose(result["connectivity"], np.corrcoef(signals, rowvar=False), atol=1e-12)
        assert client.get(f"/api/jobs/{job['id']}/views?threshold=2").status_code == 422
        assert client.get(f"/api/jobs/{job['id']}/files/unknown.txt").status_code == 404


def test_preflight_rejects_unknown_stage(tmp_path):
    with pytest.raises(ValueError, match="stage"):
        preflight({"source": str(tmp_path / "missing")}, stage="misspelled")


def test_inline_python_example_runs(tmp_path):
    # Run the documented code itself; keep illustrative real-data snippets unexecuted.
    document = Path(__file__).resolve().parents[1] / "docs/python-api.md"
    text = document.read_text(encoding="utf-8")
    section = text.split("## 1.", 1)[1].split("## 2.", 1)[0]
    code = section.split("```python\n", 1)[1].split("```", 1)[0]
    exec(compile(code, str(document), "exec"), {})
