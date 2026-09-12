"""Explicit atlas downloads, with label values and template spaces preserved."""

from pathlib import Path
import json
import numpy as np
import pandas as pd
from .models import InputError


def fetch_atlas(name="schaefer100", *, data_dir=None):
    """Explicitly download/cache one supported integer-label atlas.

    Parameters
    ----------
    name : {'schaefer100','schaefer200','schaefer400','aal116'}
        Default 'schaefer100'. Schaefer: 7 networks, 2 mm, MNI152NLin6Asym.
        AAL: SPM12 116 regions, MNIColin27. These spaces are not interchangeable.
    data_dir : str, pathlib.Path or None, default None
        Cache root; default ~/.cache/brainfc/atlases.

    Returns
    -------
    dict
        atlas (image path), rois (TSV path), space, name, source URL, n_rois.

    Notes
    -----
    Creates cache directories; Nilearn downloads only as required. Regenerates
    name_rois.tsv and name.json in that cache. ROI centroid coordinates are mm
    from the atlas affine. Network/download failures propagate. No download at
    import time; dataset/atlas licenses remain those of their providers."""
    from nilearn.datasets import fetch_atlas_schaefer_2018, fetch_atlas_aal

    root = Path(data_dir or Path.home() / ".cache" / "brainfc" / "atlases").resolve()
    root.mkdir(parents=True, exist_ok=True)
    if name in {"schaefer100", "schaefer200", "schaefer400"}:
        n = int(name.replace("schaefer", ""))
        atlas = fetch_atlas_schaefer_2018(n_rois=n, yeo_networks=7, resolution_mm=2, data_dir=root, verbose=0)
        space = "MNI152NLin6Asym"
        labels = [v.decode() if isinstance(v, bytes) else str(v) for v in atlas.labels]
        # New Nilearn LUTs include background; use the LUT as the source of IDs.
        if hasattr(atlas, "lut"):
            lut = atlas.lut
            rows = [
                {
                    "label_value": int(r["index"]),
                    "roi_id": str(int(r["index"])),
                    "name": str(r["name"]),
                    "network": str(r["name"]).split("_")[2] if len(str(r["name"]).split("_")) > 2 else "",
                }
                for _, r in lut.iterrows()
                if int(r["index"]) != 0
            ]
        else:
            labels = [v for v in labels if v.lower() != "background"]
            rows = [{"label_value": i + 1, "roi_id": str(i + 1), "name": v} for i, v in enumerate(labels)]
        source = "https://github.com/ThomasYeoLab/CBIG/tree/master/stable_projects/brain_parcellation/Schaefer2018_LocalGlobal"
    elif name == "aal116":
        atlas = fetch_atlas_aal(version="SPM12", data_dir=root, verbose=0)
        space = "MNIColin27"
        rows = [
            {"label_value": int(i), "roi_id": str(i), "name": str(v)}
            for i, v in zip(atlas.indices, atlas.labels)
            if int(i) != 0
        ]
        source = "https://www.gin.cnrs.fr/en/tools/aal/"
    else:
        raise InputError("Available atlases: schaefer100, schaefer200, schaefer400, aal116.")
    frame = pd.DataFrame(rows)
    import nibabel as nib

    img = nib.load(atlas.maps)
    data = np.asarray(img.dataobj)
    xyz = [
        nib.affines.apply_affine(img.affine, np.argwhere(data == v).mean(axis=0)) for v in frame.label_value
    ]
    frame[["x", "y", "z"]] = np.asarray(xyz)
    labels_path = root / f"{name}_rois.tsv"
    frame.to_csv(labels_path, sep="\t", index=False)
    result = {
        "atlas": str(Path(atlas.maps).resolve()),
        "rois": str(labels_path),
        "space": space,
        "name": name,
        "source": source,
        "n_rois": len(frame),
    }
    (root / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
