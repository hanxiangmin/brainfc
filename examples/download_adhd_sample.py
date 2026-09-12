"""Download one public raw ADHD-200 run and its T1, recording sources and hashes.

This uses the anonymous S3 location in the ADHD-200 project's own download
instructions. It does not download an entire cohort or run preprocessing.
"""

import hashlib
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://fcp-indi.s3.amazonaws.com/"
PREFIX = "data/Projects/ADHD200/RawDataBIDS/Brown/"


def main():
    root = Path(__file__).resolve().parents[1] / ".work" / "public-data" / "adhd200-raw"
    root.mkdir(parents=True, exist_ok=True)
    listing = ET.fromstring(
        urllib.request.urlopen(BASE + "?list-type=2&prefix=" + PREFIX + "&max-keys=1000", timeout=30).read()
    )
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    objects = [
        (x.find("s:Key", ns).text, int(x.find("s:Size", ns).text)) for x in listing.findall("s:Contents", ns)
    ]
    selected = [
        (k, n)
        for k, n in objects
        if "/sub-0026001/" in k or (k.endswith(".json") and "/" not in k[len(PREFIX) :])
    ]
    records = []
    for key, size in selected:
        dest = root / key[len(PREFIX) :]
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = BASE + key
        if not dest.exists():
            temp = dest.with_name(dest.name + ".part")
            with urllib.request.urlopen(url, timeout=60) as source, temp.open("wb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
            if temp.stat().st_size != size:
                raise ValueError("Size differs from public S3 listing")
            temp.rename(dest)
        records.append(
            {
                "url": url,
                "path": str(dest),
                "bytes": dest.stat().st_size,
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            }
        )
        print(f"Saved {dest.name} ({size} bytes)", flush=True)
    (root / "download_manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    import nibabel as nib

    inspections = []
    for r in records:
        if r["path"].endswith(".nii.gz"):
            img = nib.load(r["path"])
            inspections.append(
                {
                    "path": r["path"],
                    "shape": list(img.shape),
                    "zooms": list(map(float, img.header.get_zooms())),
                    "units": list(img.header.get_xyzt_units()),
                    "orientation": list(nib.aff2axcodes(img.affine)),
                }
            )
    (root / "inspection.json").write_text(json.dumps(inspections, indent=2), encoding="utf-8")
    print(json.dumps(inspections, indent=2))


if __name__ == "__main__":
    main()
