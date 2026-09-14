# 原始 fMRI → 脑网络：完整流程与参数

本页对应 BrainFC 0.5.1 的实际实现，说明每一步的输入、算法、调用函数和参数。先阅读总览与示例；复现实验时按参数表和输出记录核对。完整签名与返回值见 [API 参考](api-reference.md)，时序清理细节见 [处理方法](processing.md)。

## 1. 选择正确的起点

| 现有数据 | 从哪里开始 | 必须确认 |
|---|---|---|
| 原始 DICOM | `scan_dicom()` → `convert_dicom_python()` → `preprocess_fmri()` | 主 BOLD 与同一人的 T1 序列；不是定位像、场图或反向短序列 |
| 原始 NIfTI / BIDS | `inspect_raw()` → `preprocess_fmri()` | 4D 静息态 BOLD、匹配 3D T1、采集 JSON；BIDS 可用 `discover_raw()` 找候选 |
| 已完成空间预处理的影像 | `extract_connectome()` | 实际空间与图谱一致；混杂表和去噪历史。`preprocessed=True` 是调用者声明，不会触发空间预处理 |
| 已分区 ROI 时序 | `extract_connectome()` | 行是时间、列是 ROI；是否已经滤波/回归，避免重复清理 |
| 已有功能连接矩阵 | `brainfc.network.load_data(..., kind="connectivity", matrix_kind="correlation")` → `analyze()` | 矩阵含义、ROI 顺序；不要把方阵当时序再次求相关 |

```text
DICOM ──转换──> BOLD + T1 + 采集 JSON
                       │
             检查 TR、切片时间和几何
                       │
       层间时间校正 → 逐帧头动估计
                       │
       T1 N4 → 脑提取 → 组织分割 → T1 到 MNI
                       │
       BOLD 到 T1 → 合成逐帧变换 → 2 mm 标准空间
                       │
       组织混杂、FD/DVARS → 可选平滑 → 人工质控
                       │
已预处理影像 ──> ROI 均值
                       ├── 已分区时序从此处进入
       初始帧剔除 → 联合去趋势/滤波/回归/删帧
                       │
              完整有符号 FC + Fisher-z
                       │
       保存与可视化 / 普通图 / 可选原生超图
```

空间输出 BOLD 尚未进行 ROI 时序去噪；`result.timeseries` 才是清理后的 ROI 信号。空间阶段保留全部帧，`discard` 在连接提取阶段实际移除。普通图与超图均可直接从完整 FC 构建，超图不依赖普通图先筛选出来的边。

## 2. 安装与界面

在已有 **Python 3.11–3.13 的 conda 环境**中安装即可，无需重装 Python：

```shell
python -m pip install -U brainfc
brainfc serve
```

界面选择“原始 NIfTI / BIDS”或“原始 DICOM”，依次完成 **选影像 → 确认方案 → 预处理 → 检查质控 → 功能连接**。原始 NIfTI 只需 BOLD 和同一人的 T1；同名采集 JSON 自动读取。DICOM 文件夹先识别序列，确认 BOLD 与 T1。输出目录自动安排。

所有计算通过 Python 包完成。ANTsPy 的编译内核随 wheel 安装，不需要 MATLAB、SPM、Docker、FreeSurfer 许可证或独立命令行工具。首次使用会下载约 1.5 MB 的 TemplateFlow 模板；Schaefer 图谱另行缓存。

## 3. 可复现的 Python 示例

以下分两次执行，保留人工质控环节。示例选择丢弃开头 5 帧，**不是所有扫描的默认要求**；实际默认值为 0。TR 和切片时间不手填，优先读取扫描元数据。

```python
from brainfc import PreprocessConfig, inspect_raw, preprocess_fmri

settings = PreprocessConfig(discard=5, smoothing_fwhm=0, seed=42)
plan = inspect_raw("bold.nii.gz", "t1w.nii.gz", config=settings)
if not plan["ready"]:
    raise ValueError(plan["missing"])  # 按采集记录补充元数据或明确选择跳过

run = preprocess_fmri(
    "bold.nii.gz",
    "t1w.nii.gz",
    "results/preprocessed-01",  # 必须是新目录
    config=settings,
    progress=print,
)
print(run.directory / "qc.html")
```

