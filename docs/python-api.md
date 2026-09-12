# Python 使用指南

## 公共入口

```python
from brainfc import (
    Config, Connectome, InputError, extract_connectome,
    inspect_input, discover_bids, fetch_atlas,
    dataset_presets, dataset_preset,
)
```

以上是顶层导出的 9 个公共对象。其余处理函数按模块导入；所有函数、方法的真实签名和 docstring 见 [完整参考](api-reference.md)。本库采用 Python 包接口，依赖 NumPy/NiBabel/Nilearn 等科学计算库。

| 模块 | 函数 / 对象 | 用途 |
|---|---|---|
| `models` | `Config`, `Connectome`, `InputError` | 参数、结果、输入异常 |
| `pipeline` | `extract_connectome`, `fingerprint` | 完整单 run 提取；文件哈希 |
| `io` | `inspect_input`, `discover_bids`, `numeric_table`, `metadata`, `sidecar_path` | 读取与格式/配套信息 |
| `imaging` | `roi_table`, `make_rois`, `validate_volume`, `label_values` | 标签、ROI 映射、空间图像检查 |
| `imaging` | `volume_timeseries`, `cifti_timeseries`, `gifti_timeseries`, `brain_geometry` | 底层均值提取与显示表面 |
| `atlases` | `fetch_atlas` | 显式下载/缓存图谱 |
| `preprocessing` | `CommandPlan`, `dicom_plan`, `convert_dicom`, `fmriprep_plan` | 外部原始数据处理计划与执行 |
| `workflow` | `input_suggestions`, `check_input`, `preflight`, `check_raw_bids`, `validate_guidance` | 输入识别、引导检查与流程记录 |
| `presets` | `dataset_presets`, `dataset_preset` | 官方方案来源及采集提示 |
| `plotting` | `edges_of`, `plot_matrix`, `plot_views` | 显示连接选择与图像 |
| `export` | `save_result`, `write_report` | 完整文件导出 / 离线 HTML |
| `demo` | `create_demo` | 不联网的合成输入或脱敏静息态样例，见[样例说明](real-example.md) |
| `web.app` | `create_app` | 可选的 FastAPI 本地服务 |
| `cli` | `main` | 命令行入口 |

`_` 开头的帮助函数是内部实现，不承诺兼容性。完整参考额外说明 `_confounds`，以便核对时序处理。直接调用底层影像函数会绕过主流程的部分校验，通常使用 `extract_connectome`。

## 1. 可直接运行的合成体积示例

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from brainfc import Config, extract_connectome
from brainfc.demo import create_demo

with TemporaryDirectory() as tmp:
    spec = create_demo(Path(tmp) / "input")
    settings = Config(**spec.pop("config"))
    result = extract_connectome(**spec, config=settings)
    assert result.connectivity.shape == (12, 12)
    result.provenance["synthetic"] = True
    # 正式保存时使用临时目录之外的新目录：
    # result.save("./demo-result-001")
```

保存及逐项读取结果的完整可执行脚本见 `examples/quickstart.py`。

## 2. 已预处理 NIfTI

以下替换为自己的实际文件；`confounds` 必须与原始帧逐行对应，空间必须已经配准。

```python
from brainfc import Config, extract_connectome, fetch_atlas

atlas = fetch_atlas("schaefer100")
result = extract_connectome(
    "sub-01_task-rest_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz",
    atlas=atlas["atlas"], rois=atlas["rois"],
    confounds="sub-01_task-rest_desc-confounds_timeseries.tsv",
    mask="sub-01_task-rest_space-MNI152NLin6Asym_desc-brain_mask.nii.gz",
    reference="sub-01_task-rest_space-MNI152NLin6Asym_desc-brain_mask.nii.gz",
    config=Config(
        preprocessed=True,
        data_space=atlas["space"], atlas_space=atlas["space"],
        high_pass=0.01, low_pass=0.08, fd_threshold=0.5,
    ),
    progress=print,
)
```

这里的频段和 FD 值只用于展示设置方法，不是官方统一默认。`t_r=None` 会从 JSON/已知单位影像头推断；冲突会报错。`mask` 用于实际 ROI 均值，`reference` 只用于脑壳显示，二者角色独立。

## 3. 已有 ROI 时序

```python
from brainfc import Config, extract_connectome

result = extract_connectome(
    "roi_signals.1D",
    config=Config(table_header=False, detrend=False, standardize=False),
)
```

不提供坐标时只生成矩阵。可用 `rois="rois.tsv"` 加入名称与坐标；有坐标必须声明 `data_space`。无表头和二进制数组的默认 ROI ID 是字符串 `"1"`、`"2"`…；文本表头是 ROI ID，映射表必须完全一致。

多变量 MAT/NPZ 用 `Config(variable="ROISignals")`；ROI × time 文件用 `transpose=True`。本库不接受内存 ndarray 作为 `source`，需保存为 NPY 或表格文件。`extract_connectome` 不识别时序的科学来源；GUI 的 `check_input` 额外拒绝疑似对称连接矩阵。

## 4. CIFTI 与 GIFTI

```python
# dense CIFTI：先确保两个文件的 BrainModelAxis 完全一致。
dense = extract_connectome(
    "run.dtseries.nii", atlas="atlas.dlabel.nii", rois="cifti_rois.tsv",
    config=Config(preprocessed=True, data_space="fsLR", atlas_space="fsLR"),
)

