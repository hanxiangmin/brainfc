![BrainFC：从 fMRI 与脑区时序到功能连接矩阵、三维脑网络和八个解剖视图](docs/assets/brainfc-hero.png)

<p align="center">
  <a href="https://pypi.org/project/brainfc/"><img src="https://img.shields.io/pypi/v/brainfc?color=168c91" alt="PyPI version"></a>
  <a href="https://github.com/hanxiangmin/brainfc/actions/workflows/ci.yml"><img src="https://github.com/hanxiangmin/brainfc/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%E2%80%933.13-3979a5" alt="Python 3.11–3.13">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache--2.0-c18a49" alt="Apache-2.0"></a>
</p>

<p align="center"><b>静息态 fMRI 功能连接矩阵、脑网络与超图分析。</b><br>Resting-state fMRI · Functional connectivity · Connectome · Hypergraph · Python API + GUI</p>

<p align="center"><b>中文</b> · <a href="README.en.md">English</a> · <a href="docs/index.md">使用文档</a> · <a href="docs/api-reference.md">全部 API</a> · <a href="docs/datasets.md">数据下载指南</a></p>

## 安装

需要 **Python 3.11–3.13**。

```bash
pip install -U brainfc
brainfc serve
```

启动后点击 **打开真实样例** 即可体验，无需准备数据或填写参数。

## 使用

### 在界面中处理

**选择数据 → 确认方案 → 开始处理。**

上传自己的数据，界面会自动读取文件信息，提示需要确认的参数。

### 原始 fMRI：从 BOLD + T1 开始

准备同一次研究中匹配的静息态 **4D BOLD、3D T1 和 BOLD 采集 JSON**。TR、切片时间与方向优先从文件读取；缺失或冲突时提示确认。

```python
from brainfc import preprocess_fmri

run = preprocess_fmri("bold.nii.gz", "t1w.nii.gz", "results/preprocessed")
```

先打开 `results/preprocessed/qc.html` 检查脑提取、配准、组织分割和头动，再继续：

```python
from brainfc import load_preprocessed

run = load_preprocessed("results/preprocessed")
result = run.extract(qc_reviewed=True)
result.save("results/connectome")
```

### 从原始影像到脑网络，具体做了什么？

| 顺序 | 实际处理 | 调用入口与默认设置 |
| :--- | :--- | :--- |
| 1. 输入检查 | DICOM 转换（如需）；检查维度、TR、切片时间、空间几何 | `scan_dicom()` / `convert_dicom_python()` / `inspect_raw()`；不猜切片顺序 |
| 2. 时间与头动 | FFT 层间时间校正、逐帧刚体头动估计 | `preprocess_fmri()`；参考时间 `0.5 × TR`，ANTs `BOLDRigid` |
| 3. T1 与标准化 | N4、脑提取、Atropos 组织分割；BOLD→T1 刚体配准，T1→MNI SyN | 同一函数自动完成；MNI152NLin6Asym、2 mm，合成变换后逐帧一次最终空间插值 |
| 4. 混杂与质控 | 提取运动矩阵、WM/CSF、FD/DVARS；可选平滑；生成配准报告 | 默认不平滑、不删除开头帧；检查 `qc.html` 后才进入提取 |
| 5. ROI 与功能连接 | ROI 均值 → 初始帧剔除 → 联合去趋势、滤波、混杂回归与删帧 → 相关 | `run.extract()`；Schaefer100、0.01–0.1 Hz、运动矩阵 + WM/CSF、Pearson；FD 删帧默认关闭 |
| 6. 脑网络与导出 | 保存完整正负矩阵与 Fisher-z；可进一步构图或构建超图 | `result.save()` / `result.analyze_network()`；网络构建参数与显示筛选分别设置 |

**[完整方法与参数说明](docs/python-preprocessing.md)**：逐步算法、函数对应、全部预处理参数、可复现示例、质控判据和处理记录。**显式传入 `Config()` 时滤波默认关闭**，不会继承 `run.extract()` 的带通默认值；网页滤波也以确认页为准。

