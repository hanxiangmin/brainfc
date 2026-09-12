"""Technical extraction validation using a real, already preprocessed ADHD run.

Three artificial validation parcels are defined in the run's own voxel grid.
They are not standard anatomical ROIs or biological networks. This tests
reading, ROI means, confound regression and export without guessing which
specific MNI template edition the legacy dataset used.
"""

import json
from pathlib import Path
import nibabel as nib
import numpy as np
import pandas as pd
from brainfc import Config, extract_connectome


def main():
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root / ".work/public-data/adhd-preprocessed.json").read_text())
    # The downloader can be run from repository parent; resolve saved relative paths there.
    source = Path(spec["func"][0])
    if not source.is_absolute():
        source = root.parent / source
    confounds = source.parent / "0010042_regressors.csv"
    img = nib.load(source)
    data = np.asarray(img.dataobj, dtype=np.float32)
    supported = (np.std(data, axis=3) > 1) & (np.mean(data, axis=3) > 100)
    ix = np.indices(img.shape[:3])[0]
    atlas = np.where(supported, 1 + (ix >= 20) + (ix >= 40), 0).astype(np.int16)
    # Use arithmetic integer additions, not boolean OR semantics.
    atlas[supported] = 1 + (ix[supported] >= 20).astype(int) + (ix[supported] >= 40).astype(int)
    dest = root / ".work/real-adhd-validation"
    dest.mkdir(parents=True, exist_ok=True)
    atlas_path = dest / "technical-grid-parcels.nii.gz"
    a = nib.Nifti1Image(atlas, img.affine)
    a.header.set_xyzt_units("mm")
    nib.save(a, atlas_path)
    rois = dest / "rois.tsv"
    pd.DataFrame(
        {
            "label_value": [1, 2, 3],
            "roi_id": ["QC1", "QC2", "QC3"],
            "name": ["Technical grid parcel 1", "Technical grid parcel 2", "Technical grid parcel 3"],
        }
    ).to_csv(rois, sep="\t", index=False)
    frame = pd.read_csv(confounds, sep="\t")
    cols = tuple(c for c in frame if c.startswith("motion-")) + ("wm", "csf")
    result = extract_connectome(
        source,
        atlas=atlas_path,
        rois=rois,
        confounds=confounds,
        config=Config(
            preprocessed=True,
            data_space="ADHD40-legacy-preprocessed-grid",
            atlas_space="ADHD40-legacy-preprocessed-grid",
            confound_columns=cols,
            t_r=2,
        ),
        progress=print,
    )
    result.provenance["validation_only"] = (
        "Three artificial grid parcels on real preprocessed data; not anatomical-network results."
    )
    result.save(dest / "result")
    print(
        json.dumps(
            {
                "source": str(source),
                "shape": list(data.shape),
                "qc": result.qc,
                "fc": result.connectivity.tolist(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
