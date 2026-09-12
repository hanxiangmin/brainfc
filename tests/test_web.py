from fastapi.testclient import TestClient
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
