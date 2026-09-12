"""Small, hash-pinned TemplateFlow reference assets (downloaded on first use)."""

from hashlib import sha256
from pathlib import Path
import tempfile
import requests

from ..models import InputError

SPACE = "MNI152NLin6Asym"
ASSETS = {
    "head": ("tpl-MNI152NLin6Asym_res-02_T1w.nii.gz", "2a814da50173599a857d96246dc057d548072bd6dffa499f75724dbad20792b1"),
    "mask": ("tpl-MNI152NLin6Asym_res-02_desc-brain_mask.nii.gz", "e4e2b284170271afdafe26ac0997b2af5a0f5ddac35e28a7e796b52e8bc5adb1"),
}
BASE_URL = "https://templateflow.s3.amazonaws.com/tpl-MNI152NLin6Asym/"


def fetch_template(data_dir=None):
    """Return {'head': Path, 'mask': Path} for the exact MNI152NLin6Asym 2 mm grid.

    data_dir defaults to ~/ .cache/brainfc/templates (without the space). Fetches
    approximately 1.5 MB from TemplateFlow HTTPS on first use. Each cached or
    downloaded file is SHA-256 checked; invalid cache entries raise InputError.
    Downloads use a unique temporary file and atomic replacement. This is a
    fixed adult template, not suitable by default for pediatric/lesioned anatomy.
    """
    root = Path(data_dir or Path.home() / ".cache/brainfc/templates").expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    result = {}
    for key, (name, digest) in ASSETS.items():
        path = root / name
        if not path.exists():
            response = requests.get(BASE_URL + name, timeout=(15, 120))
            response.raise_for_status()
            content = response.content
            if sha256(content).hexdigest() != digest:
                raise InputError(f"Template download checksum mismatch: {name}")
            with tempfile.NamedTemporaryFile(dir=root, delete=False) as stream:
                temp = Path(stream.name)
                stream.write(content)
            temp.replace(path)
        if sha256(path.read_bytes()).hexdigest() != digest:
            raise InputError(f"Template cache checksum mismatch: {name}")
        result[key] = path
    return result
