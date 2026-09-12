"""Create an independent GitHub source ZIP and checksums from verified distributions."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import runpy
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    version = runpy.run_path(str(ROOT / "src/brainfc/_version.py"))["__version__"]
    wheel = args.dist / f"brainfc-{version}-py3-none-any.whl"
    source = args.dist / f"brainfc-{version}.tar.gz"
    github = args.dist / f"brainfc-{version}-github-source.zip"
    from check_release import check_archives

    check_archives(args.dist.resolve(), version)
    with (
        tarfile.open(source) as archive,
        zipfile.ZipFile(github, "w", compression=zipfile.ZIP_DEFLATED) as output,
    ):
        for member in archive.getmembers():
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts
            assert len(parts) > 1 and ".." not in parts
            # PKG-INFO is build-generated; source-tree metadata comes from pyproject.
            if parts[1:] == ("PKG-INFO",):
                continue
            name = "/".join(("brainfc", *parts[1:]))
            output.writestr(name, archive.extractfile(member).read())
    artifacts = [wheel, source, github]
    files = {
        p.name: {"size_bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in artifacts
    }
    manifest = {"version": version, "status": "prepared locally; not uploaded", "files": files}
    path = args.dist / f"build-manifest-v{version}.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.dist / f"SHA256SUMS-{version}.txt").write_text(
        "".join(f"{record['sha256']}  {name}\n" for name, record in files.items()), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
