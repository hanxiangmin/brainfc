"""Explicit installation of upstream atlas assets, never bundled patient data."""

from pathlib import Path
import json
import urllib.request

import nibabel as nib
import numpy as np
import pandas as pd

from .atlas import BUILTINS
from .types import ValidationError

# AAL label expansions and established abbreviations (Table S9, source below).
AAL_NAMES = {
    "Precentral": ("PreCG", "Precentral gyrus"),
    "Frontal_Sup": ("SFGdor", "Superior frontal gyrus, dorsolateral"),
    "Frontal_Sup_Orb": ("ORBsup", "Superior frontal gyrus, orbital part"),
    "Frontal_Mid": ("MFG", "Middle frontal gyrus"),
    "Frontal_Mid_Orb": ("ORBmid", "Middle frontal gyrus, orbital part"),
    "Frontal_Inf_Oper": ("IFGoperc", "Inferior frontal gyrus, opercular part"),
    "Frontal_Inf_Tri": ("IFGtriang", "Inferior frontal gyrus, triangular part"),
    "Frontal_Inf_Orb": ("ORBinf", "Inferior frontal gyrus, orbital part"),
    "Rolandic_Oper": ("ROL", "Rolandic operculum"),
    "Supp_Motor_Area": ("SMA", "Supplementary motor area"),
    "Olfactory": ("OLF", "Olfactory cortex"),
    "Frontal_Sup_Medial": ("SFGmed", "Superior frontal gyrus, medial"),
    "Frontal_Med_Orb": ("ORBsupmed", "Superior frontal gyrus, medial orbital"),
    "Rectus": ("REC", "Gyrus rectus"),
    "Insula": ("INS", "Insula"),
    "Cingulum_Ant": ("ACG", "Anterior cingulate and paracingulate gyri"),
    "Cingulum_Mid": ("DCG", "Median cingulate and paracingulate gyri"),
    "Cingulum_Post": ("PCG", "Posterior cingulate gyrus"),
    "Hippocampus": ("HIP", "Hippocampus"),
    "ParaHippocampal": ("PHG", "Parahippocampal gyrus"),
    "Amygdala": ("AMYG", "Amygdala"),
    "Calcarine": ("CAL", "Calcarine fissure and surrounding cortex"),
    "Cuneus": ("CUN", "Cuneus"),
    "Lingual": ("LING", "Lingual gyrus"),
    "Occipital_Sup": ("SOG", "Superior occipital gyrus"),
    "Occipital_Mid": ("MOG", "Middle occipital gyrus"),
    "Occipital_Inf": ("IOG", "Inferior occipital gyrus"),
    "Fusiform": ("FFG", "Fusiform gyrus"),
    "Postcentral": ("PoCG", "Postcentral gyrus"),
    "Parietal_Sup": ("SPG", "Superior parietal gyrus"),
    "Parietal_Inf": ("IPL", "Inferior parietal, excluding supramarginal and angular gyri"),
    "SupraMarginal": ("SMG", "Supramarginal gyrus"),
    "Angular": ("ANG", "Angular gyrus"),
    "Precuneus": ("PCUN", "Precuneus"),
    "Paracentral_Lobule": ("PCL", "Paracentral lobule"),
    "Caudate": ("CAU", "Caudate nucleus"),
    "Putamen": ("PUT", "Putamen"),
    "Pallidum": ("PAL", "Pallidum"),
    "Thalamus": ("THA", "Thalamus"),
    "Heschl": ("HES", "Heschl gyrus"),
    "Temporal_Sup": ("STG", "Superior temporal gyrus"),
    "Temporal_Pole_Sup": ("TPOsup", "Temporal pole: superior temporal gyrus"),
    "Temporal_Mid": ("MTG", "Middle temporal gyrus"),
    "Temporal_Pole_Mid": ("TPOmid", "Temporal pole: middle temporal gyrus"),
    "Temporal_Inf": ("ITG", "Inferior temporal gyrus"),
}
AAL_DICT_SOURCE = "https://wrap.warwick.ac.uk/id/eprint/80514/2/WRAP_Supplementary.pdf"


def _download(url, target):
    target = Path(target)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Hyper-Brain/0.2"})
    temp = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=60) as source, temp.open("wb") as dest:
            size = 0
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > 128 * 1024**2:
                    raise ValidationError("Upstream asset exceeds 128 MiB.")
                dest.write(chunk)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return target


def reference_brain(root, space):
    """Install named TemplateFlow T1w and brain mask as a matched reference."""
    folder = Path(root) / "_sources" / space
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "reference.nii.gz"
    if target.exists():
        return target
    base = f"https://templateflow.s3.amazonaws.com/tpl-{space}/"
    # Colin27 has one resolution; FSL MNI152 uses the explicit res-02 grid.
    prefix = f"tpl-{space}" + ("_res-02" if space == "MNI152NLin6Asym" else "")
    t1 = _download(base + prefix + "_T1w.nii.gz", folder / "T1w.nii.gz")
    mask = _download(base + prefix + "_desc-brain_mask.nii.gz", folder / "brain_mask.nii.gz")
    for name in ("template_description.json", *(["LICENSE"] if space == "MNIColin27" else [])):
        _download(base + name, folder / name)
    image = nib.load(t1)
    from nibabel.processing import resample_from_to

    maskdata = np.asarray(resample_from_to(nib.load(mask), image, order=0).dataobj) > 0
    data = np.asarray(image.dataobj, dtype=np.float32) * maskdata
    reference = nib.Nifti1Image(data, image.affine)
    reference.header.set_xyzt_units("mm")
    nib.save(reference, target)
    return target