支持已有 conda 环境，无需 MATLAB 或 Docker。当前未实现场图/反向相位编码畸变校正；默认设置属于 BrainFC 方案，不是各数据集的统一标准，也不声称与 SPM/DPABI 数值等价。

### 1. 已有脑区时间序列

适用于上游已完成所需去噪的 ROI 信号。TSV 首行为脑区名，每行一个时间点，只保留信号列。

```python
from brainfc import Config, extract_connectome

result = extract_connectome(
    "roi_timeseries.tsv",
    config=Config(detrend=False, standardize=False),
)

fc = result.connectivity       # ROI × ROI，完整的有符号相关矩阵
z = result.fisher_z            # 单独保存的 Fisher-z 矩阵
result.save("results/roi-001")
```

无表头文本用 `Config(table_header=False)`；NPY/NPZ/MAT 等入口见 [格式说明](docs/formats.md)。没有脑区坐标时仍可计算和绘制矩阵。

### 2. 已预处理的 fMRI 影像

以 MNI152NLin6Asym 空间的 BOLD 和 Schaefer 100 图谱为例。替换为自己的扫描文件与逐帧混杂表。

```python
from brainfc import Config, extract_connectome, fetch_atlas

atlas = fetch_atlas("schaefer100")  # 首次下载，之后复用缓存
result = extract_connectome(
    "sub-01_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz",
    atlas=atlas["atlas"],
    rois=atlas["rois"],
    confounds="sub-01_desc-confounds_timeseries.tsv",
    config=Config(
        preprocessed=True,
        data_space="MNI152NLin6Asym",
        atlas_space=atlas["space"],
    ),
)
```