**先打开上面的 `qc.html`，按第 8 节检查。** 通过后再执行下面代码；重新打开 Python 也可继续，不必重复空间预处理。

```python
from brainfc import Config, load_preprocessed
from brainfc.network import AnalysisConfig
from brainfc.network.export import export_result

run = load_preprocessed("results/preprocessed-01")  # 验证输出完整性和 SHA-256
result = run.extract(
    "schaefer100",
    config=Config(
        high_pass=0.01, low_pass=0.1,  # Hz；显式写明，便于复现
        detrend=True, standardize=True,
        discard=run.provenance["config"]["discard"],
        fd_threshold=None, min_samples=20, method="pearson",
    ),
    qc_reviewed=True,
)
result.save("results/connectome-01")  # 新目录；完整矩阵、时序、质控与图像

network = result.analyze_network(AnalysisConfig(
    graph_method="density", density=0.1,
    compute_hypergraph=False,  # 此例只构建普通图；超图用法见第 7 节
))
export_result(network, "results/network-01.zip")

print(result.connectivity.shape, result.timeseries.shape)
print(result.provenance["config"])  # 实际绑定后的 TR、空间、回归列等
print(result.sample_indices)        # 原始帧号，从 0 开始
```

这里 `run.extract()` 自动传入标准空间脑掩膜、图谱标签及 14 列运动矩阵/WM/CSF 混杂，无需重新填写路径或空间。图谱与模板首次下载后缓存。上述代码没有启用 GSR 或 FD 阈值删帧。

## 4. 采集信息与空间参数

要求单回波、恒定 TR 的 4D 静息态 BOLD 和匹配的 3D T1，具有有效 qform/sform、毫米单位、正交体素轴。未实现多回波合并、变 TR / 稀疏采样、畸变校正和表面重建。原始 DWI 不属于此入口。成人 MNI 模板是否适用于儿童、明显病变等数据，需要独立确认。

TR 按实际采集 JSON / 影像头读取；数值冲突时停止。切片时间采用 BIDS 的**秒**，支持多带相同时间；负的 `SliceEncodingDirection` 会反转时间列表。切片维度由 JSON 或 NIfTI `dim_info` 读取。只有可靠元数据缺失时才需要补充；不按奇偶层数猜采集顺序。BIDS 继承元数据需先整理为该次扫描的独立 sidecar。

### `PreprocessConfig` 全部参数

| 参数 | 默认值 / 单位 | 如何设置与实际作用 |
|---|---|---|
| `t_r` | `None` / 秒 | 自动读取 JSON/影像头；仅在有可靠采集记录时补充。显式值与已有元数据冲突会停止，不强行覆盖 |
| `slice_timing` | `"auto"` | `auto` / `require` 均要求可用的切片时间与维度；`skip` 明确跳过并记录。没有猜测“奇数先”或“偶数先” |
| `slice_axis` | `None` | 原始 NIfTI 的空间维度 `0/1/2`；优先读取 `SliceEncodingDirection` 或 `dim_info`，不是显示器上的上下方向 |
| `reference` | `0.5` / TR 比例 | 所有切片移到一个 TR 内的这一时间点，范围 `[0,1)`；例如 TR=2 s 时对应 1 s |
| `discard` | `0` / 帧 | 根据采集协议和稳态情况决定；开头这些帧不参与头动参考均值，仍做空间处理，提取时再删除；不是自动稳态检测 |
| `smoothing_fwhm` | `0.0` / mm | 0 关闭；非负空间高斯 FWHM。是否平滑及宽度由图谱尺度和研究方案决定；会影响 ROI 信号，不应用于 WM/CSF 混杂提取 |
| `seed` | `42` / 整数 | 非负 ANTs 随机种子；记录软件与线程环境，不能据此保证跨平台逐位一致 |

`preprocess_fmri()` 的 `sidecar` 可指定采集 JSON，默认找与 BOLD 同名的 JSON；`t1_mask` 可传独立脑掩膜，必须与输入 T1 原始网格匹配；`template_dir` 只改变缓存位置，**不更换模板种类或分辨率**。`progress` 接收进度字符串。输出目录必须不存在，失败目录保留用于排查。

