"""Check release metadata, documentation coverage, workflows and archive contents."""

import argparse
import ast
import hashlib
from email.parser import BytesParser
import json
from pathlib import Path
import re
import runpy
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    ".work",
    ".venv",
    "node_modules",
    "__pycache__",
    "outputs",
    ".git",
    ".env",
    ".pypirc",
    "license.txt",
}
DATA_SUFFIXES = (".nii", ".nii.gz", ".dcm", ".npy", ".npz", ".mat", ".gii", ".pyc")
EXAMPLE_FILES = {
    "timeseries.tsv", "timeseries.json", "rois.tsv", "confounds.tsv",
    "reference_mask.nii.gz", "example.json", "README.md",
}


def check_example(payloads):
    """Require the exact reviewed sample members and content in an archive."""
    assert set(payloads) == EXAMPLE_FILES | {"privacy-review.json"}, "Unreviewed example file set"
    review = json.loads(payloads["privacy-review.json"])
    assert review["status"] == "reviewed_for_direct_identifiers"
    assert set(review["reviewed_files"]) == EXAMPLE_FILES, "Incomplete example review"
    for name, digest in review["reviewed_files"].items():
        assert hashlib.sha256(payloads[name]).hexdigest() == digest, f"Unreviewed example content: {name}"


def check_names(names):
    for name in names:
        path = Path(name)
        assert not set(path.parts) & FORBIDDEN, f"Private/generated directory in archive: {name}"
        # The reviewed brain-only example mask is the sole binary-image exception.
        is_example_mask = name.replace("\\", "/").endswith("brainfc/data/rest01/reference_mask.nii.gz")
        assert is_example_mask or not name.lower().endswith(DATA_SUFFIXES), f"Data/cache in archive: {name}"
        assert not path.is_absolute() and ".." not in path.parts, f"Unsafe archive name: {name}"


def check_archives(directory, version):
    wheel = directory / f"brainfc-{version}-py3-none-any.whl"
    source = directory / f"brainfc-{version}.tar.gz"
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        check_names(names)
        prefix = "brainfc/data/rest01/"
        check_example({n[len(prefix):]: archive.read(n) for n in names if n.startswith(prefix) and not n.endswith("/")})
        for required in (
            "brainfc/web/static/app.js",
            "brainfc/web/static/app.css",
            "brainfc/web/static/reference/index.html",
            "brainfc/web/static/reference/api-reference.html",
        ):
            assert required in names, required
        metadata = BytesParser().parsebytes(
            archive.read(next(n for n in names if n.endswith(".dist-info/METADATA")))
        )
        assert metadata["Name"] == "brainfc" and metadata["Version"] == version
        assert metadata["License-Expression"] == "Apache-2.0"
        assert metadata.get_all("License-File"), "License files missing from wheel metadata"
    with tarfile.open(source) as archive:
        names = archive.getnames()
        check_names(names)
        prefix = f"brainfc-{version}/src/brainfc/data/rest01/"
        check_example({n[len(prefix):]: archive.extractfile(n).read()
                       for n in names if n.startswith(prefix) and archive.getmember(n).isfile()})
        for required in (
            "pyproject.toml",
            "README.md",
            "docs/api-reference.md",
            "scripts/generate_reference.py",
            ".github/workflows/ci.yml",
            ".github/workflows/publish.yml",
        ):
            assert any(n.endswith("/" + required) for n in names), required
    print(f"Archive scope verified: {wheel.name}, {source.name}")


def main():
    import yaml

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    version = runpy.run_path(str(ROOT / "src/brainfc/_version.py"))["__version__"]
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["dynamic"] == ["version"]
    for name in ("package.json", "package-lock.json"):
        content = json.loads((ROOT / "frontend" / name).read_text(encoding="utf-8"))
        assert content["version"] == version, f"Version differs in frontend/{name}"
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert str(citation["version"]) == version
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        # BaseLoader keeps the YAML 1.2 'on' key as a string rather than YAML 1.1 bool.
        workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert "on" in workflow and "jobs" in workflow, path
    inventory = json.loads((ROOT / "docs/api-inventory.json").read_text(encoding="utf-8"))
    covered = {entry["name"] for entry in inventory if entry["documented"]}
    missing = []
    for path in (ROOT / "src/brainfc").glob("*.py"):
        if path.name.startswith("_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and not node.name.startswith("_"):
                name = f"brainfc.{path.stem}.{node.name}"
                if name not in covered:
                    missing.append(name)
    assert not missing, f"Undocumented public API: {missing}"
    # Check Markdown file links, excluding code examples with placeholder data paths.
    for path in [ROOT / "README.md", ROOT / "README.en.md", *list((ROOT / "docs").glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        for link in re.findall(r"\]\(([^)]+)\)", text):
            link = link.split("#")[0]
            if link and not re.match(r"[a-z]+:", link):
                assert (path.parent / link).exists(), f"Broken documentation link: {path.name}: {link}"
    if args.dist:
        check_archives(args.dist.resolve(), version)
    print(f"Release metadata / API coverage / links verified for {version}.")


if __name__ == "__main__":
    main()
