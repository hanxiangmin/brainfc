"""Recover display geometry only for server-linked local extraction jobs."""
import json
from pathlib import Path

import nibabel as nib

from .storage import valid_id
from brainfc.imaging import parcel_geometry
from brainfc.models import InputError
from brainfc.pipeline import fingerprint


def restore_source_parcels(store, workspace, result_id, result):
    """Attach cached parcels without rewriting the original analysis or matrix.

    Only the server's result -> upload -> extraction-job link is trusted. The
    atlas path comes from that job's request, not imported result provenance;
    its bytes must match the extraction fingerprint, spaces and ordered ROI
    mapping must agree. Missing/changed inputs leave other displays available
    with an explicit reason. Nothing is downloaded or inferred from ROI count.
    """
    geometry = result.get("metadata", {}).get("brainfc_geometry")
    if not geometry or geometry.get("parcels"):
        return result
    reason = "该结果仅含脑轮廓与坐标，没有可用的分区图谱。可导入对应的 NIfTI 图谱。"
    try:
        record = store.get("results", result_id)
        upload = store.get("uploads", record["file_id"])
        job_id = upload.get("brainfc_job")
        if not job_id:
            result["metadata"]["parcel_surface_unavailable"] = reason
            return result
        folder = Path(workspace) / "jobs" / valid_id(job_id)
        request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
        source = json.loads((folder / "result/result.json").read_text(encoding="utf-8"))
        atlas_path = request.get("atlas")
        recorded = source.get("provenance", {}).get("inputs", {}).get("atlas", {})
        config = source.get("provenance", {}).get("config", {})
        rois = source["rois"]
        if (not atlas_path or not recorded.get("sha256")
                or config.get("atlas_space") != geometry["space"]
                or config.get("data_space") != geometry["space"]
                or [r["roi_id"] for r in rois] != result["roi_ids"]
                or rois != result["metadata"].get("roi_metadata")):
            raise InputError("该结果缺少可核实的原图谱、空间或脑区顺序；请导入对应图谱。")
        path = Path(atlas_path)
        if not path.is_file() or fingerprint(path)["sha256"] != recorded["sha256"]:
            raise InputError("提取时的图谱已移动或内容改变，无法自动恢复分区；请导入对应图谱。")
        cache = folder / "network-parcels.json"
        parcel_map = None
        if cache.is_file():
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved.get("atlas_sha256") == recorded["sha256"] and saved.get("rois") == rois:
                parcel_map = saved["parcels"]
        if parcel_map is None:
            parcel_map = parcel_geometry(nib.load(path), rois)
            temp = cache.with_suffix(".tmp")
            temp.write_text(json.dumps({"atlas_sha256": recorded["sha256"], "rois": rois,
                                        "parcels": parcel_map}, allow_nan=False), encoding="utf-8")
            temp.replace(cache)
        result["metadata"]["brainfc_geometry"] = {**geometry, "parcels": parcel_map}
    except (KeyError, ValueError, OSError, InputError) as exc:
        result["metadata"]["parcel_surface_unavailable"] = str(exc) if isinstance(exc, InputError) else reason
    return result
