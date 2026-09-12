"""Generate synthetic BOLD on a real Schaefer atlas, then use the public API.

Only atlas/template resources are real; functional signals are synthetic.
Supply --reference with a matching MNI152NLin6Asym skull-stripped reference.
"""

import argparse
from pathlib import Path
import json
import nibabel as nib
import numpy as np
from brainfc import fetch_atlas


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reference")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1] / ".work/atlas-demo"
    root.mkdir(parents=True, exist_ok=True)
    spec = fetch_atlas("schaefer100", data_dir=root / "atlas-cache")
    atlas = nib.load(spec["atlas"])
    labels = np.asarray(atlas.dataobj, dtype=np.int16)[::2, ::2, ::2]
    affine = atlas.affine @ np.diag([2.0, 2.0, 2.0, 1.0])
    if len(np.unique(labels[labels > 0])) != 100:
        raise ValueError("Downsampled demo grid lost parcels")
    rng = np.random.default_rng(43)
    latent = rng.normal(size=(7, 120))
    signals = np.zeros((101, 120), dtype=np.float32)
    for i in range(1, 101):
        signals[i] = 100 + latent[(i - 1) % 7] + rng.normal(0, 0.8, 120)
    data = signals[labels]
    img = nib.Nifti1Image(data, affine)
    img.header.set_xyzt_units("mm", "sec")
    img.header.set_zooms((4, 4, 4, 2))
    source = root / "synthetic_schaefer100_bold.nii.gz"
    nib.save(img, source)
    payload = {
        "source": str(source),
        "atlas": spec["atlas"],
        "rois": spec["rois"],
        "reference": args.reference,
        "config": {"preprocessed": True, "data_space": spec["space"], "atlas_space": spec["space"], "t_r": 2},
    }
    (root / "request.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(root / "request.json")


if __name__ == "__main__":
    main()
