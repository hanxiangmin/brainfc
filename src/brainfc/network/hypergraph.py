"""Native hyperedges with persistent identity, using XGI.

FC-profile neighborhoods are constructed representations of pairwise data.
They do not establish irreducible higher-order statistical interactions.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping

import networkx as nx
import numpy as np
import xgi
from xgi.exception import XGIError

from .graph import _at_least, _positive_integer, _validate_matrix
from .types import ValidationError

MAX_EDGES = 10000
MAX_MEMBERSHIPS = 250000


def _edge_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or (isinstance(value, str) and not value.strip()):
        raise ValidationError("Every hyperedge ID must be a nonempty string or integer.")
    return value


def _members(value, valid: set[str]) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple, set, np.ndarray)):
        raise ValidationError("Hyperedge members must be a list of ROI IDs.")
    members = [str(member) for member in value]
    if not members or len(set(members)) != len(members):
        raise ValidationError("Hyperedges must have at least one member and cannot repeat a member.")
    unknown = set(members) - valid
    if unknown:
        raise ValidationError(f"Hyperedge references unknown ROI IDs: {', '.join(sorted(unknown)[:5])}.")
    return sorted(members)


def _weight(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)) or not np.isfinite(value):
        raise ValidationError("Hyperedge weight must be a finite number.")
    return float(value)


def build_hypergraph(matrix, roi_ids=None, method: str = "knn", ks=None,
                     custom_edges=None, groups=None) -> xgi.Hypergraph:
    """Return a native XGI Hypergraph, preserving all supplied ROI nodes.

    ``knn`` accepts one k (default 5); ``multiscale`` accepts up to ten values
    (default 5, 10). Neighbors rank signed cosine similarity of zero-diagonal
    FC profiles. All cutoff ties are included, and zero-norm profiles are
    excluded from profile construction. Each edge includes its center.
    Generated member sets are deduplicated across centers/scales; their IDs
    are hashes of sorted ROI IDs. Explicit custom/template edge IDs are never
    deduplicated, even if two edges contain exactly the same members.

    Generated and template edges have unit weight. Custom weights retain their
    supplied sign. Limits: 10000 edges and 250000 total memberships.
    """
    data, ids = _validate_matrix(matrix, roi_ids)
    if method not in {"knn", "multiscale", "custom", "template"}:
        raise ValidationError("Unknown hypergraph construction method.")
    hypergraph = xgi.Hypergraph()
    hypergraph.add_nodes_from(ids)
    construction = {"method": method, "representation": "constructed hypergraph; not evidence of irreducible interactions",
                    "limits": {"edges": MAX_EDGES, "memberships": MAX_MEMBERSHIPS}}
    records = []
    membership_count = 0
    if method == "custom":
        if custom_edges is None:
            custom_edges = []
        if not isinstance(custom_edges, (list, tuple)):
            raise ValidationError("custom_edges must be a list of edge records.")
        if len(custom_edges) > MAX_EDGES:
            raise ValidationError(f"Hypergraph exceeds {MAX_EDGES} edges.")
        seen = set()
        for edge in custom_edges:
            if not isinstance(edge, Mapping) or "id" not in edge or "members" not in edge:
                raise ValidationError("Every custom edge needs id and members.")
            edge_id = _edge_id(edge["id"])
            if edge_id in seen:
                raise ValidationError(f"Duplicate hyperedge ID: {edge_id}.")
            seen.add(edge_id)
            records.append({"id": edge_id, "members": _members(edge["members"], set(ids)),
                            "weight": _weight(edge.get("weight", 1.0)), "source": "custom"})
            membership_count += len(records[-1]["members"])
            if membership_count > MAX_MEMBERSHIPS:
                raise ValidationError(f"Hypergraph exceeds {MAX_MEMBERSHIPS} memberships.")
    elif method == "template":
        groups = {} if groups is None else groups
        if not isinstance(groups, Mapping):
            raise ValidationError("groups must map group IDs to lists of ROI IDs.")
        if len(groups) > MAX_EDGES:
            raise ValidationError(f"Hypergraph exceeds {MAX_EDGES} edges.")
        for group_id, members in groups.items():
            records.append({"id": _edge_id(group_id), "members": _members(members, set(ids)),
                            "weight": 1.0, "source": "template"})
            membership_count += len(records[-1]["members"])
            if membership_count > MAX_MEMBERSHIPS:
                raise ValidationError(f"Hypergraph exceeds {MAX_MEMBERSHIPS} memberships.")
    else:
        if ks is None:
            ks = [5] if method == "knn" else [5, 10]
        if not isinstance(ks, (list, tuple)) or not 1 <= len(ks) <= 10:
            raise ValidationError("ks must contain 1 to 10 positive integers.")
        ks = sorted(set(_positive_integer(k, "ks entries") for k in ks))
        if method == "knn" and len(ks) != 1:
            # A shared analysis configuration may supply multiscale defaults.
            # Single-scale mode explicitly uses its smallest requested scale.
            construction["unused_scales"] = ks[1:]
            ks = ks[:1]
        construction.update(ks=ks, profile_diagonal="zero", similarity="signed cosine similarity",
                            tie_policy="include all cutoff ties (rtol=1e-10, atol=1e-12)",
                            duplicate_policy="merge generated member sets across centers and scales",
                            generated_weight="1.0; topology only")
        magnitudes = np.max(np.abs(data), axis=1)
        scaled = np.divide(data, magnitudes[:, None], out=np.zeros_like(data), where=magnitudes[:, None] > 0)
        norms = np.linalg.norm(scaled, axis=1)
        profiles = np.divide(scaled, norms[:, None], out=np.zeros_like(data), where=norms[:, None] > 0)
        similarity = np.clip(profiles @ profiles.T, -1.0, 1.0)
        valid = norms > 0
        construction["excluded_zero_profiles"] = sorted(ids[index] for index in np.where(~valid)[0])
        generated = {}
        for center in range(len(ids)):
            if not valid[center]:
                continue
            eligible = valid.copy()
            eligible[center] = False
            values = similarity[center, eligible]
            if not len(values):
                continue
            for k in ks:
                count = min(k, len(values))
                cutoff = np.partition(values, len(values) - count)[len(values) - count]
                choices = eligible & _at_least(similarity[center], float(cutoff))
                members = tuple(sorted([ids[center]] + [ids[j] for j in np.where(choices)[0]]))
                if members not in generated:
                    membership_count += len(members)
                    if membership_count > MAX_MEMBERSHIPS:
                        raise ValidationError(f"Hypergraph exceeds {MAX_MEMBERSHIPS} memberships; reduce scales or neighborhood sizes.")
                    digest = hashlib.sha256(json.dumps(members, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
                    generated[members] = {"id": "he_" + digest, "members": list(members), "weight": 1.0,
                                          "source": "fc_profile", "centers": set(), "scales": set()}
                generated[members]["centers"].add(ids[center])
                generated[members]["scales"].add(k)
        for record in generated.values():
            record["centers"] = sorted(record["centers"])
            record["scales"] = sorted(record["scales"])
            records.append(record)
    if len(records) > MAX_EDGES or sum(len(record["members"]) for record in records) > MAX_MEMBERSHIPS:
        raise ValidationError(f"Hypergraph exceeds {MAX_EDGES} edges or {MAX_MEMBERSHIPS} memberships; reduce scales or group sizes.")
    for record in records:
        attrs = {key: value for key, value in record.items() if key not in {"id", "members"}}
        hypergraph.add_edge(record["members"], idx=record["id"], **attrs)
    hypergraph["construction"] = construction
    return hypergraph


def to_payload(hypergraph: xgi.Hypergraph) -> dict:
    """Return native edges, sparse incidence and descriptive hypergraph metrics.

    Connectivity is incidence connectivity; it does not require constructing
    an expanded pairwise graph. Overlap summarizes the number of shared nodes
    across all distinct edge pairs, including pairs with zero overlap.
    """
    if not isinstance(hypergraph, xgi.Hypergraph):
        raise ValidationError("Expected an XGI Hypergraph.")
    nodes = sorted(hypergraph.nodes, key=str)
    edges_ids = sorted(hypergraph.edges, key=lambda value: (str(value), type(value).__name__))
    if len(nodes) > 1000 or len({str(node) for node in nodes}) != len(nodes) or len(edges_ids) > MAX_EDGES:
        raise ValidationError("Hypergraph exceeds resource limits or has ambiguous ROI IDs.")
    node_index = {node: index for index, node in enumerate(nodes)}
    records = []
    node_edges = {node: [] for node in nodes}
    incidence_rows, incidence_columns = [], []
    components = nx.utils.UnionFind(nodes)
    for index, edge_id in enumerate(edges_ids):
        _edge_id(edge_id)
        members = sorted(hypergraph.edges.members(edge_id), key=str)
        if not members:
            raise ValidationError("Empty hyperedges cannot be analyzed.")
        attrs = hypergraph.edges[edge_id]
        weight = _weight(attrs.get("weight", 1.0))
        record = {"id": edge_id, "members": [str(member) for member in members], "weight": weight, "size": len(members)}
        for key in ("source", "centers", "scales"):
            if key in attrs:
                record[key] = attrs[key]
        records.append(record)
        components.union(*members)
        for member in members:
            node_edges[member].append(index)
            incidence_rows.append(node_index[member])
            incidence_columns.append(index)
        if len(incidence_rows) > MAX_MEMBERSHIPS:
            raise ValidationError(f"Hypergraph exceeds {MAX_MEMBERSHIPS} memberships.")
    rows = []
    for node in nodes:
        memberships = node_edges[node]
        sizes = [records[index]["size"] for index in memberships]
        weights = [records[index]["weight"] for index in memberships]
        rows.append({"id": str(node), "hyperdegree": len(memberships),
                     "weighted_hyperdegree": float(sum(weights)),
                     "participation_fraction": len(memberships) / len(records) if records else 0.0,
                     "mean_incident_edge_size": float(np.mean(sizes)) if sizes else 0.0,
                     "incident_edge_ids": [records[index]["id"] for index in memberships]})
    sizes = [record["size"] for record in records]
    pairs = len(records) * (len(records) - 1) // 2
    # Sum of pair intersections equals sum_v choose(hyperdegree(v), 2), so no
    # O(edge_count**2) overlap matrix or clique expansion needs to be stored.
    total_overlap = sum(len(edges) * (len(edges) - 1) // 2 for edges in node_edges.values())
    try:
        construction = hypergraph["construction"]
    except XGIError:
        construction = {"method": "external"}
    return {"edges": records,
            "incidence": {"format": "coo", "node_ids": [str(node) for node in nodes],
                          "edge_ids": edges_ids, "shape": [len(nodes), len(records)],
                          "row_indices": incidence_rows, "column_indices": incidence_columns},
            "construction": construction,
            "metrics": {"global": {"n_nodes": len(nodes), "n_edges": len(records),
                                   "n_memberships": len(incidence_rows),
                                   "mean_hyperdegree": len(incidence_rows) / len(nodes) if nodes else 0.0,
                                   "mean_edge_size": float(np.mean(sizes)) if sizes else 0.0,
                                   "max_edge_size": max(sizes, default=0),
                                   "edge_size_distribution": {str(size): count for size, count in sorted(Counter(sizes).items())},
                                   "n_components": len(list(components.to_sets())),
                                   "isolated_nodes": sum(not memberships for memberships in node_edges.values()),
                                   "mean_pairwise_overlap": total_overlap / pairs if pairs else 0.0},
                        "nodes": rows,
                        "definitions": {"connectivity": "Connected components of native incidence; isolated ROIs remain components.",
                                        "participation_fraction": "Number of incident hyperedges / total hyperedges (not a community participation coefficient).",
                                        "mean_pairwise_overlap": "Mean number of shared ROIs over all unordered distinct edge pairs, including zero intersections.",
                                        "weighted_hyperdegree": "Sum of incident edge weights, retaining supplied signs.",
                                        "incidence": "Unweighted binary membership in sparse COO format; column identity is original hyperedge ID."}}}