def install_builtin(registry, atlas_id):
    """Download a supported builtin and import it into the supplied AtlasRegistry.

    atlas_id selects AAL SPM12 90/116 or Schaefer 100/200/400 with matched named
    reference space. Returns the installed descriptor. First use requires network
    access; provider licenses apply. Unknown IDs raise ValidationError; network
    and input-validation failures propagate. This does not register subject data.
    """
    from nilearn.datasets import fetch_atlas_aal, fetch_atlas_schaefer_2018

    catalog = next((r for r in BUILTINS if r["id"] == atlas_id), None)
    if catalog is None:
        raise ValidationError("Unknown builtin atlas.")
    if (registry._path(atlas_id) / "atlas.json").exists():
        return registry.get(atlas_id)
    cache = registry.root / "_sources"
    cache.mkdir(exist_ok=True)
    n = catalog["n_rois"]
    rows = []
    if atlas_id.startswith("aal-"):
        upstream = fetch_atlas_aal(version="SPM12", data_dir=cache)
        for value, label in zip(upstream.indices, upstream.labels):
            if int(value) == 0:
                continue
            if n == 90 and (label.startswith("Cerebelum") or label.startswith("Vermis")):
                continue
            hemi = label[-1] if label.endswith(("_L", "_R")) else "M"
            base = label[:-2] if hemi != "M" else label
            # For cerebellar parcels retain the upstream source identifier; no invented acronym.
            short, full = AAL_NAMES.get(base, (base, base.replace("_", " ")))
            rows.append(
                {
                    "label_value": int(value),
                    "roi_id": str(label),
                    "abbreviation": short + ("." + hemi if hemi != "M" else ""),
                    "name": ({"L": "Left ", "R": "Right ", "M": ""}[hemi]) + full,
                    "hemisphere": hemi,
                    "network": "AAL anatomical region",
                }
            )
        sources = [
            "https://www.gin.cnrs.fr/en/tools/aal/",
            AAL_DICT_SOURCE,
            "https://doi.org/10.1006/nimg.2001.0978",
        ]
        terms = "AAL SPM12: upstream GPL terms; atlas assets downloaded separately, not relicensed as Hyper-Brain. Reference template retains TemplateFlow source terms."
    else:
        upstream = fetch_atlas_schaefer_2018(n_rois=n, yeo_networks=7, resolution_mm=2, data_dir=cache)
        lut = upstream.lut
        for row in lut.to_dict("records"):
            if int(row["index"]) == 0:
                continue
            label = str(row["name"])
            parts = label.split("_")
            hemi = "L" if "LH" in parts else "R"
            rows.append(
                {
                    "label_value": int(row["index"]),
                    "roi_id": label,
                    "abbreviation": label.removeprefix("7Networks_"),
                    "name": label,
                    "hemisphere": hemi,
                    "network": parts[2] if len(parts) > 2 else "",
                    "color": row.get("color", ""),
                }
            )
        sources = [
            "https://github.com/ThomasYeoLab/CBIG/tree/v0.14.3-Update_Yeo2011_Schaefer2018_labelname/stable_projects/brain_parcellation/Schaefer2018_LocalGlobal",
            "https://doi.org/10.1093/cercor/bhx179",
        ]
        terms = "Schaefer2018 CBIG: MIT. Reference template retains TemplateFlow source terms."
    if len(rows) != n or upstream.template != catalog["space"]:
        raise ValidationError(
            "Upstream atlas labels or space changed; refusing an unverified template combination."
        )
    original = nib.load(upstream.maps)
    data = np.asarray(original.dataobj).copy()
    data[~np.isin(data, [r["label_value"] for r in rows])] = 0
    image = nib.Nifti1Image(data.astype(np.int16), original.affine)
    image.header.set_xyzt_units("mm")
    imagepath = cache / (atlas_id + ".nii.gz")
    nib.save(image, imagepath)
    reference = reference_brain(registry.root, catalog["space"])
    spec = registry.import_atlas(
        imagepath,
        pd.DataFrame(rows),
        name=catalog["name"],
        space=catalog["space"],
        reference=reference,
        version=catalog["version"],
        sources=sources + [f"https://www.templateflow.org/browse/#tpl-{catalog['space']}"],
        license=terms,
        atlas_id=atlas_id,
        custom=False,
        space_confirmed=True,
    )
    (registry._path(atlas_id) / "upstream_description.txt").write_text(upstream.description, encoding="utf-8")
    (registry._path(atlas_id) / "source_manifest.json").write_text(
        json.dumps(
            {
                "sources": sources,
                "template": catalog["space"],
                "version": catalog["version"],
                "labels": "Source labels preserved; AAL90 abbreviations follow Table S9; Schaefer source parcel identifiers retained.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return spec
