"""Format inspection and conservative BIDS derivative discovery."""

from __future__ import annotations

import json
from pathlib import Path
import re
import nibabel as nib
import numpy as np
import pandas as pd
from scipy.io import loadmat
from .models import InputError

TABLE_SUFFIXES = {".csv", ".tsv", ".txt", ".1d", ".npy", ".npz", ".mat"}


def numeric_table(path, *, header=True, variable=None, transpose=False):
    """Read a real finite time x ROI table and optional column IDs.

    Parameters
    ----------
    path : str or pathlib.Path
        CSV (comma), TSV (tab), TXT/1D (whitespace), NPY, NPZ or pre-v7.3 MAT.
    header : bool, default True
        Text first row is column names; '#' lines are comments. False retains the
        first numeric row. Binary formats ignore this setting.
    variable : str or None, default None
        NPZ/MAT 2D numeric variable; infer only when exactly one exists.
    transpose : bool, default False
        Transpose values and discard inferred column names.

    Returns
    -------
    tuple[numpy.ndarray, list[str] or None]
        Float array and column IDs. Requires at least two rows and columns.

    Raises
    ------
    InputError
        Complex, nonfinite, non-2D data, ambiguous variable or unsupported MAT v7.3.

    Notes
    -----
    Only ROI columns may be supplied; numeric time/index columns are not detected
    automatically. NPY/NPZ use allow_pickle=False. No symmetric-matrix check here."""
    path = Path(path)
    labels = None
    if path.suffix.lower() == ".npy":
        values = np.load(path, allow_pickle=False)
    elif path.suffix.lower() in {".npz", ".mat"}:
        if path.suffix.lower() == ".npz":
            with np.load(path, allow_pickle=False) as archive:
                arrays = {k: archive[k] for k in archive.files}
        else:
            try:
                arrays = loadmat(path)
            except NotImplementedError as exc:
                raise InputError("MAT v7.3/HDF5 is not supported; export a numeric TSV or NPY.") from exc
        keys = [
            k
            for k, v in arrays.items()
            if not k.startswith("__")
            and isinstance(v, np.ndarray)
            and v.ndim == 2
            and np.issubdtype(v.dtype, np.number)
        ]
        if variable is None:
            if len(keys) != 1:
                raise InputError(f"Choose variable explicitly from {keys}.")
            variable = keys[0]
        if variable not in keys:
            raise InputError(f"No 2D numeric variable {variable!r}; available: {keys}.")
        values = arrays[variable]
    else:
        sep = "," if path.suffix.lower() == ".csv" else "\t" if path.suffix.lower() == ".tsv" else r"\s+"
        frame = pd.read_csv(path, sep=sep, header=0 if header else None, comment="#")
        labels = frame.columns.astype(str).tolist() if header else None
        try:
            values = frame.to_numpy(dtype=float)
        except ValueError as exc:
            raise InputError(
                "Time-series table must contain only numeric ROI columns, without a time/index column."
            ) from exc
    if np.iscomplexobj(values):
        raise InputError("Complex-valued time series are unsupported.")
    values = np.asarray(values, dtype=float)
    if transpose:
        values, labels = values.T, None
    if values.ndim != 2 or min(values.shape) < 2 or not np.isfinite(values).all():
        raise InputError("Expected a finite time × ROI matrix with at least two rows and columns.")
    return values, labels


def sidecar_path(path):
    """Return the adjacent JSON candidate for a source filename.

    For *.nii[.gz], *.dtseries.nii and *.ptseries.nii replace the imaging suffix
    with .json. For other formats append .json (for example signals.tsv.json).
    Returns pathlib.Path without checking existence; BIDS inheritance is not used."""
    p = Path(path)
    return p.with_name(re.sub(r"\.(dtseries\.nii|ptseries\.nii|nii(\.gz)?)$", "", p.name) + ".json")


def metadata(path):
    """Read adjacent JSON RepetitionTime and the filename's BIDS space entity.

    Returns a dict with sidecar (absolute path or None), t_r (seconds or None),
    and space (str or None). Missing JSON yields no TR; malformed JSON propagates
    JSONDecodeError. Header TR is handled by check_input/extract_connectome."""
    path = Path(path)
    sidecar = sidecar_path(path)
    content = json.loads(sidecar.read_text(encoding="utf-8-sig")) if sidecar.is_file() else {}
    space = re.search(r"(?:^|_)space-([^_]+)", path.name)
    return {
        "sidecar": str(sidecar.resolve()) if sidecar.is_file() else None,
        "t_r": content.get("RepetitionTime"),
        "space": space.group(1) if space else None,
    }


