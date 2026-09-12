![BrainFC：从 fMRI 与脑区时序到功能连接矩阵、三维脑网络和八个解剖视图](docs/assets/brainfc-hero.png)

<p align="center">
  <a href="https://pypi.org/project/brainfc/"><img src="https://img.shields.io/pypi/v/brainfc?color=168c91" alt="PyPI version"></a>
  <a href="https://github.com/hanxiangmin/brainfc/actions/workflows/ci.yml"><img src="https://github.com/hanxiangmin/brainfc/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3979a5" alt="Python 3.11 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache--2.0-c18a49" alt="Apache-2.0"></a>
</p>

<p align="center"><b>把脑影像变成可计算、可检查、可交互的功能连接。</b><br>一个 Python 库，贯通功能连接、普通图、原生超图与网络统计；提供本地图形界面、命令行与完整 API。</p>

<p align="center"><b>中文</b> · <a href="README.en.md">English</a> · <a href="docs/index.md">使用文档</a> · <a href="docs/api-reference.md">全部 API</a> · <a href="docs/datasets.md">数据下载指南</a></p>

## 安装

需要 **Python 3.11+**。一次安装即包含计算核心、网页界面和离线手册。

**当前源码 0.4.0 已合并 Hyper-Brain。** PyPI 仍是 0.3.0；使用下方源码安装命令可立即体验网络与超图分析，迁移说明见[合并指南](docs/hyper-brain-migration.md)。

```bash
pip install brainfc
brainfc serve
```

浏览器打开 `http://127.0.0.1:8766`，点击 **打开真实样例**，使用包内经脱敏核查的 rest01 静息态数据完成去噪、矩阵计算和可视化。100 个脑区、TR 2 秒，处理后保留 145 帧；无需另找数据或手填参数，日常使用不需要 Node.js。

<details>
<summary>从 GitHub 源码安装 / 命令行演示</summary>

```bash
git clone https://github.com/hanxiangmin/brainfc.git
cd brainfc
pip install .
brainfc demo --kind rest01 --output demo-001
```

源码安装适用于开发版，以及尚未上传到 PyPI 的版本。离线手册位于本地服务的 `/reference/`，HTTP 接口说明位于 `/docs`。更多环境与批处理说明见 [快速上手](docs/quickstart.md)。

</details>

当前源码版新增[真实静息态样例 rest01](docs/real-example.md)：`brainfc demo --kind rest01 --output rest01-demo`。已去除身份信息和面部，附有处理方法、参数修正及质控记录。

## 使用

### 在界面中处理

**选择数据 → 确认方案 → 开始处理。**

界面识别文件类型，读取可用的 TR、空间和配套文件；只有无法确定的信息才需要补充。高级设置默认收起，后续步骤依次解锁。可选 ABIDE、ADNI、ADHD-200、MDD、PPMI 的资料预设，扫描元数据优先，参数仍需确认。

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

