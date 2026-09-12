from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pandas as pd
from .models import InputError


def _json(data):
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)


def write_report(result, path, *, view_image=None):
    """Write self-contained HTML and return its absolute pathlib.Path.

    result is a Connectome; path must not exist. Optional view_image is a PNG path
    embedded as the initial static preview. Parent directories are created.
    Interactive JS/CSS and result data are embedded, with JSON escaped for safe
    script embedding. Raises FileExistsError on overwrite or InputError if bundled
    assets are missing. Does not open a browser; see Connectome.view."""
    target = Path(path).expanduser().resolve()
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite {target}")
    static = files("brainfc").joinpath("web", "static")
    js = static.joinpath("app.js")
    if not js.is_file():
        raise InputError("Packaged UI is missing. Build frontend assets before building the wheel.")
    payload = result.to_dict()
    if view_image:
        payload["views_image"] = "data:image/png;base64," + base64.b64encode(
            Path(view_image).read_bytes()
        ).decode("ascii")
    data = _json(payload).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    script = js.read_text(encoding="utf-8").replace("</script", "<\\/script")
    css = static.joinpath("app.css").read_text(encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<link rel="icon" href="data:,"><title>BrainFC · 连接分析报告</title><style>'
        + css
        + '</style><div id="root"></div>'
        "<script>window.__FMRI_REPORT__=" + data + ";</script><script>" + script + "</script></html>",
        encoding="utf-8",
    )
    return target


def save_result(result, directory, *, figures=True, report=True):
    """Export a Connectome to a new directory and return its absolute Path.

    directory, figures=True and report=True have exactly the same contract as
    Connectome.save. Writes a temporary sibling directory, removes it on errors,
    and renames it on success. No ZIP is created. manifest.json hashes all other
    exported files, excluding itself. See docs/outputs.md for schemas and file list."""
    target = Path(directory).expanduser().resolve()
    if target.exists():
        raise FileExistsError(f"Result directory already exists: {target}. Choose a new directory.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        ids = [r["roi_id"] for r in result.rois]
        for name, values in [("connectivity", result.connectivity), ("fisher_z", result.fisher_z)]:
            np.save(temp / f"{name}.npy", values, allow_pickle=False)
            pd.DataFrame(values, index=ids, columns=ids).to_csv(temp / f"{name}.csv", index_label="roi_id")
        pd.DataFrame(result.timeseries, columns=ids).to_csv(temp / "timeseries.tsv", sep="\t", index=False)
        np.save(temp / "timeseries.npy", result.timeseries, allow_pickle=False)
        rows = [
            {k: v for k, v in r.items() if k != "coordinates"}
            | (dict(zip(("x", "y", "z"), r["coordinates"])) if r["coordinates"] else {})
            for r in result.rois
        ]
        pd.DataFrame(rows).to_csv(temp / "rois.tsv", sep="\t", index=False)
        pd.DataFrame({"original_volume_index": result.sample_indices}).to_csv(
            temp / "samples.tsv", sep="\t", index=False
        )
        for name, data in [
            ("qc", result.qc),
            ("provenance", result.provenance),
            ("result", result.to_dict()),
        ]:
            (temp / f"{name}.json").write_text(_json(data), encoding="utf-8")
        view_image = None
        if figures:
            for extension in ("png", "svg", "pdf"):
                result.plot_matrix(temp / f"matrix.{extension}")
                if all(r.get("coordinates") for r in result.rois):
                    result.plot_views(temp / f"eight_views.{extension}")
            if (temp / "eight_views.png").is_file():
                view_image = temp / "eight_views.png"
        if report:
            write_report(result, temp / "report.html", view_image=view_image)
        manifest = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "files": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in temp.iterdir() if p.is_file()
            },
        }
        (temp / "manifest.json").write_text(_json(manifest), encoding="utf-8")
        temp.rename(target)
    except BaseException:
        shutil.rmtree(temp)
        raise
    return target
