# 输出文件、质控与来源

## Connectome

设原始时间点数 N、保留点数 T、脑区数 R：

| 属性 | 类型/形状 | 约定 |
|---|---|---|
| `timeseries` | float ndarray `(T,R)` | 清理后的时间×脑区 |
| `connectivity` | float ndarray `(R,R)` | 对称有符号系数；对角线 1 |
| `fisher_z` | float ndarray `(R,R)` | 截断后 atanh；对角线 0 |
| `rois` | 长度 R 的 dict 列表 | 决定所有矩阵行列顺序 |
| `sample_indices` | int ndarray `(T,)` | 在原始 N 帧中的零起始位置 |
| `qc` | dict | 计数、参数、提醒 |
| `provenance` | dict | 来源、实际参数、版本和 ROI 顺序 |
| `geometry` | dict 或 None | 仅显示；原始解剖体积不会写入这里 |

体积/标签图谱按正整数标签升序；表格保持列顺序；ptseries 保持 ParcelsAxis 名称顺序。不能根据其他项目图谱的行数猜这里的 ROI 顺序。

## save() 写出的文件

| 文件 | 内容 |
|---|---|
| `connectivity.npy` | 完整 R×R 数值，无标签行/列 |
| `connectivity.csv` | 同矩阵；首列标题 roi_id，行列都是 ROI ID |
| `fisher_z.npy/.csv` | 独立 Fisher-z 数组/带标签 CSV |
| `timeseries.npy` | 清理后的 T×R 数值 |
| `timeseries.tsv` | 首行 ROI ID；没有额外索引列 |
| `rois.tsv` | ROI 元数据；coordinates 展开为 x/y/z |
| `samples.tsv` | 一列 `original_volume_index`，从 0 开始 |
| `qc.json` | 完整 QC 字典 |
| `provenance.json` | 完整来源字典 |
| `result.json` | schema_version=1 的报告数据，默认不含 timeseries |
| `manifest.json` | 其他输出文件的 SHA-256；不包含自身 |
| `matrix.png/.svg/.pdf` | 完整矩阵；`figures=True` 时写出 |
| `eight_views.png/.svg/.pdf` | 所有 ROI 有坐标且 figures=True 时写出 |
| `report.html` | report=True 时写出，内嵌 JS/CSS/数据 |

web 任务还生成 `result.zip`，其内容是 result 目录。`Connectome.save()` 本身不创建 ZIP。

`save` 创建临时同级目录，全部完成后改名为目标；失败清除临时导出。已有目标拒绝覆盖。绘图函数直接写图片时遵循 Matplotlib 覆盖规则。

## 重新读取数值

```python
from pathlib import Path
import json
import numpy as np
import pandas as pd

root = Path("./results/run-001")
matrix = np.load(root / "connectivity.npy", allow_pickle=False)
signals = np.load(root / "timeseries.npy", allow_pickle=False)
rois = pd.read_csv(root / "rois.tsv", sep="\t", dtype={"roi_id": str})
samples = pd.read_csv(root / "samples.tsv", sep="\t")
provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
assert matrix.shape == (len(rois), len(rois))
assert signals.shape[0] == len(samples)
```

当前没有 `load_result()` 或 `Connectome.load()`。报告 JSON 不含时序，不能单凭该 JSON 恢复全部 Connectome；如需重建对象，必须读取数值和元数据并自己检查一致性。

## QC 字段

| 字段 | 含义 |
|---|---|
| `n_input`, `n_retained`, `n_censored` | 原始、保留、唯一排除帧数 |
| `retained_fraction` | T/N |
| `n_rois` | R |
| `t_r` | 秒或 null |
| `duration_retained_seconds` | T×TR 或 null，不是连续时间跨度 |
| `confound_columns` | 实际回归列名 |
| `fd_mean`, `fd_max` | 所有有限原始 FD 的均值/最大值；没有 FD 为 null |
| `fd_censored` | FD 超阈或首行缺失的帧数；可以与其他原因重叠 |
| `nonsteady_censored` | 初始 discard 之后因非稳态删除的帧数 |
| `confound_nan_fill` | 允许的首行 derivative1 NaN→0 记录 |
| `confound_design_rank_with_intercept` | 有回归设计时的初步秩检查 |
| `shrinkage` | 仅 partial 方法的 Ledoit-Wolf 收缩系数 |
| `warnings` | 未提供混杂、坐标不完整、单位推断、依赖清理提醒等 |
| `format` | volume / cifti / gifti / timeseries-table |
| `roi_voxels`, `atlas_resampled`, `orientation`, `bold_shape`, `spatial_units` | 仅体积路径提供 |

不同格式的 QC 键集合不同，不应要求每个结果都具备体积专用键。`validated=True` 是 preflight 响应标记，不是科学质量通过证书。

## Provenance 字段

`software/version/created_utc` 标明软件、版本与 UTC 创建时间；`inputs` 为实际参与文件的绝对路径、SHA-256、字节数；`config` 是解析 TR/空间后的生效配置；`versions` 记录 NumPy/SciPy/NiBabel/Nilearn/scikit-learn 版本；`method/roi_order/fisher_z/operations/filter_censoring` 记录计算约定。

GUI 引导记录保存在可选 `workflow` 字段，包含用户确认、跳过理由、数据集具体方案及其官方来源。合成演示由演示命令写 `synthetic=True`。

来源中可能含本地目录名，分享报告前应知道报告包含哪些元数据。研究输入文件不打包进本库发布物。配对影像的指纹边界见 [输入格式](formats.md)。

## Geometry 和显示导出

`geometry` 包含 `space/units/orientation/source`；`brain.positions` 为展平 xyz，`brain.indices` 为展平三角面顶点索引；`parcels` 当前为空字典。有坐标但无参考/图谱影像时，brain 为两个空数组，可只显示节点/边。缺少完整坐标时 geometry 为 null。

完整 ZIP 的静态图使用生成时默认 |r|≥0.3、最多 200 边。网页当前选择的八视图需用面板导出，或调用 `/api/jobs/{id}/views`；后者缓存文件在 `view-exports/`，不会改写既有结果。GUI PNG 使用 WebGL，HTTP 的 PNG/SVG/PDF 使用 Matplotlib，同样的边集合但材质并不相同。