影像须已配准；去噪参数按上游处理记录设置。详见[处理方法](docs/processing.md)与[参数默认值](docs/python-api.md#5-参数一览)。

### 3. 可视化与导出

接上例，`result` 已包含脑区坐标：

```python
result.plot_matrix("matrix.svg")
result.plot_views("eight_views.pdf", threshold=0.4, max_edges=150)
result.view("brain-network.html", open_browser=True)
result.save("results/sub-01")

cleaned_signals = result.timeseries
original_frames = result.sample_indices
quality = result.qc
```

`save()` 保存完整结果和离线报告，目标目录须不存在。三维和八视图需要脑区坐标与空间信息。

[可直接运行的完整示例](examples/quickstart.py) · [批处理示例](examples/batch_derivatives.py) · [Python 使用指南](docs/python-api.md) · [CLI](docs/cli-reference.md) · [HTTP API](docs/http-api.md)

### 4. 继续构建图与原生超图

接上文的 `result`：

```python
from brainfc.network import AnalysisConfig
from brainfc.network.export import export_result

network = result.analyze_network(AnalysisConfig(
    graph_method="density", density=0.1,
    hypergraph_method="multiscale", hypergraph_ks=[5, 10],
))
export_result(network, "network-result.zip")
```

界面中点击 **进入网络分析**，矩阵、坐标和处理记录自动带入。

[网络分析指南](docs/network-analysis.md) · [可运行示例](examples/network_analysis.py)

## 关键功能

| 功能 | 可以做什么 |
| :--- | :--- |
| **Python 原始预处理** | DICOM 转换、层间时间、头动、N4、组织分割、SyN 配准、混杂与质控。 |
| **多格式输入** | 体积影像、CIFTI、配对 GIFTI、ROI 表格与数组；发现 fMRIPrep 单次扫描及配套文件。 |
| **统一计算** | 脑区均值提取；Nilearn 联合处理混杂、去趋势、滤波和删帧；Pearson、Spearman、Ledoit–Wolf 偏相关。 |
| **引导操作** | 按数据类别选择处理路径，自动读取可确认的元数据；数据集预设附官方来源。 |
| **同步探索** | 矩阵定位脑区；三维与八视图共享阈值、连接上限及脑区/连接选择；前方脑区悬停名称。 |
| **可追溯导出** | 原始帧号、ROI 顺序、参数、质量记录、软件版本与输入 SHA-256；保留完整正负连接。 |
| **图与原生超图** | 有符号图、密度/阈值/kNN/生成森林；FC-profile、多尺度、模板与自定义超边，保留原始 ID 和完整成员。 |
| **网络指标与统计** | 正连接路径指标、原生关联矩阵、独立被试两组比较、协变量 OLS/HC3 和 BH-FDR。 |
| **本地运行** | Python、CLI、网页共用核心；数据在本机处理，报告可离线打开。 |

### 实际界面

![BrainFC 实际三维界面：可旋转的脑网络、连接筛选和解剖参考表面](docs/assets/viewer.png)

<table>
<tr><th width="50%">完整功能连接矩阵</th><th width="50%">与三维同步的八个视图</th></tr>
<tr><td><a href="docs/assets/matrix.png"><img src="docs/assets/matrix.png" alt="Schaefer 100 脑区完整相关矩阵"></a></td><td><a href="docs/assets/eight-views.png"><img src="docs/assets/eight-views.png" alt="同一组连接在八个解剖视角下的实际渲染"></a></td></tr>
</table>

以上结果来自[脱敏真实样例 rest01](docs/real-example.md)：100 个脑区、145 个时间点。矩阵保留完整 Pearson 相关；三维与八视图共享筛选连接。顶部为产品概念插画。[处理与质控](docs/real-example.md) · [隐私核查](docs/privacy-review.md)

## 影像到功能连接的处理流程

![BrainFC 完整处理流程：格式与空间检查、时序提取、联合清理、连接计算、导出与同步视图；使用 archify skill 绘制](docs/assets/processing.png)

[查看清晰矢量图](docs/assets/processing.svg) · [下载交互流程图 HTML](docs/assets/processing.html) · [可编辑流程定义](docs/assets/processing.dataflow.json) · [逐步方法说明](docs/processing.md)

原始 BOLD + T1、DICOM、已处理影像或 ROI 时序均可进入对应流程。[Python 原始 fMRI 全流程](docs/python-preprocessing.md)包含预处理、质控和功能连接提取。

| 想进一步了解 | 文档入口 |
| :--- | :--- |
| 每个函数的签名、参数、返回值和异常 | [完整 API 参考](docs/api-reference.md) |
| 该提供哪些输入，如何准备坐标与图谱 | [输入格式](docs/formats.md) · [数据集指南](docs/datasets.md) |
| 数据集预设如何预填，哪些值需要确认 | [预设与引导流程](docs/presets-and-workflow.md) |
| 每个输出文件的含义 | [输出格式](docs/outputs.md) |
| 开发、测试与发布 | [贡献指南](CONTRIBUTING.md) · [原始 fMRI 验证记录](docs/validation-v0.5.0.md) |

## 许可与致谢

Copyright © 2026 BrainFC contributors. 代码采用 [Apache License 2.0](LICENSE)，引用信息见 [CITATION.cff](CITATION.cff)。

计算核心基于 NumPy、SciPy、NiBabel、Nilearn 和 scikit-learn；可视化使用 Matplotlib、React 和 Three.js。网络与超图分析由 [Hyper-Brain](https://github.com/hanxiangmin/Hyper-Brain) 合入，源码及第三方许可保留；详见[来源和迁移说明](docs/hyper-brain-migration.md)。流程图使用 [archify skill](https://github.com/tt-a1i/archify) 绘制；第三方许可见 [NOTICE](NOTICE) 和 [完整声明](src/brainfc/web/static/THIRD_PARTY_NOTICES.txt)。图谱与数据集遵循各自提供方的许可，本仓库仅提供经授权并核查的 rest01 衍生样例，不分发原始 DICOM 或个体 T1/BOLD 强度图像。
