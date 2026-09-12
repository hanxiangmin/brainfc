"""Transfer extracted connectivity to network analysis without temporal reprocessing."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np

from .io import validate_dataset
from .types import BrainDataset, ValidationError


def _dataset(payload):
    try:
        rois = payload["rois"]
        matrix = np.asarray(payload["connectivity"])
        ids = [str(r["roi_id"]) for r in rois]
        labels = [str(r.get("name", r["roi_id"])) for r in rois]
        if matrix.shape != (len(ids), len(ids)):
            raise ValidationError("Connectome matrix shape must match its ordered ROI records.")
        coords = [r.get("coordinates") for r in rois]
        coordinates = None if any(c is None for c in coords) else np.asarray(coords, dtype=float)
        metadata = {"brainfc": deepcopy(payload.get("provenance", {})),
                    "brainfc_qc": deepcopy(payload.get("qc", {})),
                    "sample_indices": deepcopy(payload.get("sample_indices", [])),
                    "roi_metadata": deepcopy(rois),
                    "bridge": "brainfc.connectome.v1"}
        geometry = payload.get("geometry")
        if geometry and coordinates is not None:
            metadata["brainfc_geometry"] = deepcopy(geometry)
            metadata["coordinate_space"] = geometry["space"]
        dataset = BrainDataset(matrix.copy(), "connectivity", roi_ids=ids, labels=labels,
                               coordinates=coordinates, metadata=metadata,
                               warnings=list(payload.get("qc", {}).get("warnings", [])))
        validate_dataset(dataset)
        return dataset
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid BrainFC connectome: {exc}") from exc


def from_connectome(connectome):
    """Copy a BrainFC Connectome into a network-analysis BrainDataset.

    Parameters
    ----------
    connectome : brainfc.Connectome
        An extracted run, with its complete signed correlation matrix.

    Returns
    -------
    BrainDataset
        Connectivity input with the original ROI order, names, coordinates,
        frame indices, QC and processing provenance. Available display geometry
        is copied into metadata; no atlas is guessed from the matrix size.

    Raises
    ------
    ValidationError
        Wrong input type, inconsistent dimensions/ROI identifiers, invalid
        coordinates, or an invalid correlation matrix.

    Notes
    -----
    This does not clean signals, recompute correlations, threshold the matrix
    or construct hyperedges. The returned arrays/metadata are independent copies.
    Pass the result to analyze with an explicit AnalysisConfig.
    """
    from brainfc.models import Connectome

    if not isinstance(connectome, Connectome):
        raise ValidationError("Expected a Connectome; use load_connectome for a saved result.")
    return _dataset(connectome.to_dict())


def load_connectome(path):
    """Read a saved BrainFC result as a network-analysis BrainDataset.

    Parameters
    ----------
    path : str or pathlib.Path
        A Connectome.save output directory or its result.json file. Input paths
        recorded inside provenance are metadata only and are never opened.

    Returns
    -------
    BrainDataset
        Same transfer contract as from_connectome; time series are not reprocessed.

    Raises
    ------
    FileNotFoundError
        Result JSON does not exist.
    ValidationError
        JSON is invalid, schema_version is unsupported, or the matrix/ROI mapping
        fails validation. Loading never modifies the saved result.
    """
    source = Path(path).expanduser()
    if source.is_dir():
        source = source / "result.json"
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValidationError("Expected a BrainFC schema-version-1 result.json.")
        return _dataset(payload)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValidationError(f"Cannot read BrainFC result JSON: {exc}") from exc