# 已分区 CIFTI：按 ParcelsAxis 名称保留 ROI 顺序。
parcel = extract_connectome(
    "run.ptseries.nii",
    config=Config(preprocessed=True, data_space="fsLR"),
)

# 单半球 GIFTI：同模板、半球、顶点顺序由调用者确认。
surface = extract_connectome(
    "left.func.gii", atlas="left.label.gii", rois="left_rois.tsv",
    config=Config(preprocessed=True, data_space="fsaverage-L",
                  atlas_space="fsaverage-L", t_r=2.0),
)
```

例子中的空间名称是调用约定，不能代替实际配准证据。CIFTI 自动读 SeriesAxis 的秒单位步长；GIFTI 本实现不读取 TR 元数据。表面格式不自动生成质心，3D 需要明确的坐标表；不自动合并左右半球。

## 5. 参数一览

| Config 字段 | 默认 | 单位/意义 |
|---|---|---|
| `t_r` | `None` | 秒；读取实际元数据或手动声明 |
| `high_pass`, `low_pass` | `None` | Hz；不启用滤波 |
| `detrend` | `True` | 去线性趋势 |
| `standardize` | `True` | 样本 z-score |
| `discard` | `0` | 原始开头帧数 |
| `fd_threshold` | `None` | mm；不启用 FD 阈值删帧 |
| `min_samples` | `20` | 最低保留时间点；≥3 |
| `method` | `"pearson"` | `pearson` / `spearman` / `partial` |
| `data_space`, `atlas_space` | `None` | 完整且一致的模板名 |
| `preprocessed` | `False` | 所有影像入口都要求确认 |
| `confound_columns` | `None` | 自动 motion6 + 可用 WM/CSF；或非空列名序列 |
| `table_header` | `True` | 文本首行是列名 |
| `transpose` | `False` | 默认 time × ROI |
| `variable` | `None` | MAT/NPZ 变量名 |

`Config` 禁止字段重新赋值；建议使用 `dataclasses.replace(config, method="partial")` 派生配置。字典用 `Config(**settings)` 转换。全部校验条件见 [函数参考](api-reference.md)；构造 `Config` 不等于完成数据校验。

上游已做完所需去噪且不打算再次处理时，明确使用 `detrend=False, standardize=False, high_pass=None, low_pass=None, discard=0`，不传混杂表。即使不回归头动，软件仍会记录缺少本次混杂回归的提醒；用户需结合上游记录判断。

## 6. 显式混杂模型

```python
config = Config(confound_columns=("trans_x", "trans_y", "trans_z",
                                  "rot_x", "rot_y", "rot_z", "csf"))
```

库不自动构造 Friston-24、aCompCor 或全局信号模型；需要先在混杂表中存在对应列，再显式指定。`confound_columns=()` 不是“只删帧不回归”模式，会报错。非稳态列始终用于删帧；传入混杂表意味着同时提供可用回归设计。列名、FD 缺失和设计秩规则见 [方法说明](processing.md)。

## 7. 保存与显示

```python
result.save("./results/run-001")
result.view("./report-001.html", open_browser=True)
result.plot_matrix("./matrix.png")
result.plot_views("./eight.pdf", threshold=0.4, max_edges=100,
                  selection={"kind": "node", "id": result.rois[0]["roi_id"]})

from brainfc.plotting import edges_of
edges = edges_of(result, threshold=0.4, max_edges=100)
# [(零起始行号, 零起始列号, 有符号权重), ...]
```

`save` 和 `view` 拒绝覆盖。`plot_matrix` / `plot_views` 的图片路径会按 Matplotlib 行为覆盖；`path=None` 返回 Figure，使用完应 `plt.close(fig)`。边 ID 用 `"i:j"`（i<j 的零起始矩阵索引），脑区 ID 用字符串 `roi_id`，两者不要混淆。

## 8. 批处理、预检查和外部处理

`discover_bids(root)` 返回每个 fMRIPrep run 及精确匹配的混杂/掩膜。逐条传给 `extract_connectome`，为每条使用新输出目录；不要直接拼接跨患者或跨扫描时序。可执行示例见 `examples/batch_derivatives.py`。

```python
from brainfc.workflow import preflight
info = preflight({"source": "timeseries.npy", "config": {}}, stage="review")

from brainfc.preprocessing import dicom_plan, convert_dicom, fmriprep_plan
plan = dicom_plan("./dicom", "./converted")
print(plan.to_dict()["powershell"])
# convert_dicom("./dicom", "./converted")  # 实际执行
plan = fmriprep_plan("./bids", "./derivatives", "./license.txt", participant="01")
print(plan.to_dict()["argv"])
# plan.run(log="./fmriprep.log")  # 实际执行，日志必须是新文件
```

`dicom_plan` 只计划；直接 `plan.run()` 不创建转换目录，推荐用 `convert_dicom`。fMRIPrep 输出允许已有目录以便上游工具恢复；本库没有内置完整 BIDS 整理器。

## 9. 异常和兼容性

`InputError` 继承 `ValueError`，代表主动检测到的不兼容输入。文件权限、损坏的 JSON/表格和外部进程异常也可能以原始异常类型传播。推荐只捕获自己能处理的异常，记录文件名和参数；批处理可逐 run 捕获异常并保留成功结果。

0.x 版本继续演进，推荐对可复现实验固定精确版本。`Connectome` 可变，直接实例化不会验证字段一致性；修改矩阵或 ROI 后，应自行维护一致性。可选 `result.to_hicbrain()` 需要另外安装提供 `hicbrain` 模块的 Hyper-Brain。
