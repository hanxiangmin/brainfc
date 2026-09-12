"""Guided UI preflight; the extraction core still performs full numerical checks."""

from pathlib import Path
import nibabel as nib
import numpy as np
from .io import inspect_input, numeric_table
from .models import Config, InputError
from .presets import dataset_preset


def input_suggestions(path, *, overrides=None):
    """Suggest text header handling and exactly matched local companions.

    path is a single-run file. overrides is an optional Config field dict taking
    precedence over header inference. Returns {'info': check_input output,
    'config': inferred/overridden settings, 'paths': matched files, 'notes': []}.
    All-numeric first non-comment line is considered data; numeric ROI headers
    require an explicit override. No downloads or history reuse in this Python
    function; /api/input-suggestions adds those web-workspace features."""
    import re
    from .io import discover_bids, TABLE_SUFFIXES

    p = Path(path).expanduser().resolve()
    settings = {}
    if p.suffix.lower() in TABLE_SUFFIXES - {".npy", ".npz", ".mat"}:
        with p.open(encoding="utf-8-sig") as stream:
            line = next(
                (line.strip() for line in stream if line.strip() and not line.lstrip().startswith("#")), ""
            )
        try:
            [float(v) for v in re.split(r"[,\t\s]+", line)]
            settings["table_header"] = False
        except ValueError:
            settings["table_header"] = True
    settings.update(overrides or {})
    info = check_input(p, Config(**settings))
    companions = {}
    if "_desc-preproc_bold.nii" in p.name:
        found = next((run for run in discover_bids(p.parent) if Path(run["bold"]).resolve() == p), None)
        if found:
            companions = {k: found[k] for k in ("confounds", "mask") if found.get(k)}
            if found.get("mask"):
                companions["reference"] = found["mask"]
            # Native Python derivatives bind the exact nuisance design to their
            # source path; never silently treat matrix coefficients as motion6.
            import json
            record = p.parent / "run.json"
            provenance = p.parent / "preprocessing.json"
            if record.is_file() and provenance.is_file():
                run = json.loads(record.read_text(encoding="utf-8"))
                if Path(run.get("bold", "")).resolve() == p:
                    native = json.loads(provenance.read_text(encoding="utf-8"))
                    settings.setdefault("confound_columns", native["confound_columns"])
                    settings.setdefault("discard", native["config"]["discard"])
    return {"info": info, "config": settings, "paths": companions, "notes": []}


def check_raw_bids(payload):
    """Check minimum raw BIDS BOLD/T1 inventory, without preprocessing.

    payload requires bids_dir and may contain participant (with/without sub-).
    Rejects DatasetType='derivative', absent BOLD/T1, or non-4D/short BOLD.
    Returns {'bold_runs': int, 'scope': str}. Does not validate all JSON acquisition
    fields or BIDS inheritance; fMRIPrep's full BIDS validator is still required."""
    import json

    root = Path(payload["bids_dir"]).expanduser().resolve()
    description = root / "dataset_description.json"
    if not description.is_file():
        raise InputError("先将原始 NIfTI + JSON 整理成 BIDS，并提供 dataset_description.json。")
    if json.loads(description.read_text(encoding="utf-8-sig")).get("DatasetType") == "derivative":
        raise InputError("这里需要原始 BIDS，不能再次预处理 derivatives。")
    participant = (payload.get("participant") or "").removeprefix("sub-")
    subjects = [root / f"sub-{participant}"] if participant else sorted(root.glob("sub-*"))
    found = []
    for subject in subjects:
        bold = sorted(subject.rglob("*_bold.nii*"))
        if not bold:
            continue
        if not list(subject.rglob("*_T1w.nii*")):
            raise InputError(f"{subject.name} 缺少 T1w；当前流程需要 BOLD 和 T1。")
        for path in bold:
            image = nib.load(path)
            if image.ndim != 4 or image.shape[3] < 3:
                raise InputError(f"{path.name} 不是有效的 4D BOLD 时序。")
        found.extend(str(p) for p in bold)
    if not found:
        raise InputError("未在 sub-* 目录找到 *_bold.nii[.gz]。请先核对 BIDS 文件组织。")
    return {
        "bold_runs": len(found),
        "scope": "Minimum BOLD/T1 inventory; full BIDS validation remains in fMRIPrep.",
    }


