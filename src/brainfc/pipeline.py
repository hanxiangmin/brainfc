"""One scientific core for Python, CLI and the local UI."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import hashlib
import warnings
import nibabel as nib
import numpy as np
import pandas as pd
from nilearn.signal import clean
from scipy.stats import rankdata
from sklearn.covariance import LedoitWolf
from .io import TABLE_SUFFIXES, metadata, numeric_table
from .imaging import (
    roi_table,
    make_rois,
    volume_timeseries,
    cifti_timeseries,
    gifti_timeseries,
    brain_geometry,
)
from .models import Config, Connectome, InputError
from ._version import __version__


def fingerprint(path):
    """Hash one input file in 4 MiB chunks.

    Parameters
    ----------
    path : str or pathlib.Path
        Existing file, expanded and resolved.

    Returns
    -------
    dict
        Absolute path, lowercase SHA-256 and size_bytes. Does not copy the file.
        Compound image partner files are not automatically enumerated."""
    p = Path(path).expanduser().resolve()
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return {"path": str(p), "sha256": h.hexdigest(), "size_bytes": p.stat().st_size}


def _confounds(path, n, config):
    """Build the regression design and original-frame keep mask.

    Parameters
    ----------
    path : str, pathlib.Path or None
        TSV/CSV with exactly n original rows; None means no regression design.
    n : int
        Number of original time points, before discard/censoring.
    config : Config
        Controls initial discard, FD cutoff and explicit/default regression columns.

    Returns
    -------
    tuple
        (design or None, keep_mask of shape (n,), quality_dict).

    Notes
    -----
    Nonsteady outlier columns censor nonzero rows. FD means/max use all finite
    original FD rows, including rows later excluded. Counts may overlap; use the
    combined keep mask for unique exclusions. Only first-row derivative1 NaNs
    are filled with zero, and each fill is recorded. An intercept-inclusive design
    rank/residual check occurs later in extract_connectome."""
    keep = np.ones(n, dtype=bool)
    keep[: config.discard] = False
    qc = {
        "confound_columns": [],
        "fd_mean": None,
        "fd_max": None,
        "fd_censored": 0,
        "nonsteady_censored": 0,
        "confound_nan_fill": [],
    }
    if path is None:
        if config.fd_threshold is not None or config.confound_columns:
            raise InputError("FD censoring / selected confounds require a confounds TSV/CSV.")
        return None, keep, qc
    p = Path(path)
    frame = pd.read_csv(p, sep=None, engine="python", na_values=["n/a"])
    if len(frame) != n:
        raise InputError(f"Confounds rows ({len(frame)}) differ from original time points ({n}).")
    for column in frame.columns:
        if column.startswith("non_steady_state_outlier"):
            v = pd.to_numeric(frame[column], errors="raise").to_numpy(float)
            if not np.isfinite(v).all():
                raise InputError(f"Nonfinite values in {column}.")
            keep[v != 0] = False
    qc["nonsteady_censored"] = int((~keep[config.discard :]).sum())
    if "framewise_displacement" in frame:
        fd = pd.to_numeric(frame.framewise_displacement, errors="raise").to_numpy(float)
        # The first FD is mathematically undefined. No other missing FD is silently filled.
        invalid = ~np.isfinite(fd)
        if invalid[1:].any() or np.isinf(fd[0]) or np.any(fd[np.isfinite(fd)] < 0):
            raise InputError("FD must be nonnegative and finite except for the first sample.")
        valid = fd[np.isfinite(fd)]
        qc.update(
            fd_mean=float(valid.mean()) if len(valid) else None,
            fd_max=float(valid.max()) if len(valid) else None,
        )
        if config.fd_threshold:
            bad = invalid | (fd > config.fd_threshold)
            keep[bad] = False
            qc["fd_censored"] = int(bad.sum())
    elif config.fd_threshold:
        raise InputError("Confounds lack framewise_displacement; FD is not inferred from motion parameters.")
    if config.confound_columns:
        columns = list(config.confound_columns)
    else:
        motion = [f"trans_{a}" for a in "xyz"] + [f"rot_{a}" for a in "xyz"]
        if any(c in frame for c in motion):
            if not all(c in frame for c in motion):
                raise InputError("Incomplete motion6 confounds; specify confound_columns explicitly.")
            columns = motion + [c for c in ("white_matter", "csf") if c in frame]
        else:
            raise InputError(
                "For generic confounds, specify confound_columns. No automatic regression of every column."
            )
    missing = set(columns) - set(frame.columns)
    if missing:
        raise InputError(f"Missing confound columns: {sorted(missing)}")
    matrix = frame[columns].to_numpy(float)
    # fMRIPrep temporal derivative columns use n/a on the first frame.
    for j, c in enumerate(columns):
        if np.isnan(matrix[0, j]) and "derivative1" in c:
            matrix[0, j] = 0
            qc["confound_nan_fill"].append({"column": c, "row": 0, "value": 0})
    if not np.isfinite(matrix).all():
        raise InputError("Selected confounds contain missing / nonfinite values.")
    qc["confound_columns"] = columns
    return matrix, keep, qc


def extract_connectome(
    source, *, atlas=None, rois=None, mask=None, reference=None, confounds=None, config=None, progress=None
):
    """Extract, clean and correlate one fMRI run or an ROI time-series file.

    Parameters
    ----------
    source : str or pathlib.Path
        One supported time-series file. Directories and DICOM are not accepted.
    atlas : str, pathlib.Path or None, default None
        3D nonnegative integer label image for volume; matching single-map dlabel
        for dense CIFTI; label.gii for GIFTI. Not used for tables/ptseries.
    rois : str, pathlib.Path or None, default None
        CSV/TSV mapping. Label images match by label_value; tables/ptseries by
        roi_id. Must exactly cover extracted IDs. Optional x/y/z are RAS+ mm.
    mask : str, pathlib.Path or None, default None
        Same-space volume mask. Positive values retain voxels; nearest-neighbor
        resampled. Not accepted for tables, CIFTI or GIFTI. Not used as reference
        unless also passed to reference.
    reference : str, pathlib.Path or None, default None
        Same-space 3D brain mask or skull-stripped reference for display only.
        The caller establishes registration; no transform is estimated.
    confounds : str, pathlib.Path or None, default None
        Headered TSV/CSV aligned to all original frames. See Config for selection.
    config : Config or None, default None
        None constructs Config(). Does not accept a configuration dict directly.
    progress : callable or None, default None
        Called synchronously with a human-readable str at processing milestones.

    Returns
    -------
    Connectome
        Cleaned time x ROI signals, signed R x R connectivity, Fisher-z, ROI order,
        retained original indices, QC, provenance and optional display geometry.

    Raises
    ------
    InputError
        Incompatible dimensions/axes/spaces/TR, missing ROIs, invalid confounds,
        insufficient retained frames/residual rank, nonfinite/constant ROI signals.
    OSError, ValueError
        Underlying file/parser failures may also propagate.

    Notes
    -----
    Image input requires preprocessed=True. Grid resampling is not registration.
    Processing: ROI means -> initial discard -> Nilearn joint filtering/regression/
    censoring -> correlation -> Fisher-z -> geometry/provenance. No files are
    written and no atlas is downloaded. Table numeric content is interpreted as
    time series; check_input additionally rejects suspected symmetric matrices.
    No group inference, disease classification or raw spatial preprocessing occurs."""
    config = config or Config()
    say = progress or (lambda message: None)
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise InputError("source must be a file representing a single run.")
    if config.discard < 0:
        raise InputError("discard cannot be negative.")
    meta = metadata(source)
    table = roi_table(rois)
    messages = []
    atlas_img = None
    say("Reading input and checking spatial alignment")
    if source.suffix.lower() in TABLE_SUFFIXES:
        ts, names = numeric_table(
            source, header=config.table_header, variable=config.variable, transpose=config.transpose
        )
        ids = names if names else [str(i + 1) for i in range(ts.shape[1])]
        regions = make_rois(ids, names, table=table, by_value=False)
        image_qc = {"format": "timeseries-table"}
        if atlas is not None or mask is not None:
            raise InputError(
                "Table input is already parcellated; supply a ROI table, not a volume atlas/mask."
            )
    else:
        if not config.preprocessed:
            raise InputError(
                "Image extraction requires preprocessed=True after motion correction / registration. Use the raw BIDS → fMRIPrep route for unprocessed scans."
            )
        space = config.data_space or meta["space"]
        if config.data_space and meta["space"] and config.data_space != meta["space"]:
            raise InputError("Declared data_space conflicts with the input's BIDS space entity.")
        if not space or (atlas is not None and (not config.atlas_space or space != config.atlas_space)):
            raise InputError("Declare matching data_space and atlas_space. Resampling is not registration.")
        config = replace(config, data_space=space)
        img = nib.load(source)
        if isinstance(img, nib.Cifti2Image):
            if mask is not None:
                raise InputError("Volume masks cannot be applied to CIFTI input.")
            ts, regions, image_qc, atlas_img = cifti_timeseries(img, atlas, table)
        elif isinstance(img, nib.gifti.GiftiImage):
            if mask is not None:
                raise InputError("Volume masks cannot be applied to GIFTI input.")
            ts, regions, image_qc, atlas_img = gifti_timeseries(img, atlas, table)
            messages.append(
                "GIFTI vertex alignment relies on the declared same surface/hemisphere and vertex order."
            )
        else:
            if atlas is None:
                raise InputError("4D volume requires a 3D integer label atlas.")
            ts, regions, image_qc, atlas_img = volume_timeseries(img, atlas, mask, table)
            image_qc["format"] = "volume"
            if len(img.header.get_zooms()) == 4:
                unit = img.header.get_xyzt_units()[1] if hasattr(img.header, "get_xyzt_units") else "unknown"
                scale = {"sec": 1, "msec": 0.001, "usec": 1e-6}.get(unit)
                if scale:
                    image_qc["t_r"] = float(img.header.get_zooms()[3]) * scale
                if image_qc.get("spatial_units", "").startswith("mm (unknown"):
                    messages.append(
                        "NIfTI spatial units were unspecified; coordinates interpreted as mm. Verify source metadata."
                    )
    if not np.isfinite(ts).all() or ts.ndim != 2 or ts.shape[1] < 2:
        raise InputError("Extracted time series must be finite with at least two ROIs.")
    tr = config.t_r or meta["t_r"] or image_qc.get("t_r")
    for inferred in (meta["t_r"], image_qc.get("t_r")):
        if tr and inferred and not np.isclose(tr, float(inferred), atol=1e-4, rtol=1e-4):
            raise InputError(f"TR metadata conflict: {tr} versus {inferred} seconds.")
    config = replace(config, t_r=float(tr) if tr else None)
    if config.high_pass or config.low_pass:
        if not config.t_r:
            raise InputError("Temporal filtering requires a known TR in seconds.")
        nyquist = 0.5 / config.t_r
        if any(v is not None and v >= nyquist for v in (config.low_pass, config.high_pass)):
            raise InputError(f"Filter frequencies must be below Nyquist ({nyquist:g} Hz).")
    n = len(ts)
    c, keep, cq = _confounds(confounds, n, config)
    if keep.sum() < config.min_samples:
        raise InputError(f"Only {keep.sum()} retained time points; min_samples={config.min_samples}.")
    say("Regressing confounds and applying temporal settings")
    start = config.discard
    sample_mask = np.flatnonzero(keep[start:])
    conf = c[start:] if c is not None else None
    if conf is not None:
        rank = int(np.linalg.matrix_rank(np.column_stack((np.ones(len(sample_mask)), conf[sample_mask]))))
        if len(sample_mask) - rank < 3:
            raise InputError("Too few residual degrees of freedom after confound regression.")
        cq["confound_design_rank_with_intercept"] = rank
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        try:
            cleaned = clean(
                ts[start:],
                confounds=conf,
                t_r=config.t_r,
                detrend=config.detrend,
                standardize="zscore_sample" if config.standardize else False,
                standardize_confounds=True,
                high_pass=config.high_pass,
                low_pass=config.low_pass,
                sample_mask=sample_mask,
                extrapolate=True,
                filter="butterworth" if (config.high_pass or config.low_pass) else False,
            )
        except ValueError as exc:
            raise InputError(f"Temporal cleaning failed (check scan length / filters): {exc}") from exc
        messages.extend(
            str(w.message) for w in emitted if not issubclass(w.category, (DeprecationWarning, FutureWarning))
        )
    scales = cleaned.std(axis=0)
    bad = np.flatnonzero(~np.isfinite(scales) | (scales <= 1e-10))
    if len(bad):
        raise InputError(
            f"Zero-variance / invalid ROIs after cleaning: {[regions[i]['roi_id'] for i in bad]}. No fabricated zero correlations returned."
        )
    say("Calculating connectivity and anatomical geometry")
    if config.method == "partial":
        estimator = LedoitWolf().fit(cleaned)
        precision = estimator.precision_
        matrix = -precision / np.sqrt(np.outer(np.diag(precision), np.diag(precision)))
        cq["shrinkage"] = float(estimator.shrinkage_)
    else:
        values = rankdata(cleaned, axis=0) if config.method == "spearman" else cleaned
        matrix = np.corrcoef(values, rowvar=False)
    matrix = np.clip((matrix + matrix.T) / 2, -1, 1)
    np.fill_diagonal(matrix, 1)
    if not np.isfinite(matrix).all():
        raise InputError("Connectivity contains nonfinite values.")
    z = np.arctanh(np.clip(matrix, -1 + 1e-7, 1 - 1e-7))
    np.fill_diagonal(z, 0)
    if confounds is None:
        messages.append(
            "No confound regression supplied; verify upstream denoising before using this run in a study."
        )
    if not any(r.get("coordinates") is None for r in regions):
        if not config.data_space:
            raise InputError("ROI coordinates require a declared data_space.")
        geometry = brain_geometry(atlas_img, reference, space=config.data_space, rois=regions)
    else:
        geometry = None
        messages.append(
            "No complete ROI coordinate table: matrix is available; supply coordinates to enable eight views and 3D."
        )
    say("Recording provenance")
    inputs = {
        name: fingerprint(p)
        for name, p in {
            "source": source,
            "atlas": atlas,
            "rois": rois,
            "mask": mask,
            "reference": reference,
            "confounds": confounds,
            "sidecar": meta["sidecar"],
        }.items()
        if p
    }
    qc = {
        **image_qc,
        **cq,
        "n_input": n,
        "n_retained": len(cleaned),
        "n_censored": int(n - keep.sum()),
        "retained_fraction": float(keep.mean()),
        "n_rois": len(regions),
        "t_r": config.t_r,
        "duration_retained_seconds": len(cleaned) * config.t_r if config.t_r else None,
        "warnings": messages,
    }
    provenance = {
        "software": "brainfc",
        "version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs,
        "config": config.to_dict(),
        "versions": {p: version(p) for p in ("numpy", "scipy", "nibabel", "nilearn", "scikit-learn")},
        "method": "Ledoit-Wolf shrinkage partial correlation"
        if config.method == "partial"
        else config.method,
        "roi_order": [r["roi_id"] for r in regions],
        "fisher_z": "atanh(clip(r, -1+1e-7, 1-1e-7)); diagonal=0",
        "operations": [
            "explicit spatial-space check",
            "ROI arithmetic means",
            "initial-volume removal",
            "Nilearn joint filtering and confound regression with sample mask",
            "connectivity",
        ],
        "filter_censoring": "Nilearn Butterworth uses interpolation with extrapolate=True before censor removal; retained samples keep original indices",
    }
    return Connectome(cleaned, matrix, z, regions, np.flatnonzero(keep), qc, provenance, geometry)
