"""Deterministic synthetic volume, never represented as human subject data."""

from pathlib import Path
import json
import nibabel as nib
import numpy as np
import pandas as pd


def create_demo(directory):
    """Create deterministic synthetic NIfTI inputs in a new directory.

    Returns a dict of source/atlas/rois/confounds paths plus a plain config dict.
    Use Config(**spec.pop('config')) before passing spec to extract_connectome.
    Seed 42, 160 frames, 12 artificial ROIs, TR=2 s and synthetic-demo space.
    Creates input files only; does not extract a result or download human data.
    Existing directory raises FileExistsError. Mark provenance['synthetic']=True
    when exporting an extracted demo (the CLI/GUI demo commands already do so)."""
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(42)
    shape, n = (32, 40, 32), 160
    affine = np.diag([5.0, 5.0, 5.0, 1.0])
    affine[:3, 3] = [-80, -110, -75]
    ijk = np.indices(shape).transpose(1, 2, 3, 0)
    xyz = nib.affines.apply_affine(affine, ijk)
    centres = np.array(
        [
            [x, y, z]
            for x in [-35, 35]
            for y, z in [(-60, 0), (-30, 35), (15, 45), (40, 0), (-10, -20), (-55, 40)]
        ]
    )
    atlas = np.zeros(shape, dtype=np.int16)
    latent = rng.normal(size=(n, 3))
    for i, center in enumerate(centres):
        atlas[np.linalg.norm(xyz - center, axis=-1) < 15] = (i + 1) * 10
    data = np.zeros((*shape, n), dtype=np.float32)
    motion = rng.normal(0, 0.04, (n, 6))
    for i in range(len(centres)):
        signal = latent[:, i % 3] * (1 if i < 6 else -0.7) + rng.normal(0, 0.55, n) + motion[:, 0] * 4
        index = atlas == (i + 1) * 10
        data[index] = 100 + signal + rng.normal(0, 0.12, (index.sum(), n))
    for name, a in [("demo_bold.nii.gz", data), ("demo_atlas.nii.gz", atlas)]:
        image = nib.Nifti1Image(a, affine)
        image.header.set_xyzt_units("mm", "sec")
        if a.ndim == 4:
            image.header.set_zooms((5, 5, 5, 2))
        nib.save(image, root / name)
    pd.DataFrame(
        {
            "label_value": [(i + 1) * 10 for i in range(len(centres))],
            "roi_id": [f"Demo{i + 1:02d}" for i in range(len(centres))],
            "name": [f"Synthetic ROI {i + 1:02d}" for i in range(len(centres))],
            "network": [f"Synthetic group {i % 3 + 1}" for i in range(len(centres))],
        }
    ).to_csv(root / "rois.tsv", sep="\t", index=False)
    frame = pd.DataFrame(motion, columns=[f"trans_{a}" for a in "xyz"] + [f"rot_{a}" for a in "xyz"])
    frame["framewise_displacement"] = np.abs(rng.normal(0.08, 0.02, n))
    frame.loc[[23, 74, 105], "framewise_displacement"] = 0.8
    frame.to_csv(root / "confounds.tsv", sep="\t", index=False)
    (root / "demo_bold.json").write_text(
        json.dumps({"RepetitionTime": 2, "Synthetic": True}), encoding="utf-8"
    )
    return {
        "source": str(root / "demo_bold.nii.gz"),
        "atlas": str(root / "demo_atlas.nii.gz"),
        "rois": str(root / "rois.tsv"),
        "confounds": str(root / "confounds.tsv"),
        "config": {
            "preprocessed": True,
            "data_space": "synthetic-demo",
            "atlas_space": "synthetic-demo",
            "t_r": 2,
            "fd_threshold": 0.5,
        },
    }
