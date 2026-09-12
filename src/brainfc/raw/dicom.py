"""Strict Python DICOM conversion with a separately validated UIH mosaic reader."""

from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path

import nibabel as nib
import numpy as np

from ..models import InputError


def _headers(source):
    import pydicom
    from pydicom.errors import InvalidDicomError

    root = Path(source).expanduser().resolve()
    if not root.is_dir():
        raise InputError("DICOM source must be an existing directory.")
    groups = defaultdict(list)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            d = pydicom.dcmread(path, stop_before_pixels=True)
        except (InvalidDicomError, EOFError):
            continue
        if d.get("Modality") != "MR" or not d.get("SeriesInstanceUID") or not d.get("Rows"):
            continue
        identity = "|".join(str(d.get(k, "")) for k in ("StudyInstanceUID", "SeriesInstanceUID", "EchoNumbers"))
        key = sha256(identity.encode()).hexdigest()[:20]
        groups[key].append((path, d))
    if not groups:
        raise InputError("No readable MR DICOM image series found.")
    return groups


def scan_dicom(source):
    """Inventory MR series in a local directory; read headers without pixel decoding.

    Returns a list of opaque series_id, file_count, manufacturer, candidate kind
    ('bold', 't1w', 'unknown'), TR seconds and dimensions. Hints are not proof of
    contrast/task; caller chooses one BOLD and its corresponding T1. Free-text
    descriptions, patient names, IDs, dates and DICOM UIDs are not returned.
    Series are grouped by Study/Series UID and echo; source files remain untouched.
    DICOM parsing failures propagate except non-DICOM/EOF files, which are skipped.
    """
    result = []
    for key, entries in _headers(source).items():
        d = entries[0][1]
        tr = float(d.RepetitionTime)/1000 if d.get("RepetitionTime") else None
        text = str(d.get("SeriesDescription", "")).lower() + str(d.get("ProtocolName", "")).lower()
        hint = "bold" if "bold" in text or "fmri" in text else "t1w" if "t1" in text else "unknown"
        result.append({"series_id": key, "file_count": len(entries), "candidate": hint,
                       "manufacturer": str(d.get("Manufacturer", "unknown")), "t_r": tr,
                       "rows": int(d.Rows), "columns": int(d.Columns)})
    return result


def _seconds(value):
    value = str(value)
    if len(value) < 6:
        raise InputError("Full HHMMSS slice acquisition times are required.")
    return int(value[:2])*3600 + int(value[2:4])*60 + float(value[4:])


def _timings(sequence):
    times = np.asarray([_seconds(d.AcquisitionTime) for d in sequence], dtype=float)
    # One volume can cross midnight. Unwrap relative to its earliest acquisition.
    if times.max() - times.min() > 43200:
        times[times < 43200] += 86400
    return times - times.min()


def _uih_mosaic(datasets):
    """Decode checked UIH VFRAME mosaics in their explicit per-slice geometry."""
    datasets = sorted(datasets, key=lambda d: int(d.TemporalPositionIdentifier))
    ids = [int(d.TemporalPositionIdentifier) for d in datasets]
    if ids != list(range(1, len(ids) + 1)):
        raise InputError("UIH mosaic temporal positions are missing, duplicated or nonconsecutive.")
    first = datasets[0]
    n = int(first[(0x65, 0x1050)].value)
    seq = first[(0x65, 0x1051)].value
    if n < 2 or len(seq) != n or str(first.get((0x65, 0x10), "").value) != "Image Private Header":
        raise InputError("Unsupported UIH private mosaic layout.")
    nc = math.ceil(math.sqrt(n))
    nr = math.ceil(n / nc)
    rows, cols = int(first.Rows), int(first.Columns)
    if rows % nr or cols % nc:
        raise InputError("UIH mosaic tiles do not evenly divide the pixel grid.")
    h, w = rows // nr, cols // nc
    positions = np.asarray([d.ImagePositionPatient for d in seq], dtype=float)
    step = (positions[-1] - positions[0])/(n-1)
    if not np.allclose(positions, positions[0] + np.arange(n)[:, None]*step, atol=.002):
        raise InputError("UIH slice positions are not a regular grid.")
    orientation = np.asarray(first.ImageOrientationPatient, dtype=float).reshape(2, 3)
    spacing = np.asarray(first.PixelSpacing, dtype=float)
    affine = np.eye(4)
    affine[:3, 0] = orientation[0]*spacing[1]
    affine[:3, 1] = orientation[1]*spacing[0]
    affine[:3, 2] = step
    affine[:3, 3] = positions[0]
    affine = np.diag([-1., -1., 1., 1.]) @ affine
    timings = _timings(seq)
    tr = float(first.RepetitionTime)/1000
    if np.any(timings >= tr):
        raise InputError("UIH slice times extend outside a repetition interval.")
    array = np.empty((w, h, n, len(datasets)), dtype="float32")
    for frame, d in enumerate(datasets):
        this = d[(0x65, 0x1051)].value
        if (int(d.Rows), int(d.Columns), int(d[(0x65, 0x1050)].value)) != (rows, cols, n):
            raise InputError("UIH mosaic dimensions change within a run.")
        if (not np.allclose(np.asarray(d.ImageOrientationPatient).reshape(2, 3), orientation, atol=1e-5)
            or not np.allclose(d.PixelSpacing, spacing, atol=1e-5)
            or not np.allclose([x.ImagePositionPatient for x in this], positions, atol=.002)
            or not np.allclose(_timings(this), timings, atol=.002, rtol=0)):
            raise InputError("UIH mosaic geometry or relative slice times change within a run.")
        if int(d.get("NumberOfTemporalPositions", len(datasets))) != len(datasets):
            raise InputError("UIH run is incomplete according to NumberOfTemporalPositions.")
        pixels = d.pixel_array.astype("float32")
        pixels = pixels * float(d.get("RescaleSlope", 1)) + float(d.get("RescaleIntercept", 0))
        for k in range(n):
            r, c = divmod(k, nc)
            array[:, :, k, frame] = pixels[r*h:(r+1)*h, c*w:(c+1)*w].T
    image = nib.Nifti1Image(array, affine)
    image.header.set_xyzt_units("mm", "sec")
    image.header.set_zooms((*np.linalg.norm(affine[:3, :3], axis=0), tr))
    image.header.set_dim_info(slice=2)
    return image, {"SliceTiming": timings.tolist(), "SliceEncodingDirection": "k",
                   "TimingSource": "UIH (0065,1051) per-slice AcquisitionTime, relative to volume onset"}


