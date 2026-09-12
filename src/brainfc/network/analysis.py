"""Single analysis entry point used by Python, CLI and local HTTP workers."""
from __future__ import annotations

import hashlib
from importlib.metadata import version as package_version
from datetime import datetime, timezone

import numpy as np

from . import connectivity, graph, hypergraph
from .io import validate_dataset
from .types import AnalysisConfig, AnalysisResult, ValidationError


def analyze(dataset, config=None, progress=None):
    """Analyze a validated dataset without modifying it or its source file.

    ``progress``, when supplied, receives ``(percent, message)``. Returned
    structures retain ROI identities; display layouts never change coordinates.
    """
    config = AnalysisConfig() if config is None else config
    if isinstance(config, dict):
        config = AnalysisConfig.from_dict(config)
    if not isinstance(config, AnalysisConfig):
        raise ValidationError("config must be AnalysisConfig or a dictionary.")
    config.__post_init__()
    update = progress or (lambda _percent, _message: None)
    update(5, "Validating input")
    warnings = list(dict.fromkeys(dataset.warnings + validate_dataset(dataset)))
    update(15, "Preparing functional connectivity")
    if dataset.kind == "timeseries":
        matrix = connectivity.compute_connectivity(dataset.data, method=config.connectivity_method)
    else:
        matrix = dataset.data.copy()
        if dataset.matrix_kind == "fisher_z":
            matrix = connectivity.inverse_fisher_z(matrix)
        elif dataset.matrix_kind == "covariance":
            diagonal = np.diag(matrix)
            if np.any(diagonal <= 0):
                raise ValidationError("Covariance requires strictly positive diagonal variances.")
            matrix = matrix / np.sqrt(np.outer(diagonal, diagonal))
            warnings.append("Covariance was explicitly normalized to a correlation matrix.")
        np.fill_diagonal(matrix, 1.0)
    if not np.isfinite(matrix).all() or np.max(np.abs(matrix)) > 1 + 1e-6:
        raise ValidationError("The resulting correlation matrix must be finite and within [-1, 1].")
    matrix = np.clip((matrix + matrix.T) / 2, -1, 1)
    graph_payload = {"edges": [], "metrics": {"global": {}, "nodes": []}}
    hypergraph_payload = {"edges": [], "metrics": {"global": {}, "nodes": []}}
    if config.compute_graph:
        update(30, "Building signed graph and computing positive-network metrics")
        network = graph.build_graph(matrix, roi_ids=dataset.roi_ids, method=config.graph_method,
                                    threshold=config.threshold, density=config.density, k=config.k)
        graph_payload = graph.to_payload(network)
    if config.compute_hypergraph:
        update(65, "Building native hyperedges and computing structure metrics")
        ks = [config.k] if config.hypergraph_method == "knn" else config.hypergraph_ks
        network = hypergraph.build_hypergraph(matrix, roi_ids=dataset.roi_ids,
                    method=config.hypergraph_method, ks=ks,
                    custom_edges=config.custom_edges, groups=config.groups)
        hypergraph_payload = hypergraph.to_payload(network)
    metadata = dict(dataset.metadata)
    metadata.update({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_kind": dataset.kind,
        "input_shape": list(dataset.data.shape),
        "input_matrix_kind": dataset.matrix_kind,
        "numeric_sha256": hashlib.sha256(np.ascontiguousarray(dataset.data, dtype="<f8").tobytes()).hexdigest(),
        "output_matrix_kind": "correlation",
        "dependency_versions": {name: package_version(name) for name in ("numpy", "scipy", "nilearn", "networkx", "xgi")},
        "interpretation": "Descriptive network structure; constructed hyperedges do not establish irreducible interactions or a diagnosis.",
        "anatomical_mapping": "provided" if dataset.coordinates is not None else "unavailable",
    })
    result = AnalysisResult(matrix, list(dataset.roi_ids), list(dataset.labels),
        None if dataset.coordinates is None else dataset.coordinates.copy(), graph_payload,
        hypergraph_payload, config.to_dict(), metadata, list(dict.fromkeys(warnings)))
    # Stable ROI-identity layout is saved independently from anatomical coordinates.
    ordered_ids = sorted(dataset.roi_ids)
    result.layouts = {"graph_2d": {"kind": "circular", "coordinate_space": "display", "units": "unitless", "y_axis": "down",
        "nodes": [{"id": roi, "x": float(np.cos(2 * np.pi * i / len(ordered_ids) - np.pi / 2)),
                   "y": float(np.sin(2 * np.pi * i / len(ordered_ids) - np.pi / 2))}
                  for i, roi in enumerate(ordered_ids)]}}
    update(100, "Analysis complete")
    return result
