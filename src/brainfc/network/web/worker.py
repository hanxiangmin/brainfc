"""One isolated CPU worker at a time, with durable progress and cancellation."""
from __future__ import annotations

import json
import multiprocessing
import os
import threading
import uuid

from .storage import Store, now


def run_job(workspace, job_id):
    # Scope thread limits to this subprocess; importing the library changes no environment.
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    from threadpoolctl import threadpool_limits
    from brainfc.network import AnalysisConfig, analyze, load_data
    store = Store(workspace)
    job = store.get("jobs", job_id)
    completed, errors = [], []
    try:
        config = AnalysisConfig.from_dict(job["analysis"])
        total = len(job["file_ids"])
        with threadpool_limits(limits=1):
            for i, file_id in enumerate(job["file_ids"]):
                if store.get("jobs", job_id)["status"] == "cancelled":
                    return
                upload = store.get("uploads", file_id)
                try:
                    def progress(percent, message):
                        store.patch_job(job_id, progress=round((i + percent / 100) / total * 95, 1),
                                        message=f"{i+1}/{total} · {upload['name']} · {message}")
                    # Imported extractions own their matrix semantics and ROI mapping.
                    # UI defaults must not overwrite them, especially geometry/provenance.
                    options = upload.get("brainfc_input", job["input"])
                    dataset = load_data(store.upload_path(upload), source_name=upload["name"], **options)
                    dataset.metadata["source_name"] = upload["name"]
                    result = analyze(dataset, config, progress=progress)
                    result_id = uuid.uuid4().hex
                    destination = store.result_path(result_id)
                    temporary = destination.with_suffix(".tmp")
                    temporary.write_text(json.dumps(result.to_dict(), ensure_ascii=False, allow_nan=False), encoding="utf-8")
                    temporary.replace(destination)
                    record = {"id": result_id, "name": upload["name"], "job_id": job_id,
                              "file_id": file_id, "created_at": now()}
                    store.put("results", record)
                    completed.append({"id": result_id, "name": upload["name"]})
                except Exception as exc:
                    errors.append({"name": upload["name"], "message": f"{type(exc).__name__}: {exc}"})
                store.patch_job(job_id, results=completed, errors=errors)
        store.patch_job(job_id, status="completed" if completed else "failed", progress=100,
            message=f"{len(completed)} completed; {len(errors)} failed", results=completed, errors=errors)
    except Exception as exc:
        store.patch_job(job_id, status="failed", message=f"{type(exc).__name__}: {exc}", errors=errors)


class JobManager:
    def __init__(self, store):
        self.store = store
        self.stop_event = threading.Event()
        self.guard = threading.RLock()
        self.process = None
        self.active_id = None
        self.thread = None

    def start(self):
        for job in self.store.all("jobs"):
            if job["status"] in {"queued", "running"}:
                self.store.patch_job(job["id"], status="interrupted", message="Service restarted. Retry to run again.")
        self.thread = threading.Thread(target=self._schedule, daemon=True, name="hicbrain-queue")
        self.thread.start()

    def _schedule(self):
        while not self.stop_event.wait(.25):
            with self.guard:
                if self.process is not None:
                    if self.process.is_alive():
                        continue
                    self.process.join()
                    job = self.store.get("jobs", self.active_id)
                    if job["status"] == "running":
                        self.store.patch_job(self.active_id, status="failed", message="Worker exited before completing. Retry available.")
                    self.process.close()
                    self.process = None
                    self.active_id = None
                queued = [j for j in reversed(self.store.all("jobs")) if j["status"] == "queued"]
                if queued:
                    self.active_id = queued[0]["id"]
                    self.store.patch_job(self.active_id, status="running", message="Starting local worker")
                    self.process = multiprocessing.get_context("spawn").Process(target=run_job,
                        args=(str(self.store.root), self.active_id), daemon=True)
                    self.process.start()

    def cancel(self, job_id):
        with self.guard:
            job = self.store.get("jobs", job_id)
            if job["status"] in {"queued", "running"}:
                job = self.store.patch_job(job_id, status="cancelled", message="Cancelled by user")
                if self.active_id == job_id and self.process and self.process.is_alive():
                    self.process.terminate()
                    self.process.join(timeout=5)
            return job

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        with self.guard:
            if self.process:
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(timeout=5)
                    self.store.patch_job(self.active_id, status="interrupted", message="Service stopped. Retry available.")
                self.process.close()
                self.process = None
