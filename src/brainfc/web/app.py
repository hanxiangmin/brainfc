from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import json
from pathlib import Path
import re
import shutil
import threading
from typing import Literal
from urllib.parse import urlsplit
import uuid
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from ..models import Config, InputError
from .._version import __version__
from .schemas import (
    AtlasRequest,
    CommandResponse,
    DicomRequest,
    ExtractionRequest,
    JobState,
    PathRequest,
    PreflightRequest,
    PreprocessRequest,
    SuggestionsRequest,
    UploadResponse,
    HealthResponse,
    SetupResponse,
    InputInfo,
    RunRecord,
    SuggestionsResponse,
    PresetsResponse,
    PythonPreprocessRequest,
    PythonDicomRequest,
)


def create_app(workspace=None):
    """Create the optional local FastAPI application and its workspace.

    workspace is a directory (default ~/brainfc-workspace). Creates jobs and
    workspace folders. Persisted queued/running jobs are marked interrupted on
    startup; use one server process per workspace. Returns fastapi.FastAPI.
    GUI dependencies are included in the standard package install. Local Host and same-origin checks are applied; no
    account authentication. Bind to loopback, as brainfc serve does.
    The app uses one worker with at most eight active/queued jobs. /docs, /redoc
    and /openapi.json describe HTTP contracts; see docs/http-api.md."""
    root = Path(workspace or Path.home() / "brainfc-workspace").expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    jobs_dir = root / "jobs"
    jobs_dir.mkdir(exist_ok=True)
    executor = ThreadPoolExecutor(max_workers=1)
    lock = threading.RLock()
    active = set()
    from ..network.web.app import create_app as create_network_app

    network_app = create_network_app(root / "networks", brainfc_workspace=root)
    # A prior process cannot still be running a job owned by this server instance.
    for state in jobs_dir.glob("*/status.json"):
        old = json.loads(state.read_text(encoding="utf-8"))
        if old.get("status") in {"queued", "running"}:
            old.update(
                status="interrupted", message="Previous server stopped; rerun into a new result folder."
            )
            state.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")

    @asynccontextmanager
    async def lifespan(app):
        async with network_app.router.lifespan_context(network_app):
            try:
                yield
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(
        title="BrainFC",
        version=__version__,
        lifespan=lifespan,
        description="Local single-run fMRI connectivity API. Paths refer to this server's filesystem. "
        "Use /api/preflight before /api/jobs, then poll the returned id. Extraction shares the Python core. "
        "Bind to loopback and use one server per workspace. Responses and exports include local paths.",
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and (
            urlsplit(origin).netloc != request.headers.get("host") or urlsplit(origin).scheme != "http"
        ):
            return JSONResponse({"detail": "Cross-origin requests are disabled."}, status_code=403)
        return await call_next(request)

    @app.exception_handler(InputError)
    async def input_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    def folder(job_id):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise HTTPException(404, "Unknown job")
        p = jobs_dir / job_id
        if not p.is_dir():
            raise HTTPException(404, "Unknown job")
        return p

    def set_state(dest, data):
        with lock:
            temp = dest / "status.tmp"
            temp.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            temp.replace(dest / "status.json")

    def submit(payload, kind="extract"):
        with lock:
            if len(active) >= 8:
                raise HTTPException(429, "Queue is full; wait for an existing job to finish.")
            job_id = uuid.uuid4().hex
            active.add(job_id)
        dest = jobs_dir / job_id
        dest.mkdir()
        state = {"id": job_id, "status": "queued", "message": "Waiting", "kind": kind}
        if kind == "demo":
            state["example_kind"] = payload.get("example_kind", "rest01")
        set_state(dest, state)
        (dest / "request.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        def run():
            def progress(message):
                state.update(status="running", message=message)
                set_state(dest, state)

            try:
                progress("Preparing input")
                if kind == "demo":
                    from ..demo import create_demo

                    payload.update(create_demo(dest / "demo-input", kind=state["example_kind"]))
                if kind == "python-dicom":
                    from ..raw import convert_dicom_python

                    converted = {}
                    for key, identity in (("bold", payload["bold_series"]), ("t1w", payload["t1_series"])):
                        progress(f"Python DICOM 转换：{key}")
                        converted[key] = convert_dicom_python(payload["source"], dest / "converted" / key,
                                                               series_id=identity, kind=key)
                    state.update(status="complete", message="转换完成，继续核对采集参数。", converted=converted)
                elif kind == "python-preprocess":
                    from ..raw import PreprocessConfig, preprocess_fmri

                    result = preprocess_fmri(payload["bold"], payload["t1w"], dest / "preprocessed",
                                             sidecar=payload.get("sidecar"), t1_mask=payload.get("t1_mask"),
                                             config=PreprocessConfig(**payload.get("config", {})),
                                             template_dir=root / "templates", progress=progress)
                    state.update(status="complete", message="预处理完成，请检查配准和头动报告。",
                                 run=result.run, qc=result.qc)
                elif kind == "dicom":
                    from ..preprocessing import convert_dicom

                    progress("Converting DICOM to NIfTI + JSON")
                    convert_dicom(**payload, log=dest / "preprocessing.log")
                    state.update(
                        status="complete",
                        message="DICOM conversion finished. Verify series identity and organize BIDS before preprocessing.",
                    )
                elif kind == "preprocess":
                    from ..preprocessing import fmriprep_plan

                    plan = fmriprep_plan(**payload)
                    progress("fMRIPrep is running; see preprocessing.log")
                    plan.run(log=dest / "preprocessing.log")
                    state.update(
                        status="complete",
                        message="Preprocessing finished. Inspect fMRIPrep report, then scan derivatives for extraction.",
                    )
                elif kind == "atlas":
                    from ..atlases import fetch_atlas

                    info = fetch_atlas(payload["name"], data_dir=root / "atlases")
                    state.update(status="complete", message="Atlas ready", atlas=info)
                else:
                    from ..pipeline import extract_connectome

                    config = Config(**payload.get("config", {}))
                    result = extract_connectome(
                        payload["source"],
                        config=config,
                        progress=progress,
                        **{
                            k: payload.get(k) or None
                            for k in ("atlas", "rois", "confounds", "mask", "reference")
                        },
                    )
                    if kind == "extract":
                        parent = Path(payload["source"]).resolve().parent
                        if (parent / "output_hashes.json").is_file() and (parent / "preprocessing.json").is_file():
                            from ..raw import load_preprocessed
                            native = load_preprocessed(parent)
                            if Path(native.run["bold"]) == Path(payload["source"]).resolve():
                                result.provenance["raw_preprocessing"] = native.provenance
                                result.qc["raw_preprocessing"] = native.qc
                                result.qc["warnings"].extend(native.qc["limitations"])
                    if kind == "demo":
                        result.provenance["synthetic"] = state["example_kind"] == "synthetic"
                        if state["example_kind"] == "rest01":
                            example = json.loads((dest / "demo-input/example.json").read_text(encoding="utf-8"))
                            result.provenance["example"] = example
                            result.qc["warnings"].extend(example["limitations"])
                    if payload.get("guidance"):
                        from ..presets import dataset_preset

                        guide = payload["guidance"]
                        result.provenance["workflow"] = {
                            **guide,
                            "official_preset": dataset_preset(guide["dataset"], guide["variant"]),
                        }
                    progress("Exporting matrix, eight views and offline 3D report")
                    result.save(dest / "result")
                    shutil.make_archive(str(dest / "result"), "zip", dest / "result")
                    state.update(
                        status="complete",
                        message="Extraction complete",
                        qc=result.qc,
                        result_dir=str(dest / "result"),
                    )
            except Exception as exc:
                state.update(status="failed", message=str(exc), error_type=type(exc).__name__)
            finally:
                set_state(dest, state)
                with lock:
                    active.discard(job_id)

        executor.submit(run)
        return state.copy()

    @app.get(
        "/api/health",
        tags=["System"],
        response_model=HealthResponse,
        summary="Read service version and workspace",
    )
    def health():
        return {"status": "ok", "version": __version__, "workspace": str(root)}

    @app.post("/api/python/dicom/scan", tags=["Python preprocessing"],
              summary="Inventory local MR DICOM series without returning patient identifiers")
    def python_dicom_scan(payload: PathRequest):
        from ..raw import scan_dicom
        return scan_dicom(payload.path)

    @app.post("/api/python/discover", tags=["Python preprocessing"],
              summary="List raw BIDS BOLD/T1 candidates within subject/session")
    def python_discover(payload: PathRequest):
        from ..raw import discover_raw
        return discover_raw(payload.path)

    @app.post("/api/python/dicom/run", tags=["Python preprocessing"], response_model=JobState,
              response_model_exclude_unset=True, summary="Queue Python conversion of selected BOLD and T1 series")
    def python_dicom_run(payload: PythonDicomRequest):
        return submit(payload.model_dump(mode="json"), "python-dicom")

    @app.post("/api/python/inspect", tags=["Python preprocessing"],
              summary="Validate raw BOLD/T1 geometry, TR and slice-timing readiness")
    def python_inspect(payload: PythonPreprocessRequest):
        from ..raw import PreprocessConfig, inspect_raw
        return inspect_raw(payload.bold, payload.t1w, sidecar=payload.sidecar,
                           config=PreprocessConfig(**payload.config.model_dump()))

    @app.post("/api/python/preprocess", tags=["Python preprocessing"], response_model=JobState,
              response_model_exclude_unset=True, summary="Queue in-process Python BOLD/T1 preprocessing")
    def python_preprocess(payload: PythonPreprocessRequest):
        info = python_inspect(payload)
        if not info["ready"]:
            raise InputError(" ".join(info["missing"]))
        return submit(payload.model_dump(mode="json"), "python-preprocess")

    @app.get("/api/jobs/{job_id}/preprocessing/{name}", tags=["Python preprocessing"],
             response_class=FileResponse, summary="View a completed Python preprocessing QC artifact")
    def python_qc(job_id: str, name: str):
        if name not in {"qc.html", "alignment.png", "motion.png", "qc.json", "preprocessing.json", "stages.json"}:
            raise HTTPException(404, "Unknown QC artifact")
        path = folder(job_id) / "preprocessed" / name
        if not path.is_file():
            raise HTTPException(404, "QC artifact is not ready")
        return FileResponse(path)

    @app.get(
        "/api/presets",
        tags=["Inputs"],
        response_model=PresetsResponse,
        summary="Read source-attributed dataset/protocol hints",
    )
    def presets():
        from ..presets import dataset_presets

        return dataset_presets()

    @app.get(
        "/api/setup",
        tags=["System"],
        response_model=SetupResponse,
        summary="Suggest new output paths and an existing FS_LICENSE",
    )
    def setup_defaults():
        import os

        license_path = os.environ.get("FS_LICENSE", "")
        return {
            "conversion_output": str(root / "converted" / uuid.uuid4().hex[:12]),
            "preprocessing_output": str(root / "preprocessed" / uuid.uuid4().hex[:12]),
            "license_file": license_path if Path(license_path).is_file() else "",
        }

    @app.post(
        "/api/input-suggestions",
        response_model=SuggestionsResponse,
        response_model_exclude_unset=True,
        tags=["Inputs"],
        summary="Infer metadata and companions; may download a suggested atlas",
    )
    def suggest_input(payload: SuggestionsRequest):
        payload = payload.model_dump(mode="json", exclude_unset=True)
        from ..workflow import input_suggestions
        from ..pipeline import fingerprint
        from ..atlases import fetch_atlas

        try:
            suggestion = input_suggestions(payload["source"], overrides=payload.get("overrides"))
            source_path = str(Path(payload["source"]).expanduser().resolve())
            source_hash = None
            # Reuse spatial choices only for the exact same input bytes and intact companion files.
            for record in sorted(
                jobs_dir.glob("*/result/provenance.json"), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                prior = json.loads(record.read_text(encoding="utf-8"))
                files = prior.get("inputs", {})
                if files.get("source", {}).get("path") != source_path:
                    continue
                source_hash = source_hash or fingerprint(source_path)["sha256"]
                if files["source"]["sha256"] != source_hash:
                    continue
                suggestion["config"].update(
                    {k: prior["config"].get(k) for k in ("data_space", "atlas_space")}
                )
                for key in ("atlas", "rois", "reference", "mask", "confounds"):
                    f = files.get(key)
                    if f and Path(f["path"]).is_file() and fingerprint(f["path"])["sha256"] == f["sha256"]:
                        suggestion["paths"].setdefault(key, f["path"])
                suggestion["notes"].append("已复用同一文件先前确认的空间与配套文件（SHA-256 一致）。")
                break
            space = suggestion["info"].get("space") or suggestion["config"].get("data_space")
            if space:
                suggestion["config"]["data_space"] = space
            if (
                suggestion["info"]["format"] == "volume"
                and not suggestion["paths"].get("atlas")
                and space in {"MNI152NLin6Asym", "MNIColin27"}
            ):
                try:
                    atlas = fetch_atlas(
                        "schaefer100" if space == "MNI152NLin6Asym" else "aal116", data_dir=root / "atlases"
                    )
                    suggestion["paths"].update({k: atlas[k] for k in ("atlas", "rois")})
                    suggestion["config"]["atlas_space"] = atlas["space"]
                    suggestion["notes"].append(
                        f"已按明确空间载入 {atlas['name']}，可在高级设置更换；这是软件建议。"
                    )
                except Exception as exc:
                    suggestion["notes"].append(f"推荐图谱暂未载入，请手动选择：{exc}")
            return suggestion
        except (ValueError, OSError, TypeError, KeyError) as exc:
            raise InputError(str(exc)) from exc

    @app.post(
        "/api/preflight",
        tags=["Inputs"],
        response_model=InputInfo,
        response_model_exclude_unset=True,
        summary="Validate one run at input, spatial or review stage",
    )
    def workflow_check(payload: PreflightRequest):
        payload = payload.model_dump(mode="json")
        from ..workflow import preflight

        try:
            return preflight(payload, stage=payload.get("stage", "review"))
        except (ValueError, OSError, TypeError, KeyError) as exc:
            raise InputError(str(exc)) from exc

    @app.post(
        "/api/inspect",
        tags=["Inputs"],
        response_model=InputInfo,
        response_model_exclude_unset=True,
        summary="Read file structure or list derivative runs",
    )
    def inspect(payload: PathRequest):
        from ..io import inspect_input

        return inspect_input(payload.path)

    @app.post(
        "/api/discover",
        tags=["Inputs"],
        response_model=list[RunRecord],
        summary="Discover separate fMRIPrep preprocessed volume runs",
    )
    def discover(payload: PathRequest):
        from ..io import discover_bids

        return discover_bids(payload.path)

    @app.post(
        "/api/upload",
        tags=["Inputs"],
        response_model=UploadResponse,
        summary="Upload one file (4 GiB maximum), preserving existing files",
    )
    async def upload(file: UploadFile = File(...), session: str = Form(...)):
        if not re.fullmatch(r"[a-f0-9-]{32,36}", session):
            raise HTTPException(422, "Invalid upload session")
        name = (file.filename or "").replace("\\", "/").split("/")[-1]
        if not name or name in {".", ".."} or any(c in name for c in ':<>|"'):
            raise HTTPException(422, "Invalid filename")
        dest = root / "uploads" / session
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / name
        if target.exists():
            raise HTTPException(
                409, "Filename already uploaded. Start a new session or use the existing path."
            )
        size = 0
        try:
            with target.open("xb") as stream:
                while chunk := await file.read(4 * 1024 * 1024):
                    size += len(chunk)
                    if size > 4 * 1024**3:
                        raise HTTPException(413, "Upload exceeds 4 GiB; use a local file path.")
                    stream.write(chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return {"path": str(target), "size_bytes": size}

    @app.post(
        "/api/jobs",
        tags=["Jobs"],
        response_model=JobState,
        response_model_exclude_unset=True,
        summary="Queue one extraction; does not wait for completion",
    )
    def create_job(payload: ExtractionRequest):
        payload = payload.model_dump(mode="json")
        if not payload.get("source"):
            raise InputError("Choose a source file first.")
        try:
            Config(**payload.get("config", {}))
        except TypeError as exc:
            raise InputError(str(exc)) from exc
        from ..workflow import validate_guidance

        validate_guidance(payload)
        return submit(payload)

    @app.post(
        "/api/demo",
        tags=["Jobs"],
        response_model=JobState,
        response_model_exclude_unset=True,
        summary="Process the bundled de-identified rest01 example (synthetic data only on explicit request)",
    )
    def demo(kind: Literal["rest01", "synthetic"] = "rest01"):
        """Run packaged example inputs locally; no participant data are downloaded.

        The default rest01 uses the reviewed ROI signals, confounds and brain-only
        reference mask. Its acquisition/processing record is included in provenance.
        kind=synthetic explicitly selects the artificial 12-ROI developer fixture.
        """
        return submit({"example_kind": kind}, "demo")

    @app.post(
        "/api/atlas",
        tags=["Inputs"],
        response_model=JobState,
        response_model_exclude_unset=True,
        summary="Queue a supported-atlas download",
    )
    def atlas(payload: AtlasRequest):
        payload = payload.model_dump(mode="json")
        if payload.get("name") not in {"schaefer100", "schaefer200", "schaefer400", "aal116"}:
            raise InputError("Unknown atlas")
        return submit(payload, "atlas")

    @app.post(
        "/api/preprocess/plan",
        tags=["Raw data"],
        response_model=CommandResponse,
        response_model_exclude_unset=True,
        summary="Inspect a pinned fMRIPrep command and minimum BOLD/T1 inventory",
    )
    def plan(payload: PreprocessRequest):
        payload = payload.model_dump(mode="json")
        from ..preprocessing import fmriprep_plan
        from ..workflow import check_raw_bids

        command = fmriprep_plan(**payload).to_dict()
        command["inventory"] = check_raw_bids(payload)
        return command

    @app.post(
        "/api/preprocess/run",
        tags=["Raw data"],
        response_model=JobState,
        response_model_exclude_unset=True,
        summary="Queue external Docker fMRIPrep execution",
    )
    def preprocess(payload: PreprocessRequest):
        payload = payload.model_dump(mode="json")
        from ..preprocessing import fmriprep_plan
        from ..workflow import check_raw_bids

        fmriprep_plan(**payload)
        check_raw_bids(payload)
        return submit(payload, "preprocess")

    @app.post(
        "/api/dicom/plan",
        tags=["Raw data"],
        response_model=CommandResponse,
        response_model_exclude_unset=True,
        summary="Inspect an external dcm2niix conversion command",
    )
    def dicom_command(payload: DicomRequest):
        payload = payload.model_dump(mode="json")
        from ..preprocessing import dicom_plan

        return dicom_plan(payload["source"], payload["output"]).to_dict()

    @app.post(
        "/api/dicom/run",
        tags=["Raw data"],
        response_model=JobState,
        response_model_exclude_unset=True,
        summary="Queue DICOM conversion to a new output directory",
    )
    def dicom_run(payload: DicomRequest):
        payload = payload.model_dump(mode="json")
        from ..preprocessing import dicom_plan

        dicom_plan(payload["source"], payload["output"])
        return submit({"source": payload["source"], "output": payload["output"]}, "dicom")

    @app.get(
        "/api/jobs/{job_id}/views",
        tags=["Results"],
        response_class=FileResponse,
        summary="Export eight views for the current threshold/selection",
    )
    def view_export(
        job_id: str,
        threshold: float = Query(
            0.3, ge=0, le=1, description="Inclusive |coefficient| cutoff; zero edges excluded."
        ),
        max_edges: int = Query(
            200, ge=0, le=10000, description="Cap after threshold and ROI/edge selection."
        ),
        selection_kind: str | None = None,
        selection_id: str | None = None,
        opacity: float = Query(0.28, ge=0, le=1),
        theme: str = "paper",
        format: str = "svg",
    ):
        import hashlib
        from types import SimpleNamespace
        import numpy as np
        from ..plotting import plot_views, PLOT_LOCK

        if format not in {"svg", "pdf", "png"} or max_edges > 10000:
            raise InputError("Unsupported view export format or edge limit.")
        dest = folder(job_id)
        source = dest / "result" / "result.json"
        if not source.is_file():
            raise HTTPException(404, "Result is not ready")
        selection = {"kind": selection_kind, "id": selection_id} if selection_kind else None
        params = dict(
            threshold=threshold, max_edges=max_edges, selection=selection, opacity=opacity, theme=theme
        )
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:24]
        exports = dest / "view-exports"
        exports.mkdir(exist_ok=True)
        path = exports / f"{key}.{format}"
        with PLOT_LOCK:
            if not path.exists():
                data = json.loads(source.read_text(encoding="utf-8"))
                data["connectivity"] = np.asarray(data["connectivity"])
                plot_views(SimpleNamespace(**data), path, **params)
                (exports / f"{key}.json").write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
        return FileResponse(path, filename=f"eight-views-current.{format}")

    @app.get(
        "/api/jobs",
        tags=["Jobs"],
        response_model=list[JobState],
        response_model_exclude_unset=True,
        summary="List up to 100 jobs, most recently modified first",
    )
    def jobs():
        with lock:
            return [
                json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(jobs_dir.glob("*/status.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            ][:100]

    @app.get(
        "/api/jobs/{job_id}",
        tags=["Jobs"],
        response_model=JobState,
        response_model_exclude_unset=True,
        summary="Poll persisted job state",
    )
    def job(job_id: str):
        with lock:
            return json.loads((folder(job_id) / "status.json").read_text(encoding="utf-8"))

    @app.get(
        "/api/jobs/{job_id}/files/{name}",
        tags=["Results"],
        response_class=FileResponse,
        summary="Download a named result artifact or preprocessing log",
    )
    def artifact(job_id: str, name: str):
        dest = folder(job_id)
        if name == "result.zip":
            path = dest / name
        elif name == "preprocessing.log":
            path = dest / name
        else:
            if name not in {
                "result.json",
                "matrix.png",
                "matrix.svg",
                "matrix.pdf",
                "eight_views.png",
                "eight_views.svg",
                "eight_views.pdf",
                "report.html",
                "connectivity.csv",
                "connectivity.npy",
                "fisher_z.csv",
                "fisher_z.npy",
                "timeseries.npy",
                "manifest.json",
                "qc.json",
                "provenance.json",
                "timeseries.tsv",
                "rois.tsv",
                "samples.tsv",
            }:
                raise HTTPException(404, "Unknown artifact")
            path = dest / "result" / name
        if not path.is_file():
            raise HTTPException(404, "Artifact is not ready")
        return FileResponse(
            path, filename=name if name.endswith((".zip", ".csv", ".tsv", ".npy", ".pdf", ".svg")) else None
        )

    @app.post(
        "/api/jobs/{job_id}/network-input",
        tags=["Network analysis"],
        summary="Transfer a completed extraction to network analysis with its ROI mapping",
    )
    def network_input(job_id: str):
        """Copy the full matrix and processing metadata to the local network workspace.

        Only completed extraction jobs are accepted. Returns an uploaded-file record
        and the corresponding input options for /networks/api/v1/jobs. The source
        matrix is not thresholded, and no signal cleaning/correlation is repeated.
        Repeated calls reuse the prepared input. No source files leave this server.
        """
        import numpy as np
        from ..network import load_connectome
        from ..network.io import inspect_file
        from ..network.web.storage import now

        dest = folder(job_id)
        state = json.loads((dest / "status.json").read_text(encoding="utf-8"))
        if state.get("status") != "complete" or not (dest / "result/result.json").is_file():
            raise HTTPException(409, "A completed extraction result is required.")
        store = network_app.state.store
        with lock:
            prepared = dest / "network-input.json"
            if prepared.exists():
                entry = json.loads(prepared.read_text(encoding="utf-8"))
                try:
                    store.get("uploads", entry["file"]["id"])
                    return entry
                except KeyError:
                    pass
            dataset = load_connectome(dest / "result")
            identifier = uuid.uuid4().hex
            record = {"id": identifier, "name": f"connectome-{job_id[:8]}.npy",
                      "suffix": ".npy", "created_at": now()}
            path = store.upload_path(record)
            np.save(path, dataset.data, allow_pickle=False)
            record.update(inspect_file(path, source_name=record["name"]))
            record["bytes"] = path.stat().st_size
            options = {"kind": "connectivity", "matrix_kind": "correlation",
                       "roi_ids": dataset.roi_ids, "labels": dataset.labels,
                       "coordinates": dataset.coordinates.tolist() if dataset.coordinates is not None else None,
                       "metadata": dataset.metadata}
            # Bound metadata stays server-side; the browser receives only a compact preview.
            record["brainfc_input"] = options
            record["brainfc_job"] = job_id
            store.put("uploads", record)
            public_record = {k: v for k, v in record.items() if k != "brainfc_input"}
            entry = {"file": public_record, "n_rois": dataset.n_rois,
                     "has_geometry": "brainfc_geometry" in dataset.metadata,
                     "input": {"kind": "connectivity", "matrix_kind": "correlation"}}
            prepared.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
            return entry

    app.mount("/networks", network_app, name="networks")
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")
    if (static / "reference").is_dir():
        app.mount("/reference", StaticFiles(directory=static / "reference", html=True), name="reference")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static / "index.html")

    return app
