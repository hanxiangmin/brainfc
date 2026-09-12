"""Local HTTP adapter. The scientific logic lives exclusively in the Python API."""
from __future__ import annotations

from contextlib import asynccontextmanager
import json
import threading
from pathlib import Path
import uuid
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool

from brainfc.network import AnalysisConfig, AnalysisResult, ValidationError, __version__
from .limits import RequestBodyLimitMiddleware
from .storage import Store, WorkspaceLock, now
from .worker import JobManager

SUFFIXES = {".csv", ".tsv", ".txt", ".1d", ".npy", ".npz", ".mat"}
MAX_FILE_BYTES = 128 * 1024 * 1024
_ARTIFACT_LOCK = threading.RLock()


def create_app(workspace=None):
    from platformdirs import user_data_path
    store = Store(workspace or user_data_path("brainfc", appauthor=False) / "networks")
    manager = JobManager(store)
    lock = WorkspaceLock(store.root)

    @asynccontextmanager
    async def lifespan(_app):
        lock.acquire()
        manager.start()
        try:
            yield
        finally:
            manager.close()
            lock.release()

    app = FastAPI(title="BrainFC network analysis API", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.manager = manager
    from .atlases import atlas_router
    from starlette.middleware.gzip import GZipMiddleware
    app.include_router(atlas_router(store))
    app.add_middleware(GZipMiddleware, minimum_size=2000)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=MAX_FILE_BYTES * 4)

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin access to local data is disabled."}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH"}:
            length = request.headers.get("content-length")
            if length and not length.isdecimal():
                return JSONResponse({"detail": "Invalid content length."}, status_code=400)
            if length and int(length) > MAX_FILE_BYTES * 4:
                return JSONResponse({"detail": "Request is too large; upload smaller batches."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        return response

    @app.exception_handler(ValidationError)
    async def validation_error(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.get("/api/v1/health")
    def health():
        return {"version": __version__, "local_only": True}

    @app.get("/docs", include_in_schema=False)
    def reference():
        from .reference import REFERENCE_HTML
        return HTMLResponse(REFERENCE_HTML)

    @app.get("/api/v1/uploads")
    def uploads():
        return {"files": [{k: v for k, v in item.items() if k != "brainfc_input"}
                          for item in store.all("uploads")]}

    @app.post("/api/v1/uploads")
    async def upload(files: list[UploadFile] = File(...)):
        from brainfc.network.io import inspect_file
        if not 1 <= len(files) <= 50:
            raise HTTPException(422, "Upload between 1 and 50 files at a time.")
        records, errors = [], []
        for item in files:
            filename = (item.filename or "unnamed").replace("\\", "/").split("/")[-1][:240]
            suffix = Path(filename).suffix.lower()
            destination = None
            try:
                if suffix not in SUFFIXES:
                    raise ValidationError("Supported formats: CSV, TSV, TXT, 1D, NPY, NPZ, MAT.")
                record = {"id": uuid.uuid4().hex, "name": filename, "suffix": suffix, "created_at": now()}
                destination = store.upload_path(record)
                size = 0
                with destination.open("wb") as stream:
                    while chunk := await item.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            raise ValidationError("File exceeds 128 MiB. Split the input into smaller datasets.")
                        stream.write(chunk)
                record.update(await run_in_threadpool(inspect_file, destination, source_name=filename))
                record["name"] = filename
                record["bytes"] = size
                records.append(store.put("uploads", record))
            except Exception as exc:
                if destination is not None:
                    destination.unlink(missing_ok=True)
                errors.append({"name": filename, "message": str(exc)})
            finally:
                await item.close()
        if not records:
            raise HTTPException(422, errors)
        return {"files": records, "errors": errors}

    def new_job(body):
        if not isinstance(body, dict):
            raise ValidationError("Job request must be an object.")
        file_ids = body.get("file_ids", [])
        if not isinstance(file_ids, list) or not 1 <= len(file_ids) <= 50 or any(not isinstance(item, str) for item in file_ids) or len(file_ids) != len(set(file_ids)):
            raise ValidationError("Select 1 to 50 distinct uploaded files.")
        uploads = [store.get("uploads", item) for item in file_ids]
        config = AnalysisConfig.from_dict(body.get("analysis", {}))
        options = body.get("input", {})
        allowed = {"kind", "variable", "roi_columns", "matrix_kind", "preset", "roi_ids", "labels", "coordinates", "metadata"}
        if not isinstance(options, dict) or set(options) - allowed:
            raise ValidationError("Unknown input option; paths cannot be supplied through HTTP.")
        # A second check in load_data remains authoritative for file-specific validation.
        if len(json.dumps(options)) > 2_000_000:
            raise ValidationError("Input metadata is too large.")
        return store.put("jobs", {"id": uuid.uuid4().hex, "status": "queued", "progress": 0,
            "message": "Queued", "created_at": now(), "file_ids": file_ids,
            "files": [{"id": item["id"], "name": item["name"]} for item in uploads],
            "input": options, "analysis": config.to_dict(), "results": [], "errors": []})

    @app.post("/api/v1/jobs")
    def submit(body: dict):
        return new_job(body)

    @app.get("/api/v1/jobs")
    def jobs():
        return {"jobs": store.all("jobs")}

    @app.get("/api/v1/jobs/{job_id}")
    def job(job_id: str):
        return store.get("jobs", job_id)

    @app.post("/api/v1/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        return manager.cancel(job_id)

    @app.post("/api/v1/jobs/{job_id}/retry")
    def retry(job_id: str):
        original = store.get("jobs", job_id)
        if original["status"] in {"queued", "running"}:
            raise HTTPException(409, "The job is still active.")
        return new_job(original)

    @app.get("/api/v1/results/{result_id}")
    def result(result_id: str):
        store.get("results", result_id)
        return json.loads(store.result_path(result_id).read_text(encoding="utf-8"))

    @app.get("/api/v1/results/{result_id}/export")
    def export(result_id: str, format: str = "zip"):
        from brainfc.network.export import export_result
        extensions = {"zip": "zip", "csv": "zip", "json": "json", "html": "html", "svg": "svg",
                      "png": "png", "pdf": "pdf", "graphml": "graphml", "hyperedges": "json"}
        if format not in extensions:
            raise HTTPException(422, "Unsupported export format")
        data = AnalysisResult.from_dict(result(result_id))
        target = store.root / "exports" / f"{result_id}-{format}.{extensions[format]}"
        with _ARTIFACT_LOCK:
            if not target.exists():
                temporary = target.with_name(target.name + ".tmp")
                export_result(data, temporary, format=format)
                temporary.replace(target)
        return FileResponse(target, filename=f"hicbrain-{format}-{result_id[:8]}.{extensions[format]}")

    @app.get("/api/v1/template")
    def template():
        from nilearn.datasets import load_mni152_template
        target = store.root / "templates" / "mni152_2mm.nii.gz"
        with _ARTIFACT_LOCK:
            if not target.exists():
                temporary = target.with_name("mni152_2mm.tmp.nii.gz")
                load_mni152_template(resolution=2).to_filename(temporary)
                temporary.replace(target)
        return FileResponse(target, media_type="application/octet-stream")

    @app.post("/api/v1/statistics")
    def statistics(body: dict):
        import pandas as pd
        from brainfc.network.statistics import compare_groups
        try:
            return compare_groups(pd.DataFrame(body["rows"]), group_column=body["group_column"],
                subject_column=body["subject_column"], feature_columns=body["feature_columns"],
                covariates=body.get("covariates") or None)
        except (KeyError, TypeError) as exc:
            raise ValidationError(f"Invalid cohort table or column selection: {exc}") from exc

    static = Path(__file__).with_name("static")
    if static.is_dir() and (static / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static, html=True), name="web")
    else:
        @app.get("/")
        def no_frontend():
            return JSONResponse({"message": "Frontend assets are missing. Install an official wheel or build frontend."}, status_code=503)
    return app
