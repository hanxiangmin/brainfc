"""Memory-bounded volume extraction, CIFTI alignment and GIFTI parcellation."""

from __future__ import annotations

import nibabel as nib
import numpy as np
import pandas as pd
from nibabel.processing import resample_from_to
from .models import InputError


def roi_table(path):
    """Read and validate an optional CSV/TSV ROI mapping.

    Returns pandas.DataFrame, or None when path is None. Requires unique nonempty
    roi_id. Optional label_value must be unique finite integers; coordinates must
    include all of x/y/z with finite numeric values. Empty text is preserved.
    Exact correspondence to extracted labels is checked later by make_rois."""
    if path is None:
        return None
    frame = pd.read_csv(path, sep=None, engine="python", dtype={"roi_id": str}, keep_default_na=False)
    if "roi_id" not in frame or frame.roi_id.duplicated().any() or (frame.roi_id == "").any():
        raise InputError("ROI table requires unique, nonempty roi_id values.")
    if "label_value" in frame:
        vals = pd.to_numeric(frame.label_value, errors="raise")
        if not np.isfinite(vals).all() or not np.equal(vals, np.rint(vals)).all() or vals.duplicated().any():
            raise InputError("label_value must contain unique finite integers.")
        frame["label_value"] = vals.astype(int)
    if any(x in frame for x in ("x", "y", "z")):
        if (
            not all(x in frame for x in ("x", "y", "z"))
            or not np.isfinite(frame[["x", "y", "z"]].to_numpy(float)).all()
        ):
            raise InputError("ROI coordinates require finite x, y, z columns in the declared space (mm).")
    return frame


def make_rois(ids, names=None, coords=None, table=None, *, by_value=True):
    """Construct canonical ROI records in the supplied extraction order.

    Parameters
    ----------
    ids : sequence
        Actual integer label values when by_value=True, otherwise string IDs.
    names : sequence of str or None
        Fallback labels; defaults to 'ROI {value}'.
    coords : numpy.ndarray or None
        Fallback (R,3) coordinates in RAS+ mm.
    table : pandas.DataFrame or None
        Validated mapping; name, coordinates and metadata override fallbacks.
    by_value : bool, default True
        Match mapping on label_value, otherwise roi_id; exact ID set is required.

    Returns
    -------
    list[dict]
        roi_id, label_value, name, abbreviation, hemisphere, network, coordinates.
        For already-parcellated input, label_value is a 1-based ordinal.

    Raises
    ------
    InputError
        Missing/extra mapping IDs or duplicate final roi_id values.

    Notes
    -----
    Input mapping row order does not reorder results. Fallback hemisphere is based
    on x sign (L/R/M); without coordinates it is M, not an anatomical inference."""
    records = []
    if table is not None:
        column = "label_value" if by_value else "roi_id"
        if column not in table:
            raise InputError(f"ROI table requires {column} for this input.")
        available = set(table[column].tolist())
        if set(ids) != available:
            raise InputError(
                f"ROI mapping must exactly match extracted IDs; expected {list(ids)[:12]} (total {len(ids)})."
            )
        lookup = table.set_index(column, drop=False)
    else:
        lookup = None
    for i, value in enumerate(ids):
        row = lookup.loc[value].to_dict() if lookup is not None else {}
        name = str(row.get("name", names[i] if names is not None else f"ROI {value}"))
        xyz = (
            [float(row[a]) for a in ("x", "y", "z")]
            if all(a in row for a in ("x", "y", "z"))
            else (coords[i].tolist() if coords is not None else None)
        )
        record = {
            "roi_id": str(row.get("roi_id", value)),
            "label_value": int(value) if by_value else i + 1,
            "name": name,
            "abbreviation": str(row.get("abbreviation", name)),
            "hemisphere": str(
                row.get("hemisphere", "L" if xyz and xyz[0] < 0 else "R" if xyz and xyz[0] > 0 else "M")
            ),
            "network": str(row.get("network", "")),
            "coordinates": xyz,
        }
        records.append(record)
    if len({r["roi_id"] for r in records}) != len(records):
        raise InputError("ROI identifiers are not unique.")
    return records


