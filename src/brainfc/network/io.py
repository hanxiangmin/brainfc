"""Safe local brain-array import with explicit ROI and matrix provenance.

Columns in ``roi_columns`` refer to the numeric array *after* named AFNI helper
columns have been removed. A slice is zero based and stop exclusive. MATLAB
v7.3 arrays are restored to MATLAB's orientation; time series are always T x R.
No atlas is inferred from an array's dimensions.
"""
from __future__ import annotations

import csv
import hashlib
import re
from itertools import chain
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import h5py
import numpy as np
from scipy.io import loadmat, whosmat

from .types import BrainDataset, ValidationError

MAX_ROIS = 1000
MAX_TIMEPOINTS = 100000
MAX_CELLS = 5000000
MAX_FILE_BYTES = 256 * 1024 * 1024
PRESETS = ("generic", "abide1", "abide2", "adhd", "mdd", "adni")
_FORMATS = {".csv", ".tsv", ".txt", ".1d", ".npy", ".npz", ".mat"}
_HELPERS = {"file", "subbrick"}
_KINDS = {"fc": "connectivity", "matrix": "connectivity", "time_series": "timeseries"}


def _path(path: str | Path) -> Path:
    path = Path(path)
    if not path.is_file():
        raise ValidationError("Input file does not exist or is not a regular file.")
    if path.suffix.lower() not in _FORMATS:
        raise ValidationError("Supported formats: CSV, TSV, TXT, 1D, NPY, NPZ and MAT.")
    if path.stat().st_size == 0:
        raise ValidationError("Input file is empty.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValidationError("Input file exceeds the 256 MiB local upload limit.")
    return path


def _numeric(value: str) -> bool:
    try:
        float(value)
        return bool(value.strip())
    except ValueError:
        return False


def _helper(value: str) -> bool:
    return re.sub(r"[\s_\-]", "", value.strip().lower()) in _HELPERS


def _read_text(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    def meaningful_lines(stream):
        emitted = False
        for line in stream:
            content = line.rstrip("\r\n")
            stripped = content.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                candidate = stripped.lstrip("#").strip()
                if not emitted and re.search(r"\b(?:File|Sub-brick)\b", candidate, re.I):
                    emitted = True
                    yield candidate
                continue
            emitted = True
            yield content

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            lines = meaningful_lines(stream)
            first_line = next(lines, None)
            if first_line is None:
                raise ValidationError("Input contains no data rows.")
            delimiter = "\t" if "\t" in first_line else "," if "," in first_line else None

            def parse_line(line):
                return [cell.strip() for cell in next(csv.reader([line], delimiter=delimiter))] if delimiter else line.split()

            first = parse_line(first_line)
            if any(not cell for cell in first):
                raise ValidationError("First row contains an empty cell; provide complete numeric values or nonempty column headers.")
            header = first if any(not _numeric(cell) for cell in first) else None
            width = len(first)
            keep = [i for i in range(width) if not header or not _helper(header[i])]
            if not keep:
                raise ValidationError("Input contains only auxiliary columns, no ROI values.")
            rows = (parse_line(line) for line in lines)
            if not header:
                rows = chain([first], rows)
            parsed = []
            for row_number, row in enumerate(rows, start=2 if header else 1):
                if len(parsed) >= MAX_TIMEPOINTS or (len(parsed) + 1) * width > MAX_CELLS:
                    raise ValidationError("Input exceeds 100000 rows or 5000000 numeric cells.")
                if len(row) != width:
                    raise ValidationError(f"Row {row_number} has {len(row)} columns; expected {width}.")
                try:
                    parsed.append([float(row[i]) for i in keep])
                except ValueError as exc:
                    raise ValidationError(f"Row {row_number} contains nonnumeric ROI values.") from exc
    except UnicodeDecodeError as exc:
        raise ValidationError("Text input must use UTF-8 encoding.") from exc
    if not parsed:
        raise ValidationError("Input has a header but no data rows.")
    info = {
        "column_labels": [header[i] for i in keep] if header else [],
        "discarded_columns": [header[i] for i in range(width) if i not in keep] if header else [],
        "header_detected": bool(header),
        "numeric_column_indexing": "zero-based after removal of named helper columns",
    }
    return np.asarray(parsed, dtype=float), info


def _check_array_header(shape, dtype) -> None:
    if len(shape) != 2 or np.dtype(dtype).kind not in "iuf":
        raise ValidationError("Select a two-dimensional real numeric array; objects and complex arrays are unsupported.")
    if np.prod(shape, dtype=np.int64) > MAX_CELLS or max(shape, default=0) > MAX_TIMEPOINTS:
        raise ValidationError("Array exceeds 5000000 cells or 100000 entries on one axis.")


def _npy_header(stream):
    version = np.lib.format.read_magic(stream)
    if version == (1, 0):
        shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
    elif version in {(2, 0), (3, 0)}:
        shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
    else:
        raise ValidationError("Unsupported NPY format version.")
    _check_array_header(shape, dtype)
    return {"shape": list(shape), "dtype": str(dtype)}


def _variables(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv", ".txt", ".1d"}:
        array, info = _read_text(path)
        return [{"name": "data", "shape": list(array.shape), "dtype": str(array.dtype)}], info
    if suffix == ".npy":
        with path.open("rb") as stream:
            return [{"name": "data", **_npy_header(stream)}], {}
    if suffix == ".npz":
        variables = []
        with ZipFile(path) as archive:
            members = archive.infolist()
            if sum(item.file_size for item in members) > MAX_FILE_BYTES:
                raise ValidationError("NPZ expanded size exceeds 256 MiB.")
            for member in members:
                if member.filename.endswith(".npy"):
                    with archive.open(member) as stream:
                        variables.append({"name": member.filename[:-4], **_npy_header(stream)})
        if len({item["name"] for item in variables}) != len(variables):
            raise ValidationError("NPZ contains duplicate variable names.")
        return variables, {}
    if h5py.is_hdf5(path):
        variables = []
        with h5py.File(path, "r") as file:
            for name in file:
                if name.startswith("#") or not isinstance(file.get(name, getlink=True), h5py.HardLink):
                    continue
                item = file[name]
                if isinstance(item, h5py.Dataset) and item.ndim == 2 and item.dtype.kind in "iuf":
                    if item.is_virtual or item.external:
                        raise ValidationError("MAT arrays referencing external storage are unsupported; upload a self-contained array.")
                    shape = item.shape[::-1] if "MATLAB_class" in item.attrs else item.shape
                    _check_array_header(shape, item.dtype)
                    variables.append({"name": name, "shape": list(shape), "dtype": str(item.dtype)})
        return variables, {"matlab_version": "7.3"}
    variables = []
    numeric_classes = {"double", "single", "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64"}
    for name, shape, class_name in whosmat(path):
        if len(shape) == 2 and class_name in numeric_classes:
            _check_array_header(shape, "float64")
            variables.append({"name": name, "shape": list(shape), "dtype": class_name})
    return variables, {"matlab_version": "5-7.2"}


def _suggestion(name: str, shape: list[int]) -> tuple[str, str]:
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    if "fisher" in normalized:
        return "connectivity", "fisher_z"
    if "roisignal" in normalized or "timeseries" in normalized or "timecourse" in normalized:
        return "timeseries", "correlation"
    if "covariance" in normalized:
        return "connectivity", "covariance"
    if "correlation" in normalized or "connectivity" in normalized:
        return "connectivity", "correlation"
    return ("connectivity" if shape[0] == shape[1] else "timeseries"), "correlation"


def _array_suggestion(filename: str, variable: str, shape: list[int]) -> tuple[str, str]:
    # Semantic variable names are stronger evidence than their container name.
    normalized = re.sub(r"[^a-z0-9]", "", variable.lower())
    terms = ("fisher", "roisignal", "timeseries", "timecourse", "covariance", "correlation", "connectivity")
    return _suggestion(variable if any(term in normalized for term in terms) else filename, shape)


def _metadata_array(filename: str, variable: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", variable.lower())
    if normalized == "data":
        normalized = re.sub(r"[^a-z0-9]", "", filename.lower())
    return normalized in {"coordinates", "roicoordinates", "roilabels", "labels", "atlaslabels"} or any(
        term in normalized for term in ("roicenter", "roicentre", "centerofmass", "centreofmass")
    )


def _source_name(path: Path, supplied: str | None) -> str:
    name = path.name if supplied is None else str(supplied).replace("\\", "/").rsplit("/", 1)[-1]
    if not name.strip() or name in {".", ".."}:
        raise ValidationError("Source filename must be a nonempty basename.")
    return name


def inspect_file(path: str | Path, source_name: str | None = None) -> dict[str, Any]:
    """Return array candidates and nonbinding parsing suggestions, without paths."""
    path = _path(path)
    name = _source_name(path, source_name)
    try:
        variables, info = _variables(path)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Cannot read {name}: invalid or unsupported file contents.") from exc
    if not variables:
        raise ValidationError("No two-dimensional real numeric variables were found.")
    chosen = variables[0] if len(variables) == 1 else None
    kind, matrix_kind = _array_suggestion(Path(name).stem, chosen["name"], chosen["shape"]) if chosen else ("auto", "auto")
    if chosen and (path.suffix.lower() == ".1d" or info.get("discarded_columns")):
        kind, matrix_kind = "timeseries", "correlation"
    warnings = []
    if chosen and _metadata_array(Path(name).stem, chosen["name"]):
        kind, matrix_kind = "auto", "auto"
        warnings.append("This variable contains ROI coordinate/label metadata, not functional connectivity or ROI time series.")
    if not chosen:
        warnings.append("Multiple numeric variables: explicitly choose the array to analyze.")
    if chosen and chosen["shape"][0] == chosen["shape"][1]:
        warnings.append("Square shape alone does not establish a connectivity matrix; confirm the input kind.")
    if chosen and chosen["shape"][1] > MAX_ROIS:
        warnings.append("More than 1000 original columns: explicitly select and document ROI columns.")
    if info.get("discarded_columns"):
        warnings.append("Named auxiliary columns removed: " + ", ".join(info["discarded_columns"]))
    return {
        "name": name, "format": path.suffix.lower().lstrip("."), "variables": variables,
        "suggested_kind": kind, "suggested_variable": chosen["name"] if chosen else None,
        "suggested_matrix_kind": matrix_kind, "warnings": warnings, **info,
    }


def _columns(selection, count: int) -> list[int]:
    if isinstance(selection, str):
        if not re.fullmatch(r"\d*:\d*(?::[1-9]\d*)?", selection.strip()):
            raise ValidationError("ROI slice must be zero-based start:stop[:positive_step], for example 0:116.")
        parts = [int(value) if value else None for value in selection.strip().split(":")]
        start, stop = parts[0], parts[1]
        if (start is not None and start >= count) or (stop is not None and stop > count):
            raise ValidationError(f"ROI slice exceeds the available {count} columns.")
        result = list(range(count))[slice(*parts)]
    elif isinstance(selection, (list, tuple)):
        if any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) for value in selection):
            raise ValidationError("ROI columns must be a list of zero-based integer indices.")
        result = [int(value) for value in selection]
    else:
        raise ValidationError("ROI columns must be a list of indices or a slice string.")
    if not result or len(result) != len(set(result)) or any(value < 0 or value >= count for value in result):
        raise ValidationError("ROI columns must be nonempty, unique and within the available column range.")
    return result


def load_data(
    path: str | Path, kind: str = "auto", variable: str | None = None,
    roi_columns: list[int] | str | None = None, matrix_kind: str = "auto",
    roi_ids=None, labels=None, coordinates=None, metadata=None, preset: str = "generic",
    source_name: str | None = None,
) -> BrainDataset:
    """Read a numeric file and validate it, preserving input scale and ROI order.

    Fisher-z values are never guessed from their range and are never silently
    converted here. Select ``matrix_kind='fisher_z'`` or use a named FisherZ MAT
    variable; the analysis layer performs the recorded inverse transform.
    """
    path = _path(path)
    name = _source_name(path, source_name)
    if preset.lower() not in PRESETS:
        raise ValidationError(f"Unknown preset; choose one of {PRESETS}.")
    kind = _KINDS.get(kind, kind)
    if kind not in {"auto", "connectivity", "timeseries"}:
        raise ValidationError("kind must be auto, connectivity or timeseries.")
    if matrix_kind not in {"auto", "correlation", "fisher_z", "covariance"}:
        raise ValidationError("matrix_kind must be auto, correlation, fisher_z or covariance.")
    inspection = inspect_file(path, source_name=name)
    names = [item["name"] for item in inspection["variables"]]
    if variable is None:
        if len(names) != 1:
            raise ValidationError("Multiple numeric variables require explicit variable selection: " + ", ".join(names))
        variable = names[0]
    if variable not in names:
        raise ValidationError(f"Unknown numeric variable {variable!r}; choose from {', '.join(names)}.")
    selected_info = next(item for item in inspection["variables"] if item["name"] == variable)
    if _metadata_array(Path(name).stem, variable):
        raise ValidationError("Selected variable is ROI coordinate/label metadata; supply it through ROI metadata, not as a functional input.")
    source_kind, source_matrix_kind = _array_suggestion(Path(name).stem, variable, selected_info["shape"])
    afni_timeseries = path.suffix.lower() == ".1d" or bool(inspection.get("discarded_columns"))
    if afni_timeseries:
        source_kind, source_matrix_kind = "timeseries", "correlation"
    text_info = {}
    try:
        suffix = path.suffix.lower()
        if suffix in {".csv", ".tsv", ".txt", ".1d"}:
            array, text_info = _read_text(path)
        elif suffix == ".npy":
            array = np.load(path, allow_pickle=False)
        elif suffix == ".npz":
            with np.load(path, allow_pickle=False) as archive:
                array = archive[variable]
        elif h5py.is_hdf5(path):
            with h5py.File(path, "r") as file:
                item = file[variable]
                array = item[...]
                if "MATLAB_class" in item.attrs:
                    array = array.T
        else:
            array = loadmat(path, variable_names=[variable])[variable]
        _check_array_header(array.shape, array.dtype)
        array = np.asarray(array, dtype=float)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Cannot load numeric variable {variable!r} from {name}.") from exc
    if kind == "auto":
        kind = source_kind
        generic_name = re.sub(r"[^a-z0-9]", "", f"{Path(name).stem}{variable}".lower())
        known = afni_timeseries or any(term in generic_name for term in ("fisher", "correlation", "covariance", "connectivity", "roisignal", "timeseries", "timecourse"))
        if not known and array.shape[0] == array.shape[1] and not np.allclose(array, array.T, equal_nan=True):
            raise ValidationError("Square nonsymmetric data is ambiguous; explicitly choose timeseries or correct the connectivity matrix.")
    if matrix_kind == "auto":
        matrix_kind = source_matrix_kind if kind == "connectivity" else "correlation"
    if kind == "connectivity" and matrix_kind == "correlation" and source_matrix_kind == "fisher_z":
        raise ValidationError("Source is named FisherZ: declare fisher_z or explicitly convert it before loading as correlation.")
    if kind == "connectivity" and array.shape[0] != array.shape[1]:
        raise ValidationError("Connectivity input must be square before ROI selection.")
    original_shape = list(array.shape)
    if roi_columns is None and (array.shape[1] > MAX_ROIS or preset.lower() == "mdd"):
        raise ValidationError("MDD preset and inputs with more than 1000 columns require explicit ROI-column selection and a documented atlas mapping.")
    indices = _columns(roi_columns, array.shape[1]) if roi_columns is not None else list(range(array.shape[1]))
    array = array[np.ix_(indices, indices)] if kind == "connectivity" else array[:, indices]
    replaced_diagonal = 0
    if kind == "connectivity" and matrix_kind == "fisher_z":
        replaced_diagonal = int((~np.isfinite(np.diag(array))).sum())
        if replaced_diagonal:
            diagonal = np.diag(array).copy()
            diagonal[~np.isfinite(diagonal)] = 0.0
            np.fill_diagonal(array, diagonal)
    column_labels = text_info.get("column_labels", [])
    inferred_labels = [column_labels[index] for index in indices] if column_labels else []
    if roi_ids is None and inferred_labels and len(set(inferred_labels)) == len(inferred_labels):
        roi_ids = inferred_labels
    info = dict(metadata or {})
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    info.update({
        "source_name": name, "source_sha256": digest, "source_format": inspection["format"],
        "source_variable": variable, "source_shape": original_shape,
        "roi_columns": indices, "preset": preset.lower(), "matrix_kind": matrix_kind,
        **text_info,
    })
    if replaced_diagonal:
        info["nonfinite_fisher_z_diagonal_replaced"] = replaced_diagonal
        info["diagonal_policy"] = "Undefined Fisher-z self-connections set to zero on the in-memory copy; off-diagonal values unchanged."
    dataset = BrainDataset(
        data=array, kind=kind, matrix_kind=matrix_kind, roi_ids=list(roi_ids) if roi_ids is not None else [],
        labels=list(labels) if labels is not None else inferred_labels, coordinates=coordinates, metadata=info,
    )
    dataset.warnings = validate_dataset(dataset)
    if replaced_diagonal:
        dataset.warnings.append(f"{replaced_diagonal} non-finite Fisher-z diagonal self-connections were set to zero in memory; source file unchanged.")
    if text_info.get("discarded_columns"):
        dataset.warnings.append("Named auxiliary columns removed: " + ", ".join(text_info["discarded_columns"]))
    return dataset


def validate_dataset(dataset: BrainDataset) -> list[str]:
    """Validate scientific shape/scale contracts; return nonblocking metadata gaps."""
    array = np.asarray(dataset.data)
    if array.ndim != 2 or array.dtype.kind not in "iuf" or 0 in array.shape:
        raise ValidationError("Data must be a nonempty two-dimensional real numeric array.")
    if array.size > MAX_CELLS or array.shape[0] > MAX_TIMEPOINTS or array.shape[1] > MAX_ROIS:
        raise ValidationError("Resource limit: 1000 ROIs, 100000 timepoints and 5000000 cells.")
    if array.shape[1] < 2:
        raise ValidationError("At least two ROI columns are required.")
    nonfinite = ~np.isfinite(array)
    ignored_fisher_diagonal = 0
    if dataset.kind == "connectivity" and dataset.matrix_kind == "fisher_z" and array.shape[0] == array.shape[1]:
        ignored_fisher_diagonal = int(np.diag(nonfinite).sum())
        np.fill_diagonal(nonfinite, False)
    if nonfinite.any():
        row, column = np.argwhere(nonfinite)[0]
        raise ValidationError(f"Non-finite value at zero-based row {row}, column {column}; correct missing/invalid values explicitly.")
    if dataset.kind not in {"connectivity", "timeseries"}:
        raise ValidationError("Dataset kind must be connectivity or timeseries.")
    if dataset.matrix_kind not in {"correlation", "fisher_z", "covariance"}:
        raise ValidationError("Matrix kind must be correlation, fisher_z or covariance.")
    if dataset.kind == "timeseries" and dataset.matrix_kind != "correlation":
        raise ValidationError("Fisher-z/covariance matrix kinds apply to connectivity inputs, not raw ROI time series.")
    n_rois = array.shape[1]
    if len(dataset.roi_ids) != n_rois or any(not str(value).strip() for value in dataset.roi_ids):
        raise ValidationError("ROI IDs must be nonempty and match the selected ROI count.")
    if len(set(dataset.roi_ids)) != n_rois:
        raise ValidationError("ROI IDs must be unique.")
    if len(dataset.labels) != n_rois or any(not str(value).strip() for value in dataset.labels):
        raise ValidationError("ROI labels must be nonempty and match the selected ROI count.")
    warnings = []
    if ignored_fisher_diagonal:
        warnings.append("Non-finite Fisher-z diagonal self-connections are ignored by the inverse transform; off-diagonal values must remain finite.")
    if dataset.kind == "connectivity":
        if array.shape[0] != n_rois or not np.allclose(array, array.T, rtol=1e-5, atol=1e-8, equal_nan=True):
            raise ValidationError("Connectivity matrix must be square and symmetric.")
        if dataset.matrix_kind == "correlation" and np.max(np.abs(array)) > 1 + 1e-7:
            raise ValidationError("Correlation values must be in [-1, 1]; Fisher-z and covariance require their explicit matrix kind.")
        if dataset.matrix_kind == "covariance" and np.any(np.diag(array) <= 0):
            raise ValidationError("Covariance matrices require a strictly positive diagonal.")
    else:
        if array.shape[0] < 3:
            raise ValidationError("Time series require at least three timepoints.")
        constant = np.flatnonzero(np.ptp(array, axis=0) == 0)
        if len(constant):
            raise ValidationError(f"Constant ROI channels at zero-based columns {constant[:10].tolist()}; remove or correct them explicitly.")
        tr = dataset.metadata.get("tr", dataset.metadata.get("TR"))
        time = dataset.metadata.get("time_vector")
        if tr is not None and (isinstance(tr, bool) or not isinstance(tr, (float, int)) or not np.isfinite(tr) or tr <= 0):
            raise ValidationError("TR must be a positive finite number in seconds.")
        if time is not None:
            try:
                values = np.asarray(time, dtype=float)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Time vector must contain numeric seconds.") from exc
            if values.shape != (array.shape[0],) or not np.isfinite(values).all() or np.any(np.diff(values) <= 0):
                raise ValidationError("Time vector must have one finite strictly increasing value per timepoint.")
        if tr is None and time is None:
            warnings.append("TR/time vector is missing; only static connectivity is available.")
        if "censoring" not in dataset.metadata and "removed_frames" not in dataset.metadata:
            warnings.append("Frame censoring information was not supplied.")
    if dataset.coordinates is not None:
        coords = np.asarray(dataset.coordinates)
        if coords.shape != (n_rois, 3) or not np.isfinite(coords).all():
            raise ValidationError("Coordinates must contain one finite x,y,z row per selected ROI.")
        if not dataset.metadata.get("coordinate_space"):
            warnings.append("Coordinate space is missing; anatomical alignment is unavailable.")
    else:
        warnings.append("Anatomical coordinates were not supplied; abstract network and matrix views remain available.")
    if not dataset.metadata.get("atlas"):
        warnings.append("Atlas name/version and ROI mapping were not supplied; no atlas is inferred from dimensions.")
    if "gsr" not in dataset.metadata:
        warnings.append("Global-signal regression status was not supplied.")
    return warnings
