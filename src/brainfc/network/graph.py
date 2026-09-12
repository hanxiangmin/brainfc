"""Signed undirected ROI graphs and explicitly positive-weight metrics."""
from __future__ import annotations

import math

import networkx as nx
import numpy as np
from scipy.sparse.csgraph import shortest_path

from .types import ValidationError


def _validate_matrix(matrix, roi_ids=None) -> tuple[np.ndarray, list[str]]:
    if np.iscomplexobj(matrix):
        raise ValidationError("Connectivity must be real-valued.")
    try:
        data = np.asarray(matrix, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Connectivity must be a numeric matrix.") from exc
    if data.ndim != 2 or data.shape[0] != data.shape[1] or not 1 <= len(data) <= 1000:
        raise ValidationError("Connectivity must be square with 1 to 1000 ROIs.")
    if not np.isfinite(data).all():
        raise ValidationError("Connectivity must contain only finite values.")
    if not np.allclose(data, data.T, rtol=1e-7, atol=1e-8):
        raise ValidationError("Connectivity must be symmetric.")
    if isinstance(roi_ids, (str, bytes)):
        raise ValidationError("ROI IDs must be supplied as a sequence, not one string.")
    ids = [f"ROI_{i + 1:03d}" for i in range(len(data))] if roi_ids is None else [str(v) for v in roi_ids]
    if len(ids) != len(data) or len(set(ids)) != len(ids) or any(not value.strip() for value in ids):
        raise ValidationError("ROI IDs must be nonempty, unique, and match the matrix size.")
    data = data / 2 + data.T / 2
    np.fill_diagonal(data, 0.0)
    return data, ids


def _positive_integer(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValidationError(f"{name} must be a positive integer.")
    return int(value)


def _at_least(values: np.ndarray, cutoff: float) -> np.ndarray:
    """Include numerical cutoff ties without favoring matrix column order."""
    return (values >= cutoff) | np.isclose(values, cutoff, rtol=1e-10, atol=1e-12)


def build_graph(matrix, roi_ids=None, method: str = "density", threshold: float = 0.2,
                density: float = 0.1, k: int = 5) -> nx.Graph:
    """Build an undirected graph, retaining edge signs and discarding self-loops.

    Selection ranks absolute connection strength. Density and kNN include all
    cutoff ties, so actual density/degree can exceed the request. kNN uses the
    union of directed neighbor choices. MST maximizes absolute strength and
    retains the original signed weights; zero weights denote absent edges, so
    disconnected inputs yield a forest. MST ties use canonical ROI-ID pairs.
    """
    data, ids = _validate_matrix(matrix, roi_ids)
    if method not in {"weighted", "threshold", "density", "knn", "mst"}:
        raise ValidationError("Unknown graph construction method.")
    n = len(data)
    strengths = np.abs(data)
    nonzero = strengths > 0
    selected = np.zeros((n, n), dtype=bool)
    metadata = {"method": method, "selection_weights": "absolute",
                "self_loops": "excluded", "zero_weights": "absent",
                "tie_policy": "include all cutoff ties (rtol=1e-10, atol=1e-12)"}
    if method == "weighted":
        selected = nonzero
    elif method == "threshold":
        if isinstance(threshold, bool) or not isinstance(threshold, (float, int, np.number)) or not np.isfinite(threshold) or threshold < 0:
            raise ValidationError("threshold must be a finite nonnegative number.")
        selected = nonzero & _at_least(strengths, float(threshold))
        metadata["threshold"] = float(threshold)
    elif method == "density":
        if isinstance(density, bool) or not isinstance(density, (float, int, np.number)) or not np.isfinite(density) or not 0 <= density <= 1:
            raise ValidationError("density must be between 0 and 1.")
        target = math.ceil(float(density) * n * (n - 1) / 2)
        upper = strengths[np.triu_indices(n, 1)]
        eligible = upper[upper > 0]
        if target and len(eligible):
            count = min(target, len(eligible))
            cutoff = np.partition(eligible, len(eligible) - count)[len(eligible) - count]
            selected = nonzero & _at_least(strengths, float(cutoff))
        metadata.update(requested_density=float(density), requested_edges=target)
    elif method == "knn":
        k = _positive_integer(k, "k")
        for index in range(n):
            eligible = strengths[index, nonzero[index]]
            if len(eligible):
                count = min(k, len(eligible))
                cutoff = np.partition(eligible, len(eligible) - count)[len(eligible) - count]
                selected[index] = nonzero[index] & _at_least(strengths[index], float(cutoff))
        selected |= selected.T
        metadata.update(k=k, neighbor_symmetrization="union")
    else:
        # A stable ID tie-break is invariant to reordering the matrix and IDs.
        edges = []
        for row, col in zip(*np.where(np.triu(nonzero, 1))):
            canonical = tuple(sorted((ids[row], ids[col])))
            edges.append((float(strengths[row, col]), canonical, row, col))
        forest = nx.utils.UnionFind(ids)
        for _, _, row, col in sorted(edges, key=lambda edge: (-edge[0], edge[1])):
            if forest[ids[row]] != forest[ids[col]]:
                selected[row, col] = selected[col, row] = True
                forest.union(ids[row], ids[col])
        metadata["tie_policy"] = "canonical sorted ROI-ID pairs for equal absolute weights"
    graph = nx.Graph()
    graph.add_nodes_from(ids)
    for row, col in zip(*np.where(np.triu(selected, 1))):
        graph.add_edge(ids[row], ids[col], weight=float(data[row, col]))
    metadata["actual_density"] = nx.density(graph)
    graph.graph.update(metadata)
    return graph


def analyze_graph(graph: nx.Graph) -> dict:
    """Describe signed structure; lengths, clustering and communities use w>0.

    Length = 1 / weight. Efficiency averages reciprocal shortest-path length
    over all ordered distinct ROI pairs (unreachable pairs contribute zero).
    Clustering is Onnela weighted clustering, normalized by maximum positive
    edge weight. Exact weighted betweenness is bounded to <=300 ROIs and
    <=10000 positive edges; larger inputs report null with an explicit reason.
    Community labels are descriptive Louvain partitions, resolution=1, seed=0.
    """
    if not isinstance(graph, nx.Graph) or graph.is_directed() or graph.is_multigraph():
        raise ValidationError("Expected a simple undirected NetworkX Graph.")
    nodes = sorted(graph.nodes, key=str)
    if len(nodes) > 1000 or len({str(node) for node in nodes}) != len(nodes):
        raise ValidationError("Graph requires at most 1000 unique serializable ROI IDs.")
    if nx.number_of_selfloops(graph):
        raise ValidationError("Remove self-loops before graph analysis.")
    for _, _, attrs in graph.edges(data=True):
        if not isinstance(attrs.get("weight", 1), (int, float, np.number)) or not np.isfinite(attrs.get("weight", 1)):
            raise ValidationError("Graph weights must be finite numbers.")
    n = len(nodes)
    matrix = nx.to_numpy_array(graph, nodelist=nodes, weight="weight")
    positive = np.maximum(matrix, 0.0)
    pos_graph = nx.Graph()
    pos_graph.add_nodes_from(nodes)
    for i, j in zip(*np.where(np.triu(positive > 0, 1))):
        weight = float(positive[i, j])
        pos_graph.add_edge(nodes[i], nodes[j], weight=weight, length=1.0 / weight)
    lengths = np.divide(1.0, positive, out=np.zeros_like(positive), where=positive > 0)
    distances = shortest_path(lengths, directed=False) if n else np.empty((0, 0))
    reachable = np.isfinite(distances) & (distances > 0)
    inverse = np.divide(1.0, distances, out=np.zeros_like(distances), where=reachable)
    efficiency = float(inverse.sum() / (n * (n - 1))) if n > 1 else 0.0
    degree_positive = (positive > 0).sum(axis=1)
    if positive.size and positive.max() > 0:
        cube = np.cbrt(positive / positive.max())
        triangles = np.einsum("ij,ji->i", cube @ cube, cube)
        denominator = degree_positive * (degree_positive - 1)
        clustering = np.divide(triangles, denominator, out=np.zeros(n), where=denominator > 0)
    else:
        clustering = np.zeros(n)
    betweenness_computed = n <= 300 and pos_graph.number_of_edges() <= 10000
    between = nx.betweenness_centrality(pos_graph, weight="length") if betweenness_computed else {}
    if pos_graph.number_of_edges():
        communities = nx.community.louvain_communities(pos_graph, weight="weight", resolution=1, seed=0)
        communities = sorted((sorted(group, key=str) for group in communities), key=lambda group: tuple(map(str, group)))
        modularity = float(nx.community.modularity(pos_graph, communities, weight="weight"))
    else:
        communities = [[node] for node in nodes]
        modularity = None
    membership = {node: index for index, group in enumerate(communities) for node in group}
    rows = []
    for i, node in enumerate(nodes):
        reached = int(reachable[i].sum())
        length_sum = float(distances[i, reachable[i]].sum())
        closeness = (reached / (n - 1)) * (reached / length_sum) if reached and n > 1 else 0.0
        rows.append({"id": str(node), "degree": int(graph.degree[node]),
                     "degree_centrality": float(graph.degree[node] / (n - 1)) if n > 1 else 0.0,
                     "strength": float(matrix[i].sum()), "positive_strength": float(positive[i].sum()),
                     "negative_strength": float(np.minimum(matrix[i], 0).sum()),
                     "clustering_positive": float(clustering[i]),
                     "harmonic_centrality_positive": float(inverse[i].sum() / (n - 1)) if n > 1 else 0.0,
                     "closeness_positive": closeness,
                     "betweenness_positive": float(between[node]) if betweenness_computed else None,
                     "community_positive": membership[node]})
    upper = matrix[np.triu_indices(n, 1)]
    return {"global": {"n_nodes": n, "n_edges": graph.number_of_edges(),
                       "density": float(nx.density(graph)),
                       "n_components": nx.number_connected_components(graph) if n else 0,
                       "n_positive_components": nx.number_connected_components(pos_graph) if n else 0,
                       "positive_edges": int(np.sum(upper > 0)), "negative_edges": int(np.sum(upper < 0)),
                       "mean_degree": float(sum(dict(graph.degree()).values()) / n) if n else 0.0,
                       "mean_clustering_positive": float(clustering.mean()) if n else 0.0,
                       "global_efficiency_positive": efficiency,
                       "mean_path_length_reachable_positive": float(distances[reachable].mean()) if reachable.any() else None,
                       "modularity_positive": modularity, "n_communities_positive": len(communities),
                       "betweenness_computed": betweenness_computed},
            "nodes": rows,
            "definitions": {"selection": dict(graph.graph),
                            "length_metrics": "Positive weights only; edge length=1/weight; disconnected pairs contribute 0 efficiency.",
                            "clustering": "Positive Onnela clustering, normalized by maximum positive edge weight.",
                            "negative_strength": "Sum of negative weights, retaining their negative sign.",
                            "community": "Louvain on positive weights; resolution=1, seed=0; canonical ROI-ID iteration order.",
                            "betweenness": "Exact weighted positive betweenness; omitted (null) above 300 nodes or 10000 positive edges."}}


def to_payload(graph: nx.Graph) -> dict:
    """Return JSON-safe edge records and metrics; retain input edge signs."""
    metrics = analyze_graph(graph)
    edges = []
    for source, target, attrs in graph.edges(data=True):
        source, target = sorted((str(source), str(target)))
        import hashlib
        import json
        edge_id = "edge-" + hashlib.sha256(json.dumps([source, target], ensure_ascii=False).encode()).hexdigest()[:24]
        edges.append({"id": edge_id, "source": source, "target": target, "weight": float(attrs.get("weight", 1.0))})
    return {"edges": sorted(edges, key=lambda edge: (edge["source"], edge["target"])), "metrics": metrics,
            "construction": dict(graph.graph)}