def check_input(path, config=None):
    """Inspect one run and add dimensions, TR source and atlas requirements.

    path is a file; config is Config or None. Returns inspect_input metadata plus
    n_frames, needs_atlas, t_r, tr_source, and n_rois for tables. Known image time
    headers add header_t_r. Rejects symmetric square tables as suspected matrices,
    wrong image/time axes and conflicting JSON/header TR. Numerical ROI coverage,
    named-space matching and regression feasibility require further validation.
    Unlike the extraction core, this preflight is conservative about symmetric tables."""
    config = config or Config()
    info = inspect_input(path)
    fmt = info["format"]
    if fmt == "directory":
        raise InputError("请选择一次扫描文件；原始文件夹请使用原始数据流程。")
    if fmt == "timeseries-table":
        values, _ = numeric_table(
            path, header=config.table_header, variable=config.variable, transpose=config.transpose
        )
        info.update(n_frames=int(values.shape[0]), n_rois=int(values.shape[1]), needs_atlas=False)
        if values.shape[0] == values.shape[1] and np.allclose(values, values.T):
            raise InputError("此文件是对称方阵，疑似已有连接矩阵。请选择时间 × ROI 的时序文件。")
    else:
        img = nib.load(path)
        if fmt == "volume":
            if len(img.shape) != 4 or img.shape[3] < 3:
                raise InputError("需要包含多个时间点的 4D BOLD；T1、掩膜和单张指标图不能提取 FC。")
            info.update(n_frames=int(img.shape[3]), needs_atlas=True)
            unit = img.header.get_xyzt_units()[1] if hasattr(img.header, "get_xyzt_units") else "unknown"
            scale = {"sec": 1, "msec": 0.001, "usec": 0.000001}.get(unit)
            if scale:
                info["header_t_r"] = float(img.header.get_zooms()[3]) * scale
        elif fmt == "cifti":
            axes = [img.header.get_axis(i) for i in range(img.ndim)]
            if (
                len(axes) != 2
                or not isinstance(axes[0], nib.cifti2.SeriesAxis)
                or not isinstance(axes[1], (nib.cifti2.BrainModelAxis, nib.cifti2.ParcelsAxis))
            ):
                raise InputError("需要 dtseries / ptseries 时序；dconn / pconn 连接矩阵不能作为输入时序。")
            info.update(
                n_frames=img.shape[0],
                header_t_r=float(axes[0].step),
                needs_atlas=isinstance(axes[1], nib.cifti2.BrainModelAxis),
            )
        elif fmt == "gifti":
            arrays = [
                d.data for d in img.darrays if d.intent == nib.nifti1.intent_codes["NIFTI_INTENT_TIME_SERIES"]
            ]
            if not arrays:
                raise InputError("请选择 func.gii 时序，不是表面网格或 label.gii。")
            info.update(
                n_frames=arrays[0].shape[1] if len(arrays) == 1 and arrays[0].ndim == 2 else len(arrays),
                needs_atlas=True,
            )
    json_tr, header_tr = info.get("t_r"), info.get("header_t_r")
    if json_tr and header_tr and not np.isclose(json_tr, header_tr, rtol=1e-4, atol=1e-4):
        raise InputError("JSON 和影像头中的 TR 不一致；请核实源数据后重试。")
    info["t_r"] = json_tr or header_tr
    info["tr_source"] = "JSON" if json_tr else "影像头" if header_tr else "待确认"
    return info