影像须已配准到声明的空间；图谱重采样不会代替配准。默认去趋势、标准化，不启用频带滤波或 FD 阈值删帧；需要时按上游处理记录设置。详细 [处理方法](docs/processing.md) 和 [参数默认值](docs/python-api.md#5-参数一览) 可逐项查阅。

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

`save()` 导出矩阵、时序、脑区与帧号、质量记录、处理来源、图片和离线交互报告；目标目录须为新目录。三维和八视图需要完整 ROI 坐标；自定义坐标须声明空间。

[可直接运行的完整示例](examples/quickstart.py) · [批处理示例](examples/batch_derivatives.py) · [Python 使用指南](docs/python-api.md) · [CLI](docs/cli-reference.md) · [HTTP API](docs/http-api.md)

### 4. 继续构建图与原生超图

Hyper-Brain 已集成到 `brainfc.network`，无需安装第二个库。接上文的 `result`：

```python
from brainfc.network import AnalysisConfig
from brainfc.network.export import export_result

network = result.analyze_network(AnalysisConfig(
    graph_method="density", density=0.1,
    hypergraph_method="multiscale", hypergraph_ks=[5, 10],
))
export_result(network, "network-result.zip")
```

界面中点击 **进入网络分析**，即可沿用矩阵、脑区坐标与处理记录；已有矩阵也可直接进入页面顶部的 **网络与超图分析**。支持节点连线、透明包络、分区表面、完整超边成员表与组间统计。仅有参考脑壳时不提供分区表面或图谱切片。

[网络分析完整指南](docs/network-analysis.md) · [可运行示例](examples/network_analysis.py) · [旧接口迁移](docs/hyper-brain-migration.md)

## 关键功能

| 功能 | 可以做什么 |
| :--- | :--- |
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

以上界面与矩阵来自[**经脱敏核查的真实静息态样例 rest01**](docs/real-example.md)：1 名被试、Schaefer 100 脑区、145 个保留时间点。矩阵保留原始 ROI 顺序和完整 Pearson 相关，色标固定为 −1～1；L/R 表示左右半球，分隔线标出网络边界，没有聚类重排或平滑。三维与八视图使用同一组筛选连接，不改变完整数值矩阵。顶部仍为产品概念插画。

早期 README 使用合成信号，重复的信号分组在交错的 ROI 顺序下形成周期性斜纹；现已替换为真实计算结果。可用 `python scripts/render_example_matrix.py --output matrix-demo` 复现矩阵图；[核查范围](docs/privacy-review.md)与[图像来源记录](docs/assets/matrix-provenance.json)可供检查。本例是单被试软件演示，未进行切片时序和磁敏感畸变校正。

## 影像到功能连接的处理流程

![BrainFC 完整处理流程：格式与空间检查、时序提取、联合清理、连接计算、导出与同步视图；使用 archify skill 绘制](docs/assets/processing.png)

[查看清晰矢量图](docs/assets/processing.svg) · [下载交互流程图 HTML](docs/assets/processing.html) · [可编辑流程定义](docs/assets/processing.dataflow.json) · [逐步方法说明](docs/processing.md)

ROI 时序文件可从“统一 ROI 时序”进入；原始影像先走外部 **dcm2niix → BIDS → fMRIPrep**，检查报告后重新导入。BrainFC 的 pip 包不包含这些外部工具，也不自行完成空间预处理；完整外部原始数据链的验证状态见 [验证记录](docs/validation-v0.3.0.md)。

| 想进一步了解 | 文档入口 |
| :--- | :--- |
| 每个函数的签名、参数、返回值和异常 | [完整 API 参考](docs/api-reference.md) |
| 该提供哪些输入，如何准备坐标与图谱 | [输入格式](docs/formats.md) · [数据集指南](docs/datasets.md) |
| 数据集预设如何预填，哪些值需要确认 | [预设与引导流程](docs/presets-and-workflow.md) |
| 每个输出文件的含义 | [输出格式](docs/outputs.md) |
| 开发、测试与发布 | [贡献指南](CONTRIBUTING.md) · [验证记录](docs/validation-v0.3.0.md) |

## 许可与致谢

Copyright © 2026 BrainFC contributors. 代码采用 [Apache License 2.0](LICENSE)，引用信息见 [CITATION.cff](CITATION.cff)。

计算核心基于 NumPy、SciPy、NiBabel、Nilearn 和 scikit-learn；可视化使用 Matplotlib、React 和 Three.js。网络与超图分析由 [Hyper-Brain](https://github.com/hanxiangmin/Hyper-Brain) 合入，源码及第三方许可保留；详见[来源和迁移说明](docs/hyper-brain-migration.md)。流程图使用 [archify skill](https://github.com/tt-a1i/archify) 绘制；第三方许可见 [NOTICE](NOTICE) 和 [完整声明](src/brainfc/web/static/THIRD_PARTY_NOTICES.txt)。图谱与数据集遵循各自提供方的许可，本仓库仅提供经授权并核查的 rest01 衍生样例，不分发原始 DICOM 或个体 T1/BOLD 强度图像。
