"""Thin local HTTP routes for the public AtlasRegistry and ViewConfig APIs."""

import json
from pathlib import Path
import tempfile
import threading

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from brainfc.network.atlas import AtlasRegistry
from brainfc.network.atlas_sources import reference_brain
from brainfc.network.types import AnalysisResult, ValidationError
from brainfc.network.view import ViewConfig


def atlas_router(store):
    router = APIRouter(prefix="/api/v1")
    registry = AtlasRegistry(store.root / "atlases")
    viewroot = store.root / "views"
    viewroot.mkdir(exist_ok=True)
    viewlock = threading.RLock()

    @router.get("/atlases")
    def catalog():
        return {"atlases": registry.list()}

    @router.get("/atlases/{atlas_id}")
    def spec(atlas_id: str):
        return registry.get(atlas_id)

    @router.post("/atlases/{atlas_id}/install")
    async def install(atlas_id: str):
        try:
            return await run_in_threadpool(registry.install, atlas_id)
        except ValidationError:
            raise
        except Exception as exc:
            raise HTTPException(502, f"Atlas download/generation failed; retry installation: {exc}") from exc

    @router.get("/atlases/{atlas_id}/assets/{name}")
    def asset(atlas_id: str, name: str):
        return FileResponse(registry.asset(atlas_id, name))

    @router.post("/atlases")
    async def upload_atlas(
        metadata: str = Form(...),
        parcellation: UploadFile = File(...),
        labels: UploadFile = File(...),
        reference: UploadFile | None = File(None),
    ):
        try:
            body = json.loads(metadata)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValidationError("Atlas metadata must be JSON.") from exc
        allowed = {"name", "space", "version", "sources", "license", "space_confirmed"}
        if not isinstance(body, dict) or set(body) - allowed:
            raise ValidationError("Unknown atlas metadata field.")
        if (
            not isinstance(body.get("name"), str)
            or not isinstance(body.get("space"), str)
            or body.get("space_confirmed") is not True
        ):
            raise ValidationError("Atlas name, exact space and explicit alignment confirmation are required.")
        with tempfile.TemporaryDirectory(prefix="atlas-upload-", dir=store.root / "uploads") as temp:
            paths = {}
            for key, upload in (("parcellation", parcellation), ("labels", labels), ("reference", reference)):
                if upload is None:
                    continue
                suffix = (
                    ".tsv"
                    if key == "labels" and str(upload.filename).lower().endswith(".tsv")
                    else ".csv"
                    if key == "labels"
                    else ".nii.gz"
                    if str(upload.filename).lower().endswith(".nii.gz")
                    else ".nii"
                )
                path = Path(temp) / (key + suffix)
                try:
                    size = 0
                    with path.open("wb") as f:
                        while chunk := await upload.read(1024 * 1024):
                            size += len(chunk)
                            if size > 128 * 1024**2:
                                raise ValidationError("Atlas upload exceeds 128 MiB per file.")
                            f.write(chunk)
                    paths[key] = path
                finally:
                    await upload.close()
            if "reference" not in paths:
                if body.get("space") not in {"MNIColin27", "MNI152NLin6Asym"}:
                    raise ValidationError("A custom space needs its own aligned reference brain NIfTI.")
                paths["reference"] = await run_in_threadpool(reference_brain, registry.root, body["space"])
            return await run_in_threadpool(
                registry.import_atlas,
                paths["parcellation"],
                paths["labels"],
                reference=paths["reference"],
                **body,
            )

    @router.post("/results/{result_id}/atlas")
    def binding(result_id: str, body: dict):
        store.get("results", result_id)
        original = AnalysisResult.from_dict(
            json.loads(store.result_path(result_id).read_text(encoding="utf-8"))
        )
        with viewlock:
            path = viewroot / (result_id + "-atlas.json")
            if path.exists():
                original.metadata["atlas_binding"] = json.loads(path.read_text(encoding="utf-8"))
            mapped = registry.bind(
                original,
                body.get("atlas_id"),
                body.get("ordered_roi_ids"),
                confirmed=body.get("confirmed") is True,
            )
            mapping = mapped.metadata["atlas_binding"]
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(mapping), encoding="utf-8")
            tmp.replace(path)
        return mapped.to_dict()

    @router.get("/results/{result_id}/mapped")
    def mapped_result(result_id: str):
        store.get("results", result_id)
        original = json.loads(store.result_path(result_id).read_text(encoding="utf-8"))
        path = viewroot / (result_id + "-atlas.json")
        if path.exists():
            binding = json.loads(path.read_text(encoding="utf-8"))
            spec = registry.get(binding["atlas_id"])
            if spec["sha256"]["content"] != binding["atlas_sha256"]:
                raise ValidationError("Installed atlas differs from the saved mapping.")
            return registry.bind(
                original, binding["atlas_id"], binding["ordered_roi_ids"], confirmed=True
            ).to_dict()
        return original

    @router.get("/results/{result_id}/view")
    def get_view(result_id: str):
        store.get("results", result_id)
        path = viewroot / (result_id + ".json")
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else ViewConfig().to_dict()

    @router.put("/results/{result_id}/view")
    def save_view(result_id: str, body: dict):
        store.get("results", result_id)
        view = ViewConfig.from_dict(body).to_dict()
        with viewlock:
            path = viewroot / (result_id + ".json")
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(view, allow_nan=False), encoding="utf-8")
            tmp.replace(path)
        return view

    return router
