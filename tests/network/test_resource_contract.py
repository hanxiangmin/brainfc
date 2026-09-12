"""Independent acceptance checks for bounded, local scientific computation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import h5py
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from brainfc.network import AnalysisConfig, BrainDataset, ValidationError, analyze
from brainfc.network.connectivity import compute_connectivity
from brainfc.network.graph import analyze_graph, build_graph
from brainfc.network.hypergraph import MAX_EDGES, MAX_MEMBERSHIPS, build_hypergraph
from brainfc.network.io import inspect_file, validate_dataset
from brainfc.network.statistics import compare_groups


def test_npy_dimension_header_rejected_before_loading_array_bytes(tmp_path):
    """An oversized shape can be rejected from a tiny header-only file."""
    path = tmp_path / "oversized.npy"
    with path.open("wb") as stream:
        np.lib.format.write_array_header_1_0(stream, {
            "descr": "<f8", "fortran_order": False, "shape": (5001, 1000),
        })
    assert path.stat().st_size < 1024
    with pytest.raises(ValidationError, match="5000000"):
        inspect_file(path)


def test_numeric_cell_and_roi_limits_require_no_large_allocation():
    # Broadcast views have one stored scalar; rejection must precede computation.
    oversized_series = np.broadcast_to(np.float64(1), (5001, 1000))
    with pytest.raises(ValidationError, match="5000000"):
        compute_connectivity(oversized_series)
    with pytest.raises(ValidationError, match="Resource limit"):
        validate_dataset(BrainDataset(oversized_series, "timeseries"))
    oversized_matrix = np.broadcast_to(np.float64(0), (1001, 1001))
    with pytest.raises(ValidationError, match="1000"):
        build_graph(oversized_matrix)
    with pytest.raises(ValidationError, match="1000"):
        build_hypergraph(oversized_matrix)


def test_native_hyperedge_count_and_total_membership_are_bounded():
    edges = [{"id": f"edge-{i}", "members": ["a"]} for i in range(MAX_EDGES + 1)]
    with pytest.raises(ValidationError, match="10000 edges"):
        build_hypergraph(np.eye(2), ["a", "b"], method="custom", custom_edges=edges)
    ids = [f"r{i}" for i in range(1000)]
    overlapping = [{"id": f"set-{i}", "members": ids} for i in range(MAX_MEMBERSHIPS // len(ids) + 1)]
    with pytest.raises(ValidationError, match="250000 memberships"):
        build_hypergraph(np.zeros((1000, 1000)), ids, method="custom", custom_edges=overlapping)
    with pytest.raises(ValidationError, match="1 to 10"):
        build_hypergraph(np.eye(3), method="multiscale", ks=list(range(1, 12)))


def test_large_graph_marks_uncomputed_betweenness_as_missing():
    result = analyze_graph(nx.empty_graph(301))
    assert result["global"]["betweenness_computed"] is False
    assert all(row["betweenness_positive"] is None for row in result["nodes"])
    assert result["global"]["global_efficiency_positive"] == 0
    assert "300 nodes" in result["definitions"]["betweenness"]


def test_mat_external_storage_is_rejected_before_opening_external_data(tmp_path):
    path = tmp_path / "external.mat"
    with h5py.File(path, "w") as file:
        file.create_dataset("signals", shape=(8, 2), dtype="f8", external=[("not-provided.bin", 0, 128)])
    assert not (tmp_path / "not-provided.bin").exists()
    with pytest.raises(ValidationError, match="external storage"):
        inspect_file(path)


def test_repeated_participant_after_id_normalization_cannot_be_hidden_by_missingness():
    frame = pd.DataFrame({
        "participant": ["p1", " p1 ", "p3", "p4", "p5", "p6"],
        "group": ["A", "A", "A", "B", "B", "B"],
        "feature": [np.nan, 2, 3, 4, 5, 6],
    })
    with pytest.raises(ValidationError, match="Repeated subject"):
        compare_groups(frame, "group", "participant", ["feature"])


def test_coordinate_arrays_and_unknown_space_are_preserved_without_inventing_anatomy():
    coordinates = np.array([[-42, -8, 20], [42, -8, 20], [0, 20, 36]], dtype=float)
    dataset = BrainDataset(np.array([[1, .6, -.3], [.6, 1, .2], [-.3, .2, 1]]),
                           "connectivity", coordinates=coordinates.copy())
    result = analyze(dataset, AnalysisConfig(graph_method="weighted"))
    np.testing.assert_array_equal(result.coordinates, coordinates)
    assert result.layouts["graph_2d"]["coordinate_space"] == "display"
    assert all(abs(node["x"]) <= 1 and abs(node["y"]) <= 1 for node in result.layouts["graph_2d"]["nodes"])
    assert "coordinate_space" not in result.metadata
    assert any("Coordinate space is missing" in warning for warning in result.warnings)
    assert {edge["weight"] for edge in result.graph["edges"]} == {.6, -.3, .2}
    assert result.graph["metrics"]["global"]["negative_edges"] == 1


def test_fresh_process_analysis_and_packaged_template_need_no_network(tmp_path):
    script = r'''
import json, socket
network_attempts = []
def blocked(*args, **kwargs):
    network_attempts.append(repr(args))
    raise RuntimeError("Network disabled during offline acceptance")
socket.socket.connect = blocked
socket.create_connection = blocked
import numpy as np
from brainfc.network import AnalysisConfig, BrainDataset, analyze
from nilearn.datasets import load_mni152_template
rng = np.random.default_rng(17)
latent = rng.normal(size=(90, 1))
timeseries = latent @ np.array([[1., .9, -.8, .7]]) + rng.normal(scale=.4, size=(90, 4))
result = analyze(BrainDataset(timeseries, "timeseries"),
                 AnalysisConfig(connectivity_method="partial", graph_method="weighted", k=2))
template = load_mni152_template(resolution=2)
assert template.shape[0] > 10
assert len(result.graph["edges"]) > 0
assert len(result.hypergraph["edges"]) > 0
assert network_attempts == []
print(json.dumps({"offline": True, "template_shape": template.shape,
                  "graph_edges": len(result.graph["edges"]), "hyperedges": len(result.hypergraph["edges"])}))
'''
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    process = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=environment,
                             capture_output=True, text=True, timeout=60)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout.strip())["offline"] is True


def _multipart(file_count):
    boundary = "hicbrain-resource-check"
    data = b"1,2\n3,4\n" * 16
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="sample{i}.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode()
        + data + b"\r\n" for i in range(file_count)
    ]
    return b"".join(parts) + f"--{boundary}--\r\n".encode(), boundary


def test_chunked_multipart_rejected_while_receiving_before_workspace_copy(tmp_path, monkeypatch):
    import anyio
    import httpx
    import brainfc.network.web.app as web

    monkeypatch.setattr(web, "MAX_FILE_BYTES", 256)
    app = web.create_app(tmp_path)
    body, boundary = _multipart(5)
    assert len(body) > 1024
    received_chunks = []

    async def scenario():
        async def stream():
            for start in range(0, len(body), 100):
                received_chunks.append(start)
                yield body[start:start + 100]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            response = await client.post("/api/v1/uploads", content=stream(),
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            assert "content-length" not in response.request.headers
            assert response.status_code == 413, response.text
            assert (await client.get("/api/v1/uploads")).json()["files"] == []

    anyio.run(scenario)
    assert len(received_chunks) < len(range(0, len(body), 100))
    assert list((tmp_path / "uploads").iterdir()) == []


def test_chunked_multipart_within_limit_remains_supported(tmp_path, monkeypatch):
    import anyio
    import httpx
    import brainfc.network.web.app as web

    monkeypatch.setattr(web, "MAX_FILE_BYTES", 256)
    app = web.create_app(tmp_path)
    body, boundary = _multipart(2)
    assert len(body) < 1024

    async def scenario():
        async def stream():
            for start in range(0, len(body), 73):
                yield body[start:start + 73]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            response = await client.post("/api/v1/uploads", content=stream(),
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            assert "content-length" not in response.request.headers
            assert response.status_code == 200, response.text
            assert len(response.json()["files"]) == 2

    anyio.run(scenario)


def test_chunked_json_obeys_same_request_limit(tmp_path, monkeypatch):
    import anyio
    import httpx
    import brainfc.network.web.app as web

    monkeypatch.setattr(web, "MAX_FILE_BYTES", 256)
    app = web.create_app(tmp_path)
    body = json.dumps({"rows": [], "padding": "x" * 1500}).encode()

    async def scenario():
        async def stream():
            for start in range(0, len(body), 100):
                yield body[start:start + 100]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            response = await client.post("/api/v1/statistics", content=stream(),
                                         headers={"Content-Type": "application/json"})
            assert "content-length" not in response.request.headers
            assert response.status_code == 413, response.text

    anyio.run(scenario)
