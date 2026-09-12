"""Versioned, source-attributed acquisition hints, never universal denoising recipes."""

from copy import deepcopy
from .models import InputError

ADNI = "https://adni-lde.loni.usc.edu/wp-content/uploads/2017/07/ADNI3-MRI-protocols.pdf"
PPMI = "https://www.ppmi-info.org/sites/default/files/docs/PPMI_002_MRI_Imaging_Manual_Final_v1.0_20250122_Executed-1.pdf"
ABIDE = "https://github.com/preprocessed-connectomes-project/abide"
ADHD = "https://fcp-indi.s3.amazonaws.com/data/Projects/ADHD200/RawDataBIDS/Brown/task-rest_bold.json"
MDD = "https://rfmri.org/REST-meta-MDD"


def _variant(id, name, source, *, tr=None, notes="", upstream="", input_kind="volume"):
    return {
        "id": id,
        "name": name,
        "source": source,
        "t_r": tr,
        "notes": notes,
        "upstream": upstream,
        "input_kind": input_kind,
    }


_CATALOG = [
    {
        "id": "custom",
        "name": "自有数据 / 暂不指定",
        "variants": [
            _variant(
                "custom",
                "从文件读取，手动确认",
                "",
                notes="不套用公开数据集参数。TR、空间与处理记录以本次扫描为准。",
            )
        ],
    },
    {
        "id": "abide",
        "name": "ABIDE",
        "variants": [
            _variant(
                "raw",
                "ABIDE I / II 原始影像",
                "https://fcon_1000.projects.nitrc.org/indi/abide/",
                input_kind="raw-bids",
                notes="多站点采集，TR、切片时序与扫描长度因站点而异；从实际扫描 JSON / 头信息读取。",
            ),
            _variant(
                "pcp",
                "ABIDE PCP 已处理影像 / ROI 时序",
                ABIDE,
                notes="确认下载时的 pipeline、filtering 与 global-signal 策略；没有适用于所有 PCP 输出的统一去噪设置。",
                upstream="PCP 有不同处理管线及策略。仅当所选输出已完成去噪时，选择“保留上游去噪”。",
            ),
        ],
    },
    {
        "id": "adni",
        "name": "ADNI",
        "variants": [
            _variant(
                "auto",
                "阶段 / 方案待确认",
                "https://adni.loni.usc.edu/quick-start-guide-asset/MRI_tables.html",
                input_kind="raw-dicom",
                notes="ADNI 不同阶段及 Basic / Advanced 方案不同。采集参数以 DICOM 头信息为主。",
            ),
            _variant(
                "adni3-basic",
                "ADNI 3 · Basic（方案参考）",
                ADNI,
                tr=3.0,
                input_kind="raw-dicom",
                notes="官方方案约 TR 3 s，约 10 min；数值为方案参考，硬件和软件实现可能不同，需核对实际扫描。",
            ),
            _variant(
                "adni3-advanced",
                "ADNI 3 · Advanced（方案参考）",
                ADNI,
                tr=0.6,
                input_kind="raw-dicom",
                notes="官方方案约 TR 0.6 s，SMS 8，约 10 min；不能用于 Basic 或任意 ADNI 扫描。",
            ),
        ],
    },
    {
        "id": "adhd200",
        "name": "ADHD-200",
        "variants": [
            _variant(
                "auto",
                "站点待确认",
                "https://fcon_1000.projects.nitrc.org/indi/adhd200/",
                input_kind="raw-bids",
                notes="原始数据与 Athena / NIAK 等处理版本需区分；不跨站点套用 TR、初始帧或滤波参数。",
            ),
            _variant(
                "brown",
                "Brown · RawDataBIDS",
                ADHD,
                tr=2.0,
                input_kind="raw-bids",
                notes="Brown 官方 task-rest_bold.json：TR 2 s，TE 0.025 s，35 层。时间点数量以实际 4D 文件为准。",
            ),
        ],
    },
    {
        "id": "mdd",
        "name": "MDD / REST-meta-MDD",
        "variants": [
            _variant(
                "rest-meta",
                "REST-meta-MDD · 已处理时序",
                MDD,
                input_kind="table",
                notes="共享产物包含处理后指标；请选择真正的 ROI 时间序列，已有 FC 矩阵不能作为时间序列再次提取。",
                upstream="官方说明：参与者层面 Friston-24，组水平 mean FD 校正。组水平校正不等于单个受试者 FD 剔除。请核实具体时序版本，避免重复回归。",
            ),
            _variant(
                "raw",
                "MDD 原始数据（按站点核对）",
                MDD,
                input_kind="raw-bids",
                notes="MDD 是疾病类别，不是统一采集协议。REST-meta-MDD 处理说明不能自动套用到任意 MDD 数据。",
            ),
        ],
    },
    {
        "id": "ppmi",
        "name": "PPMI",
        "variants": [
            _variant(
                "auto",
                "批次 / 序列待确认",
                "https://www.ppmi-info.org/study-design/research-documents-and-sops",
                input_kind="raw-dicom",
                notes="按本次采集日期、扫描仪和 MRI 手册版本核对；不把 2025 年方案套用到历史扫描。",
            ),
            _variant(
                "2025-mb",
                "2025 手册 · Multiband 主 BOLD",
                PPMI,
                tr=1.0,
                input_kind="raw-dicom",
                notes="2025-01-22 手册表 3：TR 1 s，600 次测量，MB 4；反向相位编码的 10 帧序列用于畸变校正，不作为静息态主扫描。",
            ),
            _variant(
                "2025-alt",
                "2025 手册 · 非 Multiband 主 BOLD",
                PPMI,
                tr=2.5,
                input_kind="raw-dicom",
                notes="2025-01-22 手册表 7：TR 2.5 s，240 次测量；反向 10 帧序列用于畸变校正。具体站点参数可能略有差异。",
            ),
        ],
    },
]


def dataset_presets():
    """Return an independent copy of the source-attributed dataset catalog.

    Returns dict with version, datasets and policy. Each dataset has id/name and
    variants. Variants contain id/name/source, input_kind and acquisition hints/
    notes. Includes custom, ABIDE, ADNI, ADHD-200, MDD and PPMI. Offline operation;
    no participant files are fetched. Scan metadata must confirm TR hints."""
    return {
        "version": "2026-09-12",
        "datasets": deepcopy(_CATALOG),
        "policy": "扫描 JSON / 头信息优先；冲突必须核对。未明确规定的高低通、FD、初始帧、图谱不设为“官方默认”。",
    }


def dataset_preset(dataset="custom", variant="custom"):
    """Return one dataset/protocol variant as an independent dictionary.

    dataset and variant default to 'custom'. Use dataset_presets() for exact
    case-sensitive identifiers. Returns dataset, dataset_name, catalog_version
    and the selected variant's fields. Raises InputError for an unknown pair.
    This is a reference record, not a Config or a guaranteed scan-specific protocol."""
    for entry in _CATALOG:
        if entry["id"] == dataset:
            for item in entry["variants"]:
                if item["id"] == variant:
                    return {
                        "dataset": entry["id"],
                        "dataset_name": entry["name"],
                        "catalog_version": "2026-09-12",
                        **deepcopy(item),
                    }
    raise InputError("Unknown dataset / protocol variant.")
