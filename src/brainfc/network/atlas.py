"""Versioned, local atlas registry. Geometry always uses NIfTI world coordinates.

An atlas is never inferred from a matrix dimension. Binding requires an explicit
ordered list of atlas ROI IDs, and produces a copy of the analysis result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import threading
from urllib.parse import urlsplit

import nibabel as nib
import numpy as np
import pandas as pd
from scipy import ndimage
from skimage.measure import marching_cubes

from .types import AnalysisResult, ValidationError

_LOCK = threading.RLock()
MAX_VOXELS = 32_000_000
BUILTINS = [
    {
        "id": "aal-spm12-116",
        "name": "AAL SPM12 · 116",
        "space": "MNIColin27",
        "version": "SPM12",
        "n_rois": 116,
    },
    {
        "id": "aal-spm12-90",
        "name": "AAL SPM12 · 90 (non-cerebellar subset)",
        "space": "MNIColin27",
        "version": "SPM12",
        "n_rois": 90,
    },
    *[
        {
            "id": f"schaefer-2018-{n}-7",
            "name": f"Schaefer 2018 · {n} / 7 networks",
            "space": "MNI152NLin6Asym",
            "version": "v0.14.3",
            "n_rois": n,
        }
        for n in (100, 200, 400)
    ],
]


@dataclass
class AtlasSpec:
    """Versioned atlas record produced by AtlasRegistry, rather than inferred from R.

    id/name/version/space identify the atlas; labels contains ordered ROI records
    including label_value and RAS+ coordinates. sources and license retain terms.
    affine/shape describe the source grid; sha256 records content and asset hashes.
    custom identifies a user atlas; schema_version is 1. This record alone does not
    verify spatial alignment or bind a matrix to its labels.
    """
    id: str
    name: str
    version: str
    space: str
    labels: list[dict]
    sources: list[str]
    license: str
    affine: list[list[float]]
    shape: list[int]
    sha256: dict[str, str]
    custom: bool = True
    schema_version: int = 1

    def to_dict(self):
        """Return atlas fields plus n_rois and installed=True for the local registry."""
        return {**asdict(self), "n_rois": len(self.labels), "installed": True}


def _digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _volume(path, *, labels=False):
    path = Path(path)
    if not (path.name.lower().endswith(".nii") or path.name.lower().endswith(".nii.gz")):
        raise ValidationError("Atlas/reference must be NIfTI (.nii or .nii.gz).")
    if path.stat().st_size > 128 * 1024**2:
        raise ValidationError("Atlas/reference exceeds 128 MiB.")
    try:
        img = nib.load(path)
        if len(img.shape) != 3 or min(img.shape) < 2 or np.prod(img.shape, dtype=np.int64) > MAX_VOXELS:
            raise ValidationError("Atlas/reference must be a 3-D volume of at most 32 million voxels.")
        if not np.isfinite(img.affine).all() or abs(np.linalg.det(img.affine[:3, :3])) < 1e-8:
            raise ValidationError("NIfTI affine is missing or singular.")
        if img.header.get_xyzt_units()[0] != "mm":
            raise ValidationError("NIfTI spatial units must explicitly be millimetres (mm).")
        q, qc = img.get_qform(coded=True)
        s, sc = img.get_sform(coded=True)
        if qc and sc and not np.allclose(q, s, atol=1e-3):
            raise ValidationError("Conflicting NIfTI qform and sform; resolve the spatial mapping first.")
        data = np.asarray(img.dataobj, dtype=np.float64 if labels else np.float32)
        if not np.isfinite(data).all():
            raise ValidationError("NIfTI contains non-finite values.")
        if labels:
            if np.any(data < 0) or not np.array_equal(data, np.rint(data)):
                raise ValidationError(
                    "Parcellation must contain nonnegative integer labels, not probabilities."
                )
            if data.max() > np.iinfo(np.int32).max:
                raise ValidationError("Parcellation labels must fit in a signed 32-bit integer.")
            ids = np.unique(data[data > 0])
            if not 1 <= len(ids) <= 1000:
                raise ValidationError("Parcellation must contain 1–1000 non-background regions.")
        elif not np.any(data > 0):
            raise ValidationError("Reference brain is empty.")
        return img, data
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Cannot read NIfTI: {exc}") from exc


def _labels(table):
    try:
        frame = (
            table.copy()
            if isinstance(table, pd.DataFrame)
            else pd.read_csv(table, sep=None, engine="python", dtype=str, keep_default_na=False)
        )
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        raise ValidationError(f"Cannot read label table: {exc}") from exc
    required = {"label_value", "roi_id", "abbreviation", "name", "hemisphere"}
    if not required <= set(frame.columns):
        raise ValidationError("Label table requires: label_value,roi_id,abbreviation,name,hemisphere.")
    records = []
    for row in frame.to_dict("records"):
        if any(pd.isna(row[k]) or not str(row[k]).strip() for k in required):
            raise ValidationError("Every ROI needs an ID, abbreviation, full name and hemisphere.")
        try:
            value = float(row["label_value"])
        except (ValueError, TypeError) as exc:
            raise ValidationError("label_value must be a positive integer.") from exc
        if not np.isfinite(value) or value != int(value) or not 0 < value <= np.iinfo(np.int32).max:
            raise ValidationError("label_value must be a positive integer (0 is background).")
        hemi = str(row["hemisphere"]).upper().strip()
        if hemi not in {"L", "R", "M", "B"}:
            raise ValidationError("hemisphere must be L, R, M (midline), or B (bilateral).")
        color = "" if pd.isna(row.get("color", "")) else str(row.get("color", "")).strip()
        if color and not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValidationError("Optional color must be a #RRGGBB hex color.")
        records.append(
            {
                "label_value": int(value),
                "roi_id": str(row["roi_id"]).strip(),
                "abbreviation": str(row["abbreviation"]).strip(),
                "name": str(row["name"]).strip(),
                "hemisphere": hemi,
                "network": "" if pd.isna(row.get("network", "")) else str(row.get("network", "")),
                "color": color,
            }
        )
    for key in ("label_value", "roi_id", "abbreviation"):
        if len({r[key] for r in records}) != len(records):
            raise ValidationError(
                f"Duplicate {key} in label table; hemisphere-specific abbreviations must be unique."
            )
    return records


def _surface(mask, affine, *, step=1):
    """Padded marching cubes; vertices remain in RAS+ millimetres."""
    points = np.argwhere(mask)
    if not len(points):
        return {"positions": [], "indices": []}
    lo = np.maximum(points.min(axis=0) - 1, 0)
    hi = np.minimum(points.max(axis=0) + 2, mask.shape)
    cut = mask[tuple(slice(a, b) for a, b in zip(lo, hi))]
    padded = np.pad(cut.astype(np.float32), 1)
    verts, faces, _, _ = marching_cubes(padded, 0.5, step_size=step, allow_degenerate=False)
    verts = nib.affines.apply_affine(affine, verts + lo - 1)
    if np.linalg.det(affine[:3, :3]) < 0:
        faces = faces[:, ::-1]
    # Gentle, symmetric smoothing for display only. Source label volume is immutable.
    from scipy.sparse import coo_matrix

    a = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]])
    b = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]])
    adj = coo_matrix(
        (np.ones(len(a) * 2), (np.r_[a, b], np.r_[b, a])), shape=(len(verts), len(verts))
    ).tocsr()
    degree = np.asarray(adj.sum(axis=1)).ravel().clip(1)
    for factor in (0.3, -0.31, 0.3, -0.31):
        verts += factor * (adj @ verts / degree[:, None] - verts)
    return {"positions": np.round(verts, 3).ravel().tolist(), "indices": faces.ravel().tolist()}


class AtlasRegistry:
    """Versioned local cache of parcellations, matched references and display meshes.

    root is an optional writable directory; None retains the legacy hicbrain
    platform-data atlas cache for compatibility. The unified GUI uses its own
    workspace/networks/atlases directory. Construction does not download assets.
    """
    def __init__(self, root=None):
        if root is None:
            from platformdirs import user_data_path

            root = user_data_path("hicbrain", appauthor=False) / "atlases"
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, atlas_id):
        if not isinstance(atlas_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}", atlas_id):
            raise ValidationError("Invalid atlas ID.")
        return self.root / atlas_id

    def list(self):
        """List builtin and imported atlas descriptors, including installation status."""
        catalog = {r["id"]: {**r, "installed": False, "custom": False} for r in BUILTINS}
        for path in sorted(self.root.glob("*/atlas.json")):
            spec = json.loads(path.read_text(encoding="utf-8"))
            catalog[spec["id"]] = {**spec, "installed": True}
        return list(catalog.values())

    def get(self, atlas_id):
        """Read an installed atlas descriptor; invalid/missing IDs raise ValidationError."""
        path = self._path(atlas_id) / "atlas.json"
        if not path.exists():
            raise ValidationError("Atlas is not installed. Install or upload it first.")
        return json.loads(path.read_text(encoding="utf-8"))

    def asset(self, atlas_id, name):
        """Return an installed asset path, restricted to the five supported filenames.

        name: geometry.json, parcellation.nii.gz, reference.nii.gz, labels.tsv or
        atlas.json. Invalid atlas IDs/asset names raise ValidationError.
        """
        self.get(atlas_id)
        if name not in {
            "geometry.json",
            "parcellation.nii.gz",
            "reference.nii.gz",
            "labels.tsv",
            "atlas.json",
        }:
            raise ValidationError("Unknown atlas asset.")
        return self._path(atlas_id) / name

    def import_atlas(
        self,
        parcellation,
        labels,
        *,
        name,
        space,
        reference,
        version="custom-1",
        sources=None,
        license="User supplied; retain original terms",
        atlas_id=None,
        custom=True,
        space_confirmed=False,
    ):
        """Validate and copy a custom parcellation with a matching reference.

        parcellation/reference are 3D NIfTI paths (<=128 MiB each); labels is a
        CSV/TSV path or DataFrame with roi_id, label_value, name, hemisphere,
        abbreviation and optional network/color. Positive integer label values must
        match the image exactly. name, exact space and reference are required.
        Caller must set space_confirmed=True after verifying alignment; resampling
        here only checks coverage and never registers anatomy. version, sources
        (HTTP(S) list), license and optional stable atlas_id describe provenance.
        custom=False is reserved for builtin installers. Returns a descriptor dict.
        Invalid labels/space/overlap or conflicting existing IDs raise ValidationError.
        Original files are preserved; equivalent cached content is reused.
        """
        if (
            not isinstance(name, str)
            or not isinstance(space, str)
            or not name.strip()
            or not space.strip()
            or space.lower() in {"unknown", "mni", "native"}
        ):
            raise ValidationError(
                "Give an atlas name and an exact named reference space (not generic MNI/native)."
            )
        if sources is not None and (
            not isinstance(sources, list)
            or any(
                not isinstance(url, str) or urlsplit(url).scheme not in {"http", "https"} for url in sources
            )
        ):
            raise ValidationError("Sources must be a list of HTTP(S) source URLs.")
        if not isinstance(version, str) or not version.strip():
            raise ValidationError("Atlas version must be a nonempty string.")
        if space_confirmed is not True:
            raise ValidationError(
                "Confirm that parcellation and reference are already aligned in the declared space; no registration is performed."
            )
        img, data = _volume(parcellation, labels=True)
        ref, refdata = _volume(reference)
        rows = _labels(labels)
        if {r["label_value"] for r in rows} != set(np.unique(data[data > 0]).astype(int)):
            raise ValidationError(
                "Label table and nonzero image labels must match exactly, including nonconsecutive IDs."
            )
        # Check world-space overlap, not equal voxel sizes. Resampling does NOT register anatomy.
        from nibabel.processing import resample_from_to

        reference_on_atlas = np.asarray(resample_from_to(ref, img, order=1).dataobj)
        nonzero = data > 0
        if np.mean(reference_on_atlas[nonzero] > 0) < 0.95:
            raise ValidationError(
                "Atlas and reference have insufficient world-space overlap; verify space and affine."
            )
        for row in rows:
            voxels = np.argwhere(data == row["label_value"])
            # Representative voxel nearest the centroid stays inside this parcel.
            centroid = voxels.mean(axis=0)
            point = voxels[np.argmin(np.sum((voxels - centroid) ** 2, axis=1))]
            row["coordinates"] = nib.affines.apply_affine(img.affine, point).tolist()
            if space in {"MNIColin27", "MNI152NLin6Asym"}:
                x = float(nib.affines.apply_affine(img.affine, centroid)[0])
                if (row["hemisphere"] == "L" and x > 2) or (row["hemisphere"] == "R" and x < -2):
                    raise ValidationError(
                        f"Hemisphere for {row['roi_id']} contradicts its MNI RAS+ location; verify labels and affine."
                    )
        digest = hashlib.sha256(
            (
                _digest(parcellation)
                + _digest(reference)
                + json.dumps(rows, sort_keys=True)
                + str(space)
                + str(version)
            ).encode()
        ).hexdigest()
        atlas_id = atlas_id or "custom-" + digest[:20]
        target = self._path(atlas_id)
        with _LOCK:
            if (target / "atlas.json").exists():
                existing = self.get(atlas_id)
                if existing["sha256"]["content"] != digest:
                    raise ValidationError(
                        "Atlas ID already exists with different content; use a new ID/version."
                    )
                return existing
            with tempfile.TemporaryDirectory(prefix="atlas-", dir=self.root) as temp:
                stage = Path(temp)
                nib.save(img, stage / "parcellation.nii.gz")
                nib.save(ref, stage / "reference.nii.gz")
                pd.DataFrame(rows).drop(columns="coordinates").to_csv(
                    stage / "labels.tsv", sep="\t", index=False
                )
                brainmask = ndimage.binary_fill_holes(refdata > 0)
                geometry = {
                    "space": space,
                    "units": "mm",
                    "orientation": "RAS+",
                    "brain": _surface(brainmask, ref.affine, step=2),
                    "parcels": {},
                }
                for row in rows:
                    geometry["parcels"][row["roi_id"]] = _surface(data == row["label_value"], img.affine)
                (stage / "geometry.json").write_text(
                    json.dumps(geometry, separators=(",", ":")), encoding="utf-8"
                )
                spec = AtlasSpec(
                    atlas_id,
                    str(name),
                    str(version),
                    str(space),
                    rows,
                    list(sources or []),
                    str(license),
                    img.affine.tolist(),
                    list(img.shape),
                    {
                        "content": digest,
                        "parcellation": _digest(stage / "parcellation.nii.gz"),
                        "reference": _digest(stage / "reference.nii.gz"),
                    },
                    custom=custom,
                ).to_dict()
                spec["geometry_notes"] = (
                    "RAS+ mm; representative voxel inside each ROI; lightly smoothed marching-cubes display surfaces. Source segmentation preserved. Space alignment declared by source/uploader, not established by registration."
                )
                (stage / "atlas.json").write_text(
                    json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                target.mkdir(exist_ok=True)
                for file in stage.iterdir():
                    shutil.copy2(file, target / file.name)
            return spec

    def bind(self, result, atlas_id, ordered_roi_ids, *, confirmed=False):
        """Copy a result with an explicitly confirmed, ordered atlas mapping.

        result is AnalysisResult or its serialized dictionary; atlas_id must be
        installed. ordered_roi_ids supplies exactly one distinct known atlas ID
        per matrix row; confirmed=True is mandatory. Returns AnalysisResult with
        ROI metadata, coordinates and atlas hashes. No reparcellation or matrix
        reordering occurs. Changing an existing binding raises ValidationError.
        """
        if not confirmed:
            raise ValidationError(
                "Explicitly confirm the matrix ROI order; shape alone cannot identify an atlas."
            )
        spec = self.get(atlas_id)
        result = AnalysisResult.from_dict(
            result.to_dict() if isinstance(result, AnalysisResult) else copy.deepcopy(result)
        )
        lookup = {r["roi_id"]: r for r in spec["labels"]}
        if not isinstance(ordered_roi_ids, list) or len(ordered_roi_ids) != len(result.roi_ids):
            raise ValidationError("Provide one atlas ROI ID per matrix row, in the same order.")
        if (
            any(not isinstance(roi, str) for roi in ordered_roi_ids)
            or len(set(ordered_roi_ids)) != len(ordered_roi_ids)
            or not set(ordered_roi_ids) <= set(lookup)
        ):
            raise ValidationError("ROI mapping contains duplicates or unknown atlas IDs.")
        previous = result.metadata.get("atlas_binding")
        if previous and (previous["atlas_id"] != atlas_id or previous["ordered_roi_ids"] != ordered_roi_ids):
            raise ValidationError(
                "This result is already bound to a parcellation. Load the original unmapped result to correct a mapping; changing an atlas does not reparcellate a matrix."
            )
        mapped = [lookup[x] for x in ordered_roi_ids]
        result.labels = [r["abbreviation"] for r in mapped]
        result.coordinates = np.array([r["coordinates"] for r in mapped], dtype=float)
        result.metadata.update(
            {
                "anatomical_mapping": "atlas-bound",
                "atlas_verified": True,
                "atlas": spec["name"],
                "coordinate_space": spec["space"],
                "atlas_binding": {
                    "atlas_id": atlas_id,
                    "atlas_sha256": spec["sha256"]["content"],
                    "ordered_roi_ids": ordered_roi_ids,
                    "confirmed": True,
                },
                "roi_metadata": [{**r, "source_roi_id": roi} for r, roi in zip(mapped, result.roi_ids)],
            }
        )
        return result

    def install(self, atlas_id):
        """Fetch official assets explicitly, preserving their source terms locally."""
        from .atlas_sources import install_builtin

        return install_builtin(self, atlas_id)
