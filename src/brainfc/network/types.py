"""Shared, serializable contracts for the Python API and local application."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from numbers import Real
from typing import Any

import numpy as np
from .._version import __version__


class ValidationError(ValueError):
    """An input cannot be analyzed without an explicit correction."""


@dataclass
class BrainDataset:
    """Network-analysis input: a matrix or already-prepared ROI time series.

    data is a real 2D array; kind is 'connectivity' (R x R) or 'timeseries'
    (T x R). roi_ids and labels are ordered nonempty strings, defaulting to
    ROI_001... and the IDs respectively. coordinates is optional R x 3 RAS+ mm;
    declare its exact coordinate_space in metadata. matrix_kind is correlation,
    fisher_z or covariance (last two only for connectivity). metadata and warnings
    hold caller provenance and known limitations. Construction coerces numeric
    values; validate_dataset/analyze performs scientific shape/scale checks.
    Matrices are not copied when the input already has float dtype.
    """
    data: np.ndarray
    kind: str
    roi_ids: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    coordinates: np.ndarray | None = None
    matrix_kind: str = "correlation"
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        try:
            raw = np.asarray(self.data)
            if raw.dtype.kind not in "iuf":
                raise ValidationError("Data must contain real numeric values, not objects or complex numbers.")
            self.data = raw.astype(float, copy=False)
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"Cannot convert input to a numeric array: {exc}") from exc
        if self.data.ndim != 2:
            raise ValidationError("Data must be a two-dimensional numeric array.")
        n = self.data.shape[1]
        self.roi_ids = [str(x) for x in self.roi_ids] if self.roi_ids is not None and len(self.roi_ids) else [f"ROI_{i+1:03d}" for i in range(n)]
        self.labels = [str(x) for x in self.labels] if self.labels is not None and len(self.labels) else list(self.roi_ids)
        if self.coordinates is not None:
            self.coordinates = np.asarray(self.coordinates, dtype=float)

    @property
    def n_rois(self) -> int:
        """Return the number of data columns, i.e. ordered regions."""
        return self.data.shape[1]


@dataclass
class AnalysisConfig:
    """Settings for descriptive graph and hypergraph construction.

    connectivity_method: pearson/spearman/partial, only used for time series;
    partial uses Ledoit-Wolf shrinkage. No signal cleaning is performed here.
    graph_method: weighted/threshold/density/knn/mst; signed values are preserved,
    while edge selection ranks absolute weights. threshold is in [0,1], density
    in (0,1], k a positive integer. Cutoff ties can increase the realized density.
    hypergraph_method: knn/multiscale/template/custom. knn uses k; multiscale uses
    hypergraph_ks. custom_edges contains {id, members, optional weight} records;
    groups maps template IDs to ROI-ID lists. Custom IDs retain their str/int type
    and distinct IDs with identical memberships remain distinct.
    compute_graph/compute_hypergraph enable each structure; at least one must be
    true. All defaults appear in the generated signature. Invalid configuration
    raises ValidationError. Constructed hyperedges are descriptive, not a test
    for irreducible physiological interactions.
    """
    connectivity_method: str = "pearson"
    graph_method: str = "density"
    threshold: float = 0.2
    density: float = 0.1
    k: int = 5
    hypergraph_method: str = "knn"
    hypergraph_ks: list[int] = field(default_factory=lambda: [5, 10])
    custom_edges: list[dict[str, Any]] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)
    compute_graph: bool = True
    compute_hypergraph: bool = True

    def __post_init__(self):
        enums = {
            "connectivity_method": ["pearson", "spearman", "partial"],
            "graph_method": ["weighted", "threshold", "density", "knn", "mst"],
            "hypergraph_method": ["knn", "multiscale", "custom", "template"],
        }
        for name, allowed in enums.items():
            if getattr(self, name) not in allowed:
                raise ValidationError(f"{name} must be one of {allowed}.")
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, Real) or not np.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValidationError("threshold must be between 0 and 1.")
        if isinstance(self.density, bool) or not isinstance(self.density, Real) or not np.isfinite(self.density) or not 0 < self.density <= 1:
            raise ValidationError("density must be greater than 0 and at most 1.")
        if not isinstance(self.k, int) or isinstance(self.k, bool) or self.k < 1:
            raise ValidationError("k must be a positive integer.")
        if not isinstance(self.hypergraph_ks, list) or not self.hypergraph_ks or any(not isinstance(k, int) or isinstance(k, bool) or k < 1 for k in self.hypergraph_ks):
            raise ValidationError("hypergraph_ks must contain positive integers.")
        if not isinstance(self.compute_graph, bool) or not isinstance(self.compute_hypergraph, bool):
            raise ValidationError("compute_graph and compute_hypergraph must be booleans.")
        if not self.compute_graph and not self.compute_hypergraph:
            raise ValidationError("Select at least one of graph or hypergraph analysis.")

    def to_dict(self):
        """Return a deep dataclass-field dictionary suitable for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        """Validate keyword fields and construct a configuration; reject unknown keys."""
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValidationError(f"Invalid analysis configuration: {exc}") from exc


@dataclass
class AnalysisResult:
    """Serializable descriptive network result, normally returned by analyze.

    connectivity: full R x R correlation (unit diagonal). roi_ids/labels preserve
    input order; coordinates are independent of display layouts. graph contains
    signed edges, construction metadata and global/node metrics; hypergraph holds
    native member sets with original IDs, sparse incidence and structure metrics.
    config is the resolved AnalysisConfig; metadata holds input hashes, coordinate
    space and processing provenance; warnings lists limitations. version records
    BrainFC's version; layouts stores display-only positions, never anatomy.
    Direct construction/from_dict is not a substitute for analyze validation.
    """
    connectivity: np.ndarray
    roi_ids: list[str]
    labels: list[str]
    coordinates: np.ndarray | None
    graph: dict[str, Any]
    hypergraph: dict[str, Any]
    config: dict[str, Any]
    metadata: dict[str, Any]
    warnings: list[str]
    version: str = __version__
    layouts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        """Return JSON-ready data; arrays become lists and nonfinite scalars become None."""
        def convert(x):
            if isinstance(x, np.ndarray):
                return convert(x.tolist())
            if isinstance(x, np.generic):
                return convert(x.item())
            if isinstance(x, float) and not np.isfinite(x):
                return None
            if isinstance(x, dict):
                return {str(k): convert(v) for k, v in x.items()}
            if isinstance(x, (list, tuple)):
                return [convert(v) for v in x]
            return x
        return convert(asdict(self))

    @classmethod
    def from_dict(cls, value):
        """Restore arrays from a trusted serialized result; does not run scientific validation."""
        value = dict(value)
        value["connectivity"] = np.asarray(value["connectivity"], dtype=float)
        if value.get("coordinates") is not None:
            value["coordinates"] = np.asarray(value["coordinates"], dtype=float)
        return cls(**value)
