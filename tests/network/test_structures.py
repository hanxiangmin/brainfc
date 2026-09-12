import json

import networkx as nx
import numpy as np
import pytest
import xgi

from brainfc.network.graph import analyze_graph, build_graph, to_payload as graph_payload
from brainfc.network.hypergraph import build_hypergraph, to_payload as hypergraph_payload
from brainfc.network.types import ValidationError


def test_known_weighted_path_efficiency_and_centrality():
    matrix = np.array([[0, 2, 0], [2, 0, 2], [0, 2, 0]], dtype=float)
    metrics = analyze_graph(build_graph(matrix, ["a", "b", "c"], method="weighted"))
    assert metrics["global"]["global_efficiency_positive"] == pytest.approx(5 / 3)
    assert metrics["global"]["mean_path_length_reachable_positive"] == pytest.approx(2 / 3)
    assert metrics["nodes"][1]["betweenness_positive"] == pytest.approx(1)
    assert metrics["global"]["mean_clustering_positive"] == 0


def test_triangle_clustering_matches_networkx_and_negative_edge_preserved():
    matrix = np.array([[0, 0.8, 0.4, 0], [0.8, 0, 0.6, 0], [0.4, 0.6, 0, -0.9], [0, 0, -0.9, 0]])
    graph = build_graph(matrix, ["a", "b", "c", "d"], method="weighted")
    payload = graph_payload(graph)
    assert payload["edges"][-1]["weight"] == -0.9
    assert payload["metrics"]["global"]["n_components"] == 1
    assert payload["metrics"]["global"]["n_positive_components"] == 2
    pos = nx.Graph([(u, v, a) for u, v, a in graph.edges(data=True) if a["weight"] > 0])
    assert payload["metrics"]["nodes"][0]["clustering_positive"] == pytest.approx(nx.clustering(pos, "a", weight="weight"))
    assert payload["metrics"]["nodes"][-1]["negative_strength"] == -0.9
    json.dumps(payload, allow_nan=False)


@pytest.mark.parametrize("method", ["weighted", "threshold", "density", "knn", "mst"])
def test_graph_permutation_invariance_including_cutoff_ties(method):
    matrix = np.array([[0, .8, .8, .1, 0], [.8, 0, -.8, .4, .2], [.8, -.8, 0, .4, .3], [.1, .4, .4, 0, .6], [0, .2, .3, .6, 0]])
    ids = ["a", "b", "c", "d", "e"]
    permutation = [4, 2, 0, 3, 1]
    original = graph_payload(build_graph(matrix, ids, method=method, density=.2, threshold=.4, k=1))
    reordered = graph_payload(build_graph(matrix[np.ix_(permutation, permutation)], [ids[i] for i in permutation], method=method, density=.2, threshold=.4, k=1))
    assert original == reordered


def test_density_and_knn_keep_all_cutoff_ties_mst_is_tree():
    matrix = np.ones((5, 5)) - np.eye(5)
    assert build_graph(matrix, method="density", density=.1).number_of_edges() == 10
    assert build_graph(matrix, method="knn", k=1).number_of_edges() == 10
    assert nx.is_tree(build_graph(matrix, method="mst"))
    assert build_graph(matrix, method="density", density=0).number_of_edges() == 0


def test_empty_graph_and_isolates_are_defined():
    assert analyze_graph(nx.Graph())["global"]["global_efficiency_positive"] == 0
    result = graph_payload(build_graph(np.zeros((4, 4))))
    assert result["metrics"]["global"]["n_components"] == 4
    assert result["metrics"]["global"]["mean_path_length_reachable_positive"] is None
    json.dumps(result, allow_nan=False)