def validate_volume(img, *, ndim=None):
    """Validate a NiBabel spatial image without resampling it.

    img must be a SpatialImage with finite invertible affine. Optional ndim checks
    exact dimension count. Requires mm/unknown units and consistent coded qform/
    sform (numpy.allclose atol=1e-3, default rtol). Returns None or raises InputError.
    When ndim=None, this helper does not independently restrict dimension count."""
    if not isinstance(img, nib.spatialimages.SpatialImage) or (ndim is not None and len(img.shape) != ndim):
        raise InputError(f"Expected a {ndim or '3/4'}D spatial image.")
    if (
        img.affine is None
        or not np.isfinite(img.affine).all()
        or abs(np.linalg.det(img.affine[:3, :3])) < 1e-10
    ):
        raise InputError("Image affine is missing, nonfinite or singular.")
    if hasattr(img.header, "get_xyzt_units") and img.header.get_xyzt_units()[0] not in {"mm", "unknown"}:
        raise InputError("Spatial image units must be mm; convert metre/micron images before use.")
    if hasattr(img, "get_qform"):
        q, qc = img.get_qform(coded=True)
        s, sc = img.get_sform(coded=True)
        if qc and sc and not np.allclose(q, s, atol=1e-3):
            raise InputError(
                "Conflicting qform/sform: resolve the image's spatial mapping before extraction."
            )


def label_values(data):
    """Return sorted positive integer ROI labels from a numeric array.

    Requires nonnegative, finite integer values; zero is background. Returns a
    1D integer numpy.ndarray with 2 to 2000 labels, otherwise raises InputError.
    Probabilistic atlases are not accepted."""
    if not np.isfinite(data).all() or np.any(data < 0) or not np.equal(data, np.rint(data)).all():
        raise InputError(
            "Atlas must contain nonnegative integer labels (0 is background), not probabilities."
        )
    ids = np.unique(data[data > 0]).astype(int)
    if not 2 <= len(ids) <= 2000:
        raise InputError("Atlas must contain 2–2000 non-background ROIs.")
    return ids


def volume_timeseries(img, atlas_path, mask_path=None, table=None):
    """Compute arithmetic ROI means on one 4D NiBabel volume.

    img is a loaded spatial image; atlas_path is a 3D integer-label filename.
    mask_path optionally restricts labels by positive mask values. table is an
    optional validated pandas ROI mapping. Atlas/mask are nearest-neighbor
    resampled to the BOLD grid; coordinate centroids use the original atlas.

    Returns (time_x_roi_array, roi_records, image_qc, aligned_atlas_image).
    QC includes voxel counts, resampling flag, orientation, shape and units.
    Reads BOLD in 8-frame slabs, casts slabs to float32 and accumulates means in
    float64. All original atlas ROIs must remain after resampling/masking.
    Raises InputError on geometry/coverage/nonfinite-ROI failures. This low-level
    function does not check named spaces, preprocessing status or temporal settings."""
    validate_volume(img, ndim=4)
    atlas = nib.load(atlas_path)
    validate_volume(atlas, ndim=3)
    original = np.asanyarray(atlas.dataobj)
    ids = label_values(original)
    grid = (img.shape[:3], img.affine)
    # Spatial resampling changes only the atlas grid. It is never registration.
    aligned = resample_from_to(atlas, grid, order=0)
    labels = np.asarray(aligned.dataobj, dtype=np.int32)
    if mask_path is not None:
        mask = nib.load(mask_path)
        validate_volume(mask, ndim=3)
        m = np.asarray(resample_from_to(mask, grid, order=0).dataobj)
        if not np.isfinite(m).all():
            raise InputError("Brain mask contains nonfinite values.")
        labels[m <= 0] = 0
    present = np.unique(labels[labels > 0])
    if not np.array_equal(ids, present):
        raise InputError(
            f"Atlas ROIs absent from BOLD/mask: {sorted(set(ids) - set(present))}. Check coverage and registration."
        )
    coords = np.array(
        [nib.affines.apply_affine(atlas.affine, np.argwhere(original == v).mean(axis=0)) for v in ids]
    )
    flat = labels.ravel()
    selected = np.flatnonzero(flat > 0)
    codes = np.searchsorted(ids, flat[selected])
    counts = np.bincount(codes, minlength=len(ids))
    values = np.empty((img.shape[3], len(ids)), dtype=float)
    # Only a small slab of time points is held in memory, even for long runs.
    for start in range(0, img.shape[3], 8):
        chunk = np.asarray(img.dataobj[..., start : start + 8], dtype=np.float32)
        chunk = chunk.reshape((-1, chunk.shape[-1]))[selected]
        if not np.isfinite(chunk).all():
            raise InputError(
                "Nonfinite BOLD values inside an ROI; repair the input instead of imputing correlations."
            )
        for t in range(chunk.shape[1]):
            values[start + t] = np.bincount(codes, weights=chunk[:, t], minlength=len(ids)) / counts
    rois = make_rois(ids.tolist(), coords=coords, table=table)
    qc = {
        "roi_voxels": counts.tolist(),
        "atlas_resampled": atlas.shape != grid[0] or not np.allclose(atlas.affine, img.affine),
        "orientation": list(nib.aff2axcodes(img.affine)),
        "bold_shape": list(img.shape),
        "spatial_units": "mm (unknown NIfTI units assumed mm)"
        if hasattr(img.header, "get_xyzt_units") and img.header.get_xyzt_units()[0] == "unknown"
        else "mm",
    }
    return values, rois, qc, aligned