疾病/队列名称不能决定 TR、切片顺序或去噪策略。ABIDE、ADNI、ADHD-200、MDD、PPMI 的预设只提供有来源的采集参考，扫描元数据优先，详见 [预设依据](presets-and-workflow.md)。

## 5. 空间预处理：实际函数与固定设置

用户只需调用 `preprocess_fmri()`。下表列出它内部调用的函数；其中 N4、SyN、Atropos 等低层设置目前固定在实现中，**不是可直接传给 `PreprocessConfig` 的参数**。算法细节以固定依赖 ANTsPy 0.6.3 和 [流水线源码](https://github.com/hanxiangmin/brainfc/blob/main/src/brainfc/raw/pipeline.py) 为准。

| 步骤 | 实际调用 | 设置、输入与输出 |
|---|---|---|
| DICOM 转换（如需） | `convert_dicom_python()`；`pydicom` + `dicom2nifti` | 联影 UIH 拼图按每层位置与时间解码；标准 TE/TR 毫秒转秒；序列与回波分开，输出 NIfTI + 最小采集 JSON |
| 层间时间校正 | `brainfc.raw.temporal.slice_time_correct()`；SciPy FFT | 两端各反射填充 T 帧，逐切片移到 `reference × TR`，保留全部帧索引。明确跳过时省略此步 |
| 头动估计 | `ants.motion_correction()` | `type_of_transform="BOLDRigid"`、`fdOffset=50`；初始参考为去除指定开头帧后的均值，再用校正后的对应帧均值作 BOLD 参考；保存每帧刚体矩阵 |
| T1 偏置与脑提取 | `ants.resample_image()`、`ants.n4_bias_field_correction()`、`ants.registration()` / `apply_transforms()` | T1 工作网格 1.5 mm；N4 `shrink_factor=2`、迭代 `[30,20,10]`、容差 `1e-6`。没有独立掩膜时，整头 SyN 后逆传播模板掩膜，保留最大连通部分并填孔；脑内再 N4 |
| 组织分割 | `ants.atropos()` | `i="KMeans[3]"`、`m="[0.2,1x1x1]"`、`c="[5,0]"`；按 T1 类别平均强度由低到高指定 CSF / GM / WM，不是 SPM 的组织先验模型 |
| T1 标准化 | `ants.registration()` | 去颅骨 T1→MNI152NLin6Asym；`type_of_transform="SyN"`、`reg_iterations=(60,40,20)`，模板脑掩膜约束；整头预配准也用相同 SyN 迭代 |
| BOLD 与 T1 对齐 | `nilearn.masking.compute_epi_mask()`、`ants.registration()` | BOLD 参考信号掩膜 `opening=1`；masked BOLD→脑 T1，`type_of_transform="Rigid"`、`aff_iterations=(1000,500,250,100)`；互信息度量继承固定 ANTsPy 版本默认 |
| 脑覆盖与重采样 | `ants.apply_transforms()` | 标准化 EPI 掩膜与模板脑掩膜取交集，覆盖率 <50% 停止；合成 T1 标准化、BOLD→T1 和逐帧头动变换，从层间时间校正后的输入**只做一次最终空间插值**，2 mm、线性插值 |
| 混杂提取 | SciPy `binary_erosion()`、`ants.apply_transforms()`、NumPy 均值 | WM/CSF 概率 >0.9；在 T1 工作网格腐蚀 1 体素，最近邻变换并与覆盖掩膜相交，各至少 20 体素；从未平滑标准空间 BOLD 提取均值 |
| FD / DVARS | 头动结果中的 `FD`；NumPy 时间差分 | ANTs generalized FD；DVARS 是相邻帧脑内体素强度差的均方根，未标准化、单位随原始强度；两者首帧写为 `n/a` |
| 可选平滑 | `scipy.ndimage.gaussian_filter()` | 逐帧三维高斯，FWHM 换算为各轴体素 sigma；默认关闭；此后写入空间预处理 BOLD |
| 报告 | `brainfc.raw.quality.write_qc()` | 对齐、组织与头动图，以及 `qc.html`；不会自动把运行成功判成影像质量合格 |

ANTs 使用 LPS 物理坐标，NiBabel 使用 RAS；影像适配器通过 NIfTI 保存几何，已设旋转坐标往返测试。图像变换和点变换有不同方向约定，不能把变换列表反向后直接当成逆变换。

该实现参考教程的步骤组织，**不声称与 SPM、DPABI 或 fMRIPrep 数值等价**。切片插值边界、配准优化、组织分割和运动混杂模型均有明确差异。

配准种子通过 ANTsPy 0.6.3 的配置接口传入底层 ANTs；仅向 `registration()` 传旧版 `random_seed` 关键字在该版本不会生效。结果记录种子、库版本和 ITK 线程环境，跨平台或多线程计算不保证逐位一致。实际验证范围见 [0.5.0 验证记录](validation-v0.5.0.md)。

## 6. ROI、去噪与功能连接

### 三个入口的默认行为

| 设置 | `run.extract(config=None)` | `extract_connectome(..., config=None)` / 显式 `Config()` | 网页新建提取方案 |
|---|---|---|---|
| 高通 / 低通 | 0.01 / 0.1 Hz | `None` / `None`，不滤波 | 初始留空，不滤波；以确认页实际值为准 |
| 去趋势 / 标准化 | 开 / 样本 z-score | 开 / 样本 z-score | 初始均开；选择“上游已去噪”会关闭重复清理 |
| 初始帧 | 继承空间预处理的 `discard` | 0 | 原始流程继承 `discard` |
| 回归列 | 默认 14 列（12 列运动矩阵/偏移 + WM/CSF） | 没有 confounds 则不回归；有表时识别完整 motion6 + 可用 WM/CSF，其他模型需指定列 | 原始流程自动带入 14 列；外部影像按提供的表及确认策略 |
| FD 删帧 | 关闭 | 关闭 | 初始关闭 |
| 相关方法 / 最少帧数 | Pearson / 20 | Pearson / 20 | Pearson / 20 |

**显式 `Config` 是完整配置，不是对便捷默认值的局部补丁。** 例如 `run.extract(config=Config(discard=5), ...)` 会关闭带通；若要保留，应同时写 `high_pass=0.01, low_pass=0.1`。网页和 Python 共用计算核心，但初始化默认值不同；比较结果必须比较最终配置。

### ROI 提取

`run.extract(atlas="schaefer100")` 调用 `fetch_atlas()`，再调用 `extract_connectome()`；默认 Schaefer 100，可选同一 MNI152NLin6Asym 空间的 `schaefer200` / `schaefer400`。不同 MNI 变体不能仅凭名称中有“MNI”就混用。

体积数据由 `brainfc.imaging.volume_timeseries()` 将离散标签以最近邻重采样到 BOLD 网格，然后对脑掩膜内每个 ROI 计算体素算术均值。0 是背景；ROI 按原始正标签数值升序排列。任何 ROI 在掩膜内为空都会报错。这里调整网格，不重新估计配准；标签、ID、名称及 RAS+ mm 坐标一起保存。提取后的 ROI 信号才进入时序清理。

### `Config` 的时序参数

| 参数 | 类默认值 | 含义与设置依据 |
|---|---|---|
| `t_r` | `None` | 秒；`run.extract()` 绑定真实输出 TR，冲突报错 |
| `high_pass` / `low_pass` | `None` / `None` | Hz；分别开启高通/低通，两者均有值时为带通。须 `0 < high_pass < low_pass < 1/(2×TR)`；单一截止频率也须小于 Nyquist。0.01–0.1 是便捷入口默认，不是官方通用最佳值 |
| `detrend` | `True` | 去线性趋势；已在上游完成时避免无依据地重复 |
| `standardize` | `True` | Nilearn `zscore_sample`；关闭则不做该标准化 |
| `discard` | `0` | 删除输入最前面的帧，必须与本次空间预处理记录一致 |
| `confound_columns` | `None` | 非空列名序列显式指定回归变量；列必须存在且通过有限值校验。`run.extract()` 留空时自动绑定运动矩阵 + WM/CSF；空列表不能用来关闭该默认回归 |
| `fd_threshold` | `None` | mm；正数才开启逐帧剔除。`FD > 阈值` 删除，等于阈值保留；不连带删除邻帧。必须按实际 FD 定义制定阈值 |
| `min_samples` | `20` | 删帧后最少保留点数，≥3 的整数；20 是运行检查下限，不代表足够的可靠性或统计效能 |
| `method` | `"pearson"` | `pearson` / `spearman` / `partial`，见下文 |

其余 `Config` 字段用于输入解释：`data_space=None`、`atlas_space=None`、`preprocessed=False`（便捷原始入口自动绑定）；`table_header=True`、`transpose=False`、`variable=None`（表格/数组/MAT 入口），详见 [格式说明](formats.md)。

`run.extract()` 默认使用 0.01–0.1 Hz、去趋势和样本 z-score，回归 9 个旋转矩阵元素、3 个 LPS 仿射偏移及 WM/CSF 均值。这是 BrainFC 的可修改建议；不是数据集官方统一参数，也不是 SPM motion6 / Friston-24。矩阵列可能线性相关，提取会检查实际设计秩和残余自由度。

`discard` 应与预处理配置一致。TR 和空间由真实输出绑定。FD 默认不用于删帧；显式 `fd_threshold` 才启用。这里的 FD 是 **ANTs generalized FD，`fdOffset=50 mm`**，不是 Power FD；不能直接套用另一种 FD 的阈值。首行 FD/DVARS 未定义，写为 `n/a`。DVARS 为原始强度单位。全局信号提供为检查列，默认不回归。

14 列的确切名称为 `motion_matrix_00` … `motion_matrix_22`（3×3 旋转矩阵逐行排列）、`motion_offset_x/y/z`（LPS 下的 `t+c−Rc`）、`white_matter`、`csf`。这 14 列不等于 14 个独立运动自由度；不自动追加导数、平方项、aCompCor 或 ICA-AROMA。

### 联合清理顺序和删帧

`extract_connectome()` 先建立原始帧保留掩码，再去除开头 `discard` 帧，最后将信号、混杂及剩余帧索引一起传给 `nilearn.signal.clean()`。设置 `standardize_confounds=True`；有截止频率则 `filter="butterworth"`，否则关闭滤波；显式 `extrapolate=True`。

有带通和删帧时，Nilearn 先插值被剔除位置用于规则时间网格的去趋势和滤波，再移除指定样本、回归混杂并标准化；信号和混杂接受配套滤波。没有开启滤波时不做该滤波插值。BrainFC 不将删帧后的不规则样本重新当成连续等间隔扫描。具体顺序及默认滤波实现见 [Nilearn `signal.clean`](https://nilearn.github.io/stable/modules/generated/nilearn.signal.clean.html)。

当前依赖 `nilearn>=0.14,<0.15`；未覆盖其 Butterworth 默认阶数 5、`padtype="odd"`、`padlen=None`，使用前后向滤波。BrainFC 暂未将阶数/边界填充设为 `Config` 参数。短序列无法满足滤波要求时会报错，应检查扫描长度和方案，不能直接省略失败步骤后声称完成相同处理。

`non_steady_state_outlier*` 非零的帧也会被剔除；原始 Python 路线目前不自动生成这些列。启用 FD 时首帧缺失 FD 被删除；后续缺失 FD 报错。保留帧数、回归设计秩、常数 ROI 和非有限值均检查；没有把不可计算的连接填成 0。全部规则见 [删帧与回归定义](processing.md)。

### 矩阵怎么算

| `method` | 实现 | 输出解释 |
|---|---|---|
| `pearson` | `numpy.corrcoef(cleaned, rowvar=False)` | 清理后 ROI 时序两两线性相关 |
| `spearman` | `scipy.stats.rankdata(..., axis=0)` 后 Pearson | 平均并列秩的秩相关 |
| `partial` | `sklearn.covariance.LedoitWolf` 的精度矩阵 P，`−Pij / sqrt(Pii×Pjj)` | 收缩估计的偏相关，收缩系数记录在 QC |

结果对称化、截到 `[−1,1]`，对角线设为 1。`result.fisher_z` 单独保存 `atanh(clip(r, −1+1e−7, 1−1e−7))`，对角线 0。此数值转换不生成 p 值；完整 FC 保留所有正负相关，不按可视化阈值稀疏化。

## 7. 从 FC 构建脑网络

`result.analyze_network(AnalysisConfig(...))` 经 `brainfc.network.bridge.from_connectome()` 和 `brainfc.network.analyze()` 转交已有完整 FC、ROI、空间和处理来源；不会再次做时序去噪或重新从时序计算 FC。图与超图分别由 `brainfc.network.graph.build_graph()`、`brainfc.network.hypergraph.build_hypergraph()` 构建，再计算描述性指标。可用函数的准确模块名见 [API 参考](api-reference.md)。

### 普通图

| `AnalysisConfig` 设置 | 实际选边方式 |
|---|---|
| `graph_method="density", density=0.1`（默认） | 按绝对 FC 强度，目标边数 `ceil(0.1×N×(N−1)/2)`；截止并列全部保留，实际密度可高于请求值，非零边不足时可更低 |
| `graph_method="threshold", threshold=0.2` | 保留绝对强度达到阈值的非零边；阈值只在该方法生效，不是 p 值 |
| `graph_method="knn", k=5` | 各 ROI 取最强 k 个非零连接，取两侧邻居选择的并集，包含截止并列；最终度不必等于 k |
| `graph_method="weighted"` | 全部非零边 |
| `graph_method="mst"` | 绝对权重的最大生成森林；孤立节点保留 |

均去掉自环、保留被选边原始符号。正/负强度分开记录；路径指标只使用正边、长度 `1/weight`，不能把负相关直接当负路径长度。完整指标定义见 [网络方法](network/methods.md)。提取可支持更多 ROI，但网络模块上限为 1000 个 ROI。

### 原生超图（可选）

```python
network = result.analyze_network(AnalysisConfig(
    graph_method="density", density=0.1,
    hypergraph_method="multiscale", hypergraph_ks=[5, 10],
    compute_graph=True, compute_hypergraph=True,
))
export_result(network, "results/network-multiscale-01.zip")
```

`AnalysisConfig()` 默认同时计算图和超图：`compute_graph=True`、`compute_hypergraph=True`。默认超图 `hypergraph_method="knn"` 使用 `k=5`；`hypergraph_ks=[5,10]` 只在 `multiscale` 生效。`template` 使用 `groups={组ID: [ROI ID, ...]}`；`custom` 使用 `custom_edges=[{"id": ..., "members": [...], "weight": ...}]`，两者默认空，须提供所需成员。

FC-profile 超图将完整 FC 的对角线置零，把每行视作该 ROI 的连接模式，按**有符号余弦相似度**选择邻居。每条超边包含中心及邻居；截止并列保留，完全相同的生成成员集合合并，记录中心和尺度，生成超边权重为 1。它不同于按 `|FCij|` 选择普通图邻居；也不是从 fMRI 直接估计多体相互作用。

`connectivity_method="pearson"` 是网络模块读取时序时的默认值；从 `Connectome` 传入矩阵时不生效。改变相关方法应回到第 6 节的 `Config(method=...)`。

### 显示筛选与分析选边分别记录

`result.plot_views(..., threshold=0.3, max_edges=200)` 和三维页面的阈值、选择、透明度只控制显示。完整矩阵不变，已算出的图指标也不会随旋转或显示筛选改变。要改变网络分析的边，须改变 `AnalysisConfig` 并重新分析。提取页的三维和八视图共享显示选择；网络分析页展示相应分析结果的普通边/超边。球棍不是纤维束，超边不是已证实的不可约生理相互作用。

## 8. 质控：何时继续，何时停止

| 检查位置 | 看什么 | 处理要求 |
|---|---|---|
| 输入计划 | TR、帧数、切片方向与采集时间、同一被试的 BOLD/T1 | 冲突或不匹配先解决，不能靠改文件名/头信息掩盖问题 |
| `qc.html` 脑提取图 | 皮层/小脑是否被误删、颅外组织是否明显残留 | 明显异常先停止；可检查输入或提供独立 T1 脑掩膜后在新目录重跑 |
| BOLD→T1 与 T1→MNI 叠加 | 脑室、外轮廓、左右方向、皮层是否整体对齐 | 明显错位不能继续做标准图谱提取；头动/刚体配准不能修复所有 EPI 畸变 |
| WM/CSF 叠加 | 掩膜是否落在对应组织，是否混入大量灰质/脑外 | 组织数达到运行下限不代表组织选择正确 |
| 覆盖与运动曲线 | 视野缺失、FD/DVARS 峰值、持续头动 | 覆盖 <50% 自动停止；超过下限仍须检查。按研究预先制定的扫描排除和删帧规则处理 |
| 连接结果 `qc.json` | 保留帧数、原始帧号、回归列/设计秩、警告与 ROI 体素数 | `min_samples=20` 只是数值下限；警告不等于已解决，不能仅凭矩阵可绘制认定可用于研究 |

`qc_reviewed=True` 是研究者检查后的确认，不是自动质量认证。不提供统一的“合格 FD”或最低可靠扫描时长；这两项应结合采集方案、FD 定义与研究设计决定。单例验证范围见第 10 节。

## 9. DICOM、命令行与公共函数

```shell
brainfc convert ./dicom --scan
brainfc convert ./dicom --series-id <上一步的序列ID> --kind bold --output ./bold-converted
brainfc convert ./dicom --series-id <T1序列ID> --kind t1w --output ./t1-converted
brainfc process ./bold-converted/image.nii.gz --t1w ./t1-converted/image.nii.gz --output ./preprocessed
```

Python 对应 `scan_dicom()`、`convert_dicom_python()`、`inspect_raw()`、`preprocess_fmri()`、`load_preprocessed()`；完整签名、错误、返回值见 [API 参考](api-reference.md)。`discover_raw()` 保留同一 subject/session 内的候选对，多 T1 不会随意选择。

通用 DICOM 由 dicom2nifti 的布局与几何校验决定是否支持，不能承诺所有厂商、压缩方式及私有格式都能转换。无可靠切片时间的布局不会伪造 `SliceTiming`。不支持的数据会报错。

公共入口分工：`scan_dicom()` 返回可选择的序列；`convert_dicom_python()` 转换指定序列；`discover_raw()` 返回 BIDS 候选；`inspect_raw()` 检查元数据；`preprocess_fmri()` 返回 `PreprocessedRun`；`load_preprocessed()` 载入完成的运行；`PreprocessedRun.extract()` 返回 `Connectome`；`Connectome.analyze_network()` 返回 `AnalysisResult`。`Connectome.save()` 保存目录，`export_result()` 保存网络 ZIP，两者不能混为同一个导出格式。

## 10. 保存什么，如何复现与报告

输出包含标准空间 BOLD、脑掩膜、WM/CSF 掩膜、混杂表、`transforms/`、`work/` 中间影像、`qc.html`、`qc.json`、`preprocessing.json`、`run.json`、`output_hashes.json` 和 `stages.json`。失败输出保留供检查，但不能加载为成功结果。重跑需新目录。

检查脑提取完整性、脑室/皮层对齐、WM/CSF 所在组织、脑覆盖及 FD/DVARS。模板传播掩膜与模板的重叠不是独立分割精度；代码和界面不会以该数值自动宣告质量合格。

| 要核对的事项 | 读取哪里 |
|---|---|
| 原始文件、模板、实际 TR / 切片时间、空间算法、种子与版本 | 预处理目录 `preprocessing.json`；`resolved` 为读入后的采集值，`config` 为用户配置；模板有 SHA-256 |
| 预处理完成状态与输出完整性 | `stages.json`、`output_hashes.json`；`load_preprocessed()` 核验清单中的核心影像、混杂与记录文件，不是对全部中间文件或人工质控的认证 |
| 实际滤波、回归列、丢弃帧、相关方法 | 连接目录 `provenance.json` 的 `config`、`versions`、`raw_preprocessing`；无需从截图猜参数 |
| 完整数值与排列 | `connectivity.npy/csv`、`fisher_z.npy/csv`、`timeseries.npy/tsv`、`rois.tsv`、`samples.tsv`；矩阵和 ROI 表共用顺序 |
| 留存样本与文件校验 | 连接目录 `qc.json`、`manifest.json`；`samples.tsv` 保留 0 起始的原始索引，删帧后存在间断时不能当连续时段 |
| 网络选择及指标含义 | 网络导出的 `result.json` 中 `config`、`metadata`、`graph`、`hypergraph`；报告请求与实际密度，超边成员和构建方法 |

研究方法应至少报告：软件/依赖版本；采集 TR 与切片信息来源；初始帧数；是否做层间时间/畸变校正；配准模型、准确模板和分辨率；平滑 FWHM；图谱与 ROI 顺序；回归列和 GSR；带通、FD 定义及阈值；质控排除规则与实际保留帧数；相关估计器；网络选边方法/实际密度或超图尺度。实际记录是方法部分的依据，不能把本页默认值直接当作自己的运行参数。

### 已验证范围与未实现部分

[原始 fMRI 验证记录](validation-v0.5.0.md)包含已知信号层间校正、几何与刚体配准测试、转换对照，以及一例成人静息态原始数据完整运行。该例为 150 帧、TR 2 s、81 层，丢弃 5 帧、Schaefer100、0.01–0.1 Hz、无空间平滑/FD 删帧，得到 100×100 FC 和 145 个保留点；这些数字是验证实例，不是各数据集推荐参数。仓库 `rest01` 是已有处理的公开衍生样例，不能将打开它等同于重新执行原始影像预处理。

当前没有场图/反向相位编码畸变校正、多回波合并、变 TR/稀疏采样、儿童专用模板流程、皮层表面重建、任务 GLM 或 DWI/DTI。没有 MATLAB/SPM/DPABI 逐值等价验证，也没有据此获得多中心、全厂商或临床有效性结论。原始路线通过 Python 包调用 ANTs 编译内核，不等于所有算法以纯 Python 编写。

DICOM 元数据只输出处理需要的字段，但结构影像仍包含可识别解剖形态，处理输出也会记录本机输入路径。**转换和预处理不等于脱敏**；原始影像与此类结果应留在本地，不属于包内公开样例。

## 11. 实现依据与源码

本页描述本库实际行为；上游文档解释所调用算法，不代表其全部功能均已在 BrainFC 暴露。

- [原始空间流水线](https://github.com/hanxiangmin/brainfc/blob/main/src/brainfc/raw/pipeline.py) · [层间时间实现](https://github.com/hanxiangmin/brainfc/blob/main/src/brainfc/raw/temporal.py)
- [ROI 提取](https://github.com/hanxiangmin/brainfc/blob/main/src/brainfc/imaging.py) · [时序与 FC 核心](https://github.com/hanxiangmin/brainfc/blob/main/src/brainfc/pipeline.py)
- [普通图](https://github.com/hanxiangmin/brainfc/blob/main/src/brainfc/network/graph.py) · [原生超图](https://github.com/hanxiangmin/brainfc/blob/main/src/brainfc/network/hypergraph.py)

- [ANTsPy 配准与变换接口](https://antspyx.readthedocs.io/en/stable/registration.html)
- [ANTsPy N4](https://antspyx.readthedocs.io/en/latest/utils.html)
- [ANTsPy Atropos](https://antspyx.readthedocs.io/en/latest/segmentation.html)
- [dicom2nifti](https://icometrix.github.io/dicom2nifti/)
- [BIDS 切片时间与方向定义](https://github.com/bids-standard/bids-specification/blob/master/src/schema/objects/metadata.yaml)
- [TemplateFlow MNI152NLin6Asym 定义](https://github.com/templateflow/tpl-MNI152NLin6Asym)
- [dcm2niix UIH 几何与切片时间实现参考](https://github.com/rordenlab/dcm2niix/blob/master/console/nii_dicom.cpp)