def inspect_input(path):
    """Inspect file structure or discover preprocessed volume runs in a directory.

    Parameters
    ----------
    path : str or pathlib.Path
        Existing source file or derivative directory.

    Returns
    -------
    dict
        Common file keys: path, size_bytes, sidecar, t_r, space, format.
        Volume adds shape/affine/orientation/units when available; CIFTI shape/axes;
        GIFTI array shapes; NPZ/MAT variable shapes. Directory returns format/runs.

    Raises
    ------
    InputError
        Missing path or unreadable image. Low-level table/JSON errors may propagate.

    Notes
    -----
    Inspection alone does not validate numerical signals, ROI coverage or cleaning
    feasibility. Use check_input/preflight or extract_connectome for deeper checks."""
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise InputError(f"File does not exist: {path}")
    if path.is_dir():
        return {"format": "directory", "runs": discover_bids(path)}
    result = {"path": str(path), "size_bytes": path.stat().st_size, **metadata(path)}
    if path.suffix.lower() in TABLE_SUFFIXES:
        result["format"] = "timeseries-table"
        if path.suffix.lower() == ".npz":
            with np.load(path, allow_pickle=False) as a:
                result["variables"] = {k: list(a[k].shape) for k in a.files}
        elif path.suffix.lower() == ".mat":
            from scipy.io import whosmat

            result["variables"] = {name: list(shape) for name, shape, _ in whosmat(path)}
        return result
    try:
        img = nib.load(path)
    except Exception as exc:
        raise InputError("Cannot read image. Convert DICOM with brainfc dicom first.") from exc
    if isinstance(img, nib.Cifti2Image):
        result.update(
            format="cifti",
            shape=list(img.shape),
            axes=[type(img.header.get_axis(i)).__name__ for i in range(img.ndim)],
        )
    elif isinstance(img, nib.gifti.GiftiImage):
        result.update(format="gifti", arrays=[list(d.data.shape) for d in img.darrays])
    else:
        result.update(
            format="volume",
            shape=list(img.shape),
            orientation=list(nib.aff2axcodes(img.affine)),
            affine=img.affine.tolist(),
        )
        if hasattr(img.header, "get_xyzt_units"):
            result["units"] = list(img.header.get_xyzt_units())
    return result


def discover_bids(root):
    """List separate fMRIPrep preprocessed volume runs below root.

    Parameters
    ----------
    root : str or pathlib.Path
        Recursively scanned for *_desc-preproc_bold.nii* in sorted path order.

    Returns
    -------
    list[dict]
        Each record has bold, confounds, mask, subject, session, task, run, sidecar,
        t_r, space. Missing companions/entities are None. No matches yields [].

    Raises
    ------
    InputError
        More than one matching mask or confounds file makes a run ambiguous.

    Notes
    -----
    Companions must be in the same directory with exactly matching entities after
    excluding space/res/den/desc; masks additionally match space/res. No merging,
    raw BIDS conversion, multi-echo combination or full BIDS metadata inheritance."""
    root = Path(root).expanduser().resolve()
    result = []
    paths = sorted(set(root.rglob("*_desc-preproc_bold.nii*")))
    for p in paths:
        entities = dict(re.findall(r"(?:^|_)([a-zA-Z0-9]+)-([^_]+)", p.name.split(".")[0]))
        key = {k: v for k, v in entities.items() if k not in {"space", "res", "den", "desc"}}

        def candidates(pattern, spatial=False):
            hits = []
            for q in p.parent.glob(pattern):
                other = dict(re.findall(r"(?:^|_)([a-zA-Z0-9]+)-([^_]+)", q.name.split(".")[0]))
                otherkey = {k: v for k, v in other.items() if k not in {"space", "res", "den", "desc"}}
                if key == otherkey and (
                    not spatial or all(other.get(k) == entities.get(k) for k in ("space", "res"))
                ):
                    hits.append(q)
            if len(hits) > 1:
                raise InputError(f"Ambiguous companions for {p.name}: {[x.name for x in hits]}")
            return str(hits[0]) if hits else None

        result.append(
            {
                "bold": str(p),
                "confounds": candidates("*_desc-confounds_timeseries.tsv"),
                "mask": candidates("*_desc-brain_mask.nii*", True),
                "subject": entities.get("sub"),
                "session": entities.get("ses"),
                "task": entities.get("task"),
                "run": entities.get("run"),
                **metadata(p),
            }
        )
    return result