def cifti_timeseries(img, atlas_path=None, table=None):
    """Extract a loaded CIFTI time series with exact axis matching.

    img requires SeriesAxis in SECOND followed by BrainModelAxis or ParcelsAxis.
    Dense input requires atlas_path: one LabelAxis map whose BrainModelAxis equals
    the input axis. Parcel input is read directly in ParcelsAxis name order.
    table optionally maps labels/parcel IDs and supplies display coordinates.

    Returns (time_x_roi_array, roi_records, {'t_r': seconds, 'format':'cifti'}, None).
    Dense data uses 16-frame slabs and unweighted grayordinate means. No CIFTI
    display centroids or surface mesh are inferred. InputError reports invalid
    axes/atlas/nonfinite dense data; pipeline validates parcel signals afterwards.
    Low-level extraction does not validate named spaces/preprocessing status."""
    from nibabel.cifti2.cifti2_axes import BrainModelAxis, LabelAxis, ParcelsAxis, SeriesAxis

    axes = [img.header.get_axis(i) for i in range(img.ndim)]
    if len(axes) != 2 or not isinstance(axes[0], SeriesAxis):
        raise InputError(
            "CIFTI input must be SeriesAxis × BrainModelAxis (.dtseries) or ParcelsAxis (.ptseries)."
        )
    if axes[0].unit != "SECOND":
        raise InputError("CIFTI time unit must be SECOND.")
    if isinstance(axes[1], ParcelsAxis):
        values = np.asarray(img.dataobj, dtype=float)
        rois = make_rois(axes[1].name.tolist(), axes[1].name.tolist(), table=table, by_value=False)
    elif isinstance(axes[1], BrainModelAxis):
        if atlas_path is None:
            raise InputError(
                "Dense CIFTI needs a matching .dlabel.nii atlas and an ROI coordinate table for 3D."
            )
        atlas = nib.load(atlas_path)
        if (
            not isinstance(atlas, nib.Cifti2Image)
            or not isinstance(atlas.header.get_axis(0), LabelAxis)
            or atlas.shape[0] != 1
        ):
            raise InputError("CIFTI atlas must be a single-map .dlabel.nii.")
        if atlas.header.get_axis(1) != axes[1]:
            raise InputError(
                "CIFTI brain-model axes differ; equal array lengths do not establish grayordinate alignment."
            )
        labels = np.asarray(atlas.dataobj).ravel()
        ids = label_values(labels)
        mapping = atlas.header.get_axis(0).label[0]
        if any(int(v) not in mapping for v in ids):
            raise InputError("CIFTI atlas label table is incomplete.")
        values = np.empty((img.shape[0], len(ids)))
        selections = [np.flatnonzero(labels == v) for v in ids]
        for start in range(0, img.shape[0], 16):
            slab = np.asarray(img.dataobj[start : start + 16], dtype=float)
            if not np.isfinite(slab).all():
                raise InputError("CIFTI contains nonfinite values.")
            values[start : start + 16] = np.column_stack([slab[:, ix].mean(axis=1) for ix in selections])
        rois = make_rois(ids.tolist(), [mapping[int(v)][0] for v in ids], table=table)
    else:
        raise InputError("Unsupported CIFTI axis; a connectivity matrix is not an fMRI time series.")
    return values, rois, {"t_r": float(axes[0].step), "format": "cifti"}, None