def convert_dicom_python(source, output, *, series_id=None, kind="bold"):
    """Convert ONE selected DICOM series to image.nii.gz and a minimal acquisition JSON.

    source is a local directory, output a new directory outside the source tree.
    series_id comes from scan_dicom; None requires exactly one MR series. kind is
    'bold' (4D >=20 frames) or 't1w' (3D). Uses dicom2nifti for supported standard
    MR layouts; UIH mosaics use explicit private per-slice position/time records.
    Geometry validators remain enabled; unsupported layouts fail, never guess.
    Returns {'image', 'sidecar', 'shape', 'engine'} with absolute file paths.

    Standard EchoTime (0018,0081) and RepetitionTime (0018,0080) are read in ms and
    written in seconds; conflicts within a selected series are errors. Generic
    layouts without validated slice times omit SliceTiming, requiring explicit
    skip or a reviewed JSON before preprocessing. No patient/date/free-text fields
    are copied. Images can still identify anatomy: conversion IS NOT defacing or
    a privacy certification. Original DICOM is never modified.
    """
    import pydicom
    from dicom2nifti.convert_dicom import dicom_array_to_nifti

    if kind not in {"bold", "t1w"}:
        raise InputError("DICOM kind must be bold or t1w.")
    src, dest = Path(source).resolve(), Path(output).expanduser().resolve()
    if src == dest or src in dest.parents or dest in src.parents:
        raise InputError("DICOM output must be outside and separate from the source tree.")
    if dest.exists():
        raise FileExistsError("DICOM conversion requires a new directory.")
    groups = _headers(source)
    if series_id is None:
        if len(groups) != 1:
            raise InputError("Select one series_id from scan_dicom; multiple series found.")
        series_id = next(iter(groups))
    if series_id not in groups:
        raise InputError("Selected series is no longer present in the source.")
    datasets = [pydicom.dcmread(p) for p, _ in groups[series_id]]
    sop = [str(d.SOPInstanceUID) for d in datasets]
    if len(set(sop)) != len(sop):
        raise InputError("Duplicate DICOM SOP instances in the selected series.")
    meta = {}
    for name in ("RepetitionTime", "EchoTime"):
        values = [float(d.get(name)) for d in datasets if d.get(name) is not None]
        if values:
            if len(values) != len(datasets) or not np.isfinite(values).all() or not np.allclose(values, values[0]):
                raise InputError(f"Inconsistent {name} in selected DICOM series.")
            meta[name] = values[0]/1000
    first = datasets[0]
    if str(first.get("Manufacturer", "")).upper() == "UIH" and (0x65, 0x1051) in first:
        image, timing = _uih_mosaic(datasets)
        meta.update(timing)
        engine = "BrainFC UIH explicit mosaic geometry"
    else:
        converted = dicom_array_to_nifti(datasets, None, reorient_nifti=False)
        image = converted["NII"]
        engine = "dicom2nifti"
    expected = 4 if kind == "bold" else 3
    if len(image.shape) != expected or (kind == "bold" and image.shape[-1] < 20):
        raise InputError(f"Converted series is not a valid {kind} image: {image.shape}.")
    data = image.get_fdata(dtype=np.float32)
    if not np.isfinite(data).all():
        raise InputError("Converted DICOM pixels contain nonfinite values.")
    fresh = nib.Nifti1Image(data, image.affine)
    fresh.header.set_xyzt_units("mm", "sec")
    if kind == "bold":
        if not meta.get("RepetitionTime"):
            raise InputError("Cannot obtain a validated TR for this DICOM layout; supply reviewed NIfTI/JSON.")
        fresh.header.set_zooms((*image.header.get_zooms()[:3], meta["RepetitionTime"]))
    fresh.header.set_dim_info(slice=image.header.get_dim_info()[2])
    meta.update({"ConversionSoftware": engine, "Privacy": "Metadata minimized; anatomy NOT anonymized"})
    dest.mkdir(parents=True)
    path = dest / "image.nii.gz"
    nib.save(fresh, path)
    sidecar = dest / "image.json"
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # Hashes establish original-byte provenance without copying identifiers.
    records = [{"sha256": sha256(p.read_bytes()).hexdigest()} for p, _ in groups[series_id]]
    (dest / "source_hashes.json").write_text(json.dumps(records), encoding="utf-8")
    return {"image": str(path), "sidecar": str(sidecar), "shape": list(image.shape), "engine": engine}
