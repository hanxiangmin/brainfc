"""Bundled examples with explicit synthetic or human-data provenance."""

from pathlib import Path
import json
import shutil
import nibabel as nib
import numpy as np
import pandas as pd


def create_demo(directory, *, kind="synthetic"):
    """Copy or generate bundled example inputs in a new directory.

    Returns a dict of source/atlas/rois/confounds paths plus a plain config dict.
    Use Config(**spec.pop('config')) before passing spec to extract_connectome.
    kind='synthetic' (default): seed 42, 160 frames, 12 artificial ROIs, TR=2 s
    in synthetic-demo space. kind='rest01': a de-identified single-participant
    resting-state example, with 150 preprocessed time points in 100 Schaefer ROIs,
    confounds and a brain-only display mask. The latter includes an example.json
    methods/QC record; it has no slice-timing or susceptibility-distortion correction.
    Its returned spec also includes reference, and omits atlas (table input).
    Creates inputs only, without network access or computing connectivity.
    Existing directories raise FileExistsError; invalid kind raises ValueError.
    When exporting, mark provenance['synthetic'] according to kind (the CLI does so).
    """
    if kind not in {"synthetic", "rest01"}:
        raise ValueError("kind must be 'synthetic' or 'rest01'.")
    if kind == "rest01":
        from importlib.resources import files, as_file

        resource = files("brainfc").joinpath("data", "rest01")
        root = Path(directory).resolve()
        root.mkdir(parents=True, exist_ok=False)
        for name in ("timeseries.tsv", "timeseries.json", "rois.tsv", "confounds.tsv",
                     "reference_mask.nii.gz", "example.json", "README.md", "privacy-review.json"):
            with as_file(resource.joinpath(name)) as source:
                shutil.copyfile(source, root / name)
        settings = json.loads((root / "example.json").read_text(encoding="utf-8"))["extraction_config"]
        return {
            "source": str(root / "timeseries.tsv"),
            "rois": str(root / "rois.tsv"),
            "confounds": str(root / "confounds.tsv"),
            "reference": str(root / "reference_mask.nii.gz"),
            "config": settings,
        }
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