def test_custom_edges_keep_distinct_identity_and_native_incidence():
    edges = [{"id": "first", "members": ["a", "b"], "weight": 0.4},
             {"id": "duplicate-members", "members": ["b", "a"], "weight": -0.3},
             {"id": 9, "members": ["b", "c"]}]
    h = build_hypergraph(np.zeros((4, 4)), ["a", "b", "c", "d"], method="custom", custom_edges=edges)
    result = hypergraph_payload(h)
    assert h.num_edges == 3
    assert set(h.edges) == {"first", "duplicate-members", 9}
    assert result["metrics"]["global"]["n_components"] == 2
    assert result["metrics"]["global"]["mean_pairwise_overlap"] == pytest.approx(4 / 3)
    assert result["metrics"]["nodes"][1]["hyperdegree"] == 3
    assert result["incidence"]["shape"] == [4, 3]
    json.dumps(result, allow_nan=False)


def test_hypergraph_template_identity_and_isolated_roi():
    result = hypergraph_payload(build_hypergraph(np.eye(3), ["a", "b", "c"], method="template", groups={"system-a": ["a", "b"]}))
    assert result["edges"][0]["id"] == "system-a"
    assert result["metrics"]["global"]["isolated_nodes"] == 1


@pytest.mark.parametrize("method,ks", [("knn", [1]), ("multiscale", [1, 2, 3])])
def test_profile_hypergraph_permutation_equivariance(method, ks):
    matrix = np.array([[1, .8, .8, .1], [.8, 1, .2, .4], [.8, .2, 1, .4], [.1, .4, .4, 1]])
    ids = ["a", "b", "c", "d"]
    order = [3, 1, 0, 2]
    first = hypergraph_payload(build_hypergraph(matrix, ids, method=method, ks=ks))
    second = hypergraph_payload(build_hypergraph(matrix[np.ix_(order, order)], [ids[i] for i in order], method=method, ks=ks))
    assert first == second


def test_profile_ties_and_diagonal_do_not_invent_edge_identity():
    matrix = np.ones((5, 5))
    first = build_hypergraph(matrix, method="multiscale", ks=[1, 2, 3])
    assert first.num_edges == 1
    assert len(first.edges.members()[0]) == 5
    np.fill_diagonal(matrix, 99)
    second = build_hypergraph(matrix, method="knn", ks=[1])
    assert list(first.edges) == list(second.edges)


def test_zero_profile_and_empty_hypergraph():
    result = hypergraph_payload(build_hypergraph(np.eye(4)))
    assert result["edges"] == []
    assert result["metrics"]["global"]["n_components"] == 4
    assert hypergraph_payload(xgi.Hypergraph())["metrics"]["global"]["n_components"] == 0


@pytest.mark.parametrize("edges", [
    [{"id": "x", "members": ["a", "unknown"]}],
    [{"id": "x", "members": ["a", "a"]}],
    [{"id": "x", "members": []}],
    [{"id": "x", "members": ["a"]}, {"id": "x", "members": ["b"]}],
    [{"id": "x", "members": ["a"], "weight": float("nan")}],
])
def test_bad_custom_edges_fail_instead_of_silent_xgi_mutation(edges):
    with pytest.raises(ValidationError):
        build_hypergraph(np.eye(2), ["a", "b"], method="custom", custom_edges=edges)


@pytest.mark.parametrize("matrix,ids", [([[0, 1], [0, 0]], None), (np.eye(2), ["same", "same"]), (np.ones((3, 2)), None), ([[1, np.nan], [np.nan, 1]], None)])
def test_invalid_matrices_and_roi_identifiers(matrix, ids):
    with pytest.raises(ValidationError):
        build_graph(matrix, ids)
    with pytest.raises(ValidationError):
        build_hypergraph(matrix, ids)


def test_structure_construction_does_not_modify_connectivity():
    matrix = np.array([[1, .8, .2], [.8, 1, .4], [.2, .4, 1]])
    original = matrix.copy()
    build_graph(matrix)
    build_hypergraph(matrix)
    np.testing.assert_array_equal(matrix, original)


def test_undefined_zero_profiles_remain_permutation_invariant():
    matrix = np.zeros((3, 3))
    first = hypergraph_payload(build_hypergraph(matrix, ["a", "b", "c"]))
    second = hypergraph_payload(build_hypergraph(matrix, ["c", "a", "b"]))
    assert first == second