def gifti_timeseries(img, atlas_path, table=None):
    """Extract loaded GIFTI functional arrays using one LABEL-intent atlas.

    atlas_path must have one label array with matching vertex count. Functional
    arrays must have TIME_SERIES intent: one vertices x time array or one 1D
    vertex array per frame. table optionally supplies label mapping/coordinates.
    Returns (time_x_roi_array, roi_records, {'format':'gifti'}, None).
    Arithmetic means use the complete dense array in memory. TR is not inferred
    from GIFTI metadata. InputError reports incompatible intents/counts or nonfinite
    signals. The caller must establish same hemisphere/template/vertex ordering."""
    if atlas_path is None:
        raise InputError(
            "GIFTI functional data needs a label GIFTI of the SAME hemisphere, surface and vertex order."
        )
    atlas = nib.load(atlas_path)
    if not isinstance(atlas, nib.gifti.GiftiImage) or len(atlas.darrays) != 1:
        raise InputError("GIFTI atlas must contain one label array.")
    if atlas.darrays[0].intent != nib.nifti1.intent_codes["NIFTI_INTENT_LABEL"]:
        raise InputError("GIFTI atlas array must use LABEL intent.")
    labels = np.asarray(atlas.darrays[0].data)
    ids = label_values(labels)
    arrays = [
        np.asarray(d.data)
        for d in img.darrays
        if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_TIME_SERIES"]
    ]
    if not arrays:
        raise InputError("Functional GIFTI arrays must use TIME_SERIES intent.")
    if len(arrays) == 1 and arrays[0].ndim == 2:
        dense = arrays[0].T  # GIFTI time series: vertices × time.
    elif all(a.ndim == 1 for a in arrays):
        dense = np.stack(arrays)
    else:
        raise InputError("Use one vertices × time GIFTI array or one vertex array per time point.")
    if dense.shape[1] != len(labels):
        raise InputError("GIFTI vertex counts do not match.")
    if not np.isfinite(dense).all():
        raise InputError("GIFTI contains nonfinite values.")
    lookup = atlas.labeltable.get_labels_as_dict()
    values = np.column_stack([dense[:, labels == v].mean(axis=1) for v in ids])
    return (
        values,
        make_rois(ids.tolist(), [lookup.get(int(v), f"ROI {v}") for v in ids], table=table),
        {"format": "gifti"},
        None,
    )


def brain_geometry(atlas_img=None, reference=None, *, space="unknown"):
    """Build a display mesh from atlas coverage or an explicit reference.

    atlas_img is an optional loaded 3D spatial image; reference is an optional
    3D brain-mask/skull-stripped-reference filename taking precedence. space labels
    the output; this function does not prove alignment to that named space.

    Returns a dict with space, units='mm', orientation='RAS+', brain (flat positions/
    indices), parcels={} and source. With no image returns an empty mesh, preserving
    coordinate-only visualization. Positive voxels undergo closing/hole filling,
    Gaussian interpolation (sigma=0.65 voxel), marching cubes and RAS+ transform.
    Only display geometry changes; no ROI extraction data are modified.
    InputError reports invalid/empty references. Atlas coverage is not a pial surface."""
    from scipy.ndimage import binary_closing, binary_fill_holes, gaussian_filter
    from skimage.measure import marching_cubes

    img = nib.load(reference) if reference else atlas_img
    if img is None:
        return {
            "space": space,
            "units": "mm",
            "orientation": "RAS+",
            "brain": {"positions": [], "indices": []},
            "parcels": {},
            "source": "No anatomical surface supplied; ROI coordinates only",
        }
    validate_volume(img, ndim=3)
    data = np.asarray(img.dataobj)
    if not np.isfinite(data).all():
        raise InputError("Reference image contains nonfinite values.")
    # Reference should be a brain mask or skull-stripped T1, in the same space.
    mask = data > 0
    mask = binary_fill_holes(binary_closing(mask, iterations=1))
    if not mask.any():
        raise InputError("Anatomical reference / atlas coverage is empty.")
    # Subvoxel display surface; the mask used for ROI extraction is never smoothed.
    field = gaussian_filter(np.pad(mask, 2).astype(np.float32), sigma=0.65)
    verts, faces, _, _ = marching_cubes(field, level=0.5, step_size=1)
    verts = nib.affines.apply_affine(img.affine, verts - 2)
    signed_volume = np.einsum(
        "ij,ij->i", verts[faces[:, 0]], np.cross(verts[faces[:, 1]], verts[faces[:, 2]])
    ).sum()
    if signed_volume < 0:
        faces = faces[:, [0, 2, 1]]
    return {
        "space": space,
        "units": "mm",
        "orientation": "RAS+",
        "brain": {"positions": verts.round(3).ravel().tolist(), "indices": faces.ravel().tolist()},
        "parcels": {},
        "display_surface": "Gaussian mask interpolation (0.65 voxel); display only, ROI coordinates unchanged",
        "source": "Supplied brain mask / skull-stripped reference"
        if reference
        else "Atlas coverage envelope (not a cortical surface)",
    }