def preflight(payload, *, stage="review"):
    """Validate a guided extraction request without calculating connectivity.

    payload contains source, optional atlas/rois/mask/reference/confounds paths and
    a plain config dict. stage='input' performs check_input only; 'spatial' also
    checks preprocessing declaration, spaces and companion paths; 'review' further
    checks TR, Nyquist, confound rows and retained-frame counts.
    Returns input metadata; review adds n_retained, confound_columns, effective_tr
    and validated=True. Raises InputError or file/parser errors on invalid inputs.
    Full ROI coverage, CIFTI alignment and cleaned-signal variance are checked only
    by extract_connectome. This function does not download or write files."""
    if stage not in {"input", "spatial", "review"}:
        raise InputError("stage must be input, spatial or review.")
    config = Config(**payload.get("config", {}))
    info = check_input(payload.get("source", ""), config)
    if stage == "input":
        return info
    if info["format"] != "timeseries-table":
        if not config.preprocessed:
            raise InputError("请先完成预处理并核对报告，再确认头动校正和空间配准。")
        space = config.data_space or info.get("space")
        if not space:
            raise InputError("请确认影像的实际空间。")
        if info.get("space") and config.data_space and config.data_space != info["space"]:
            raise InputError("数据空间与文件中的 space 标识冲突。")
        if info.get("needs_atlas") and not payload.get("atlas"):
            raise InputError("此类数据需要匹配的分区图谱，不能跳过。")
        if payload.get("atlas") and config.atlas_space != space:
            raise InputError("数据空间和图谱空间必须一致；重采样不能替代配准。")
        if payload.get("atlas"):
            atlas = nib.load(payload["atlas"])
            if info["format"] == "volume" and (
                isinstance(atlas, (nib.Cifti2Image, nib.gifti.GiftiImage)) or len(atlas.shape) != 3
            ):
                raise InputError("体积 BOLD 需要 3D 整数分区图谱。")
            if info["format"] == "cifti" and not isinstance(atlas, nib.Cifti2Image):
                raise InputError("dense CIFTI 需要相同 BrainModelAxis 的 dlabel 图谱。")
            if info["format"] == "gifti" and not isinstance(atlas, nib.gifti.GiftiImage):
                raise InputError("GIFTI 时序需要同半球、同顶点顺序的 label.gii。")
    for key in ("atlas", "rois", "mask", "reference", "confounds"):
        if payload.get(key) and not Path(payload[key]).is_file():
            raise InputError(f"{key} 文件不存在。")
    if stage == "spatial":
        return info
    tr = config.t_r or info.get("t_r")
    if config.t_r and info.get("t_r") and not np.isclose(config.t_r, info["t_r"], rtol=1e-4, atol=1e-4):
        raise InputError("填写的 TR 与当前扫描元数据冲突。请采用扫描值并核对预设方案。")
    if config.high_pass or config.low_pass:
        if not tr:
            raise InputError("启用滤波前必须确认 TR。")
        if any(v and v >= 0.5 / tr for v in (config.high_pass, config.low_pass)):
            raise InputError("滤波频率必须小于 Nyquist 频率 1 / (2 × TR)。")
    if info["n_frames"] - config.discard < config.min_samples:
        raise InputError("丢弃初始帧后不足最低时间点数。")
    from .pipeline import _confounds

    _, keep, confound_qc = _confounds(payload.get("confounds") or None, info["n_frames"], config)
    if int(keep.sum()) < config.min_samples:
        raise InputError("头动 / 初始帧剔除后不足最低时间点数。")
    return {
        **info,
        "n_retained": int(keep.sum()),
        "confound_columns": confound_qc["confound_columns"],
        "effective_tr": tr,
        "validated": True,
    }


def validate_guidance(payload):
    """Validate optional GUI decisions attached to an extraction payload.

    Returns None when guidance is absent (standard API clients need no UI clicks).
    Otherwise requires recognized dataset/variant, source/spatial/denoise/review
    confirmations, explicit skipped confounds/reference choices and raw-data QC
    confirmation when applicable, then runs preflight. Returns a copy enriched
    with official_preset. It never applies preset hints to Config automatically."""
    guide = payload.get("guidance")
    if guide is None:
        return None  # Standard API callers use the same scientific core without UI state.
    if not isinstance(guide, dict):
        raise InputError("Invalid workflow record.")
    preset = dataset_preset(guide.get("dataset"), guide.get("variant"))
    if not all(
        guide.get(k) is True
        for k in ("source_confirmed", "spatial_confirmed", "denoise_confirmed", "review_confirmed")
    ):
        raise InputError("请按顺序完成数据、空间、去噪和最终复核。")
    if not payload.get("confounds") and guide.get("confounds_decision") not in {"upstream", "skip"}:
        raise InputError("未提供混杂变量时，请明确选择保留上游去噪或跳过。")
    if not payload.get("reference") and guide.get("reference_decision") != "skip":
        raise InputError("请明确确认是否跳过可选的解剖参考。")
    if guide.get("input_kind", "").startswith("raw") and not guide.get("raw_qc_confirmed"):
        raise InputError("原始数据需完成预处理并确认质控。")
    preflight(payload)
    return {**guide, "official_preset": preset}
