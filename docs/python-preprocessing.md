# Python 原始 fMRI 全流程

在已有 **Python 3.11–3.13 的 conda 环境**中安装即可，无需重装 Python：

```shell
python -m pip install -U brainfc
brainfc serve
```

界面选择“原始 NIfTI / BIDS”或“原始 DICOM”，依次完成 **选影像 → 确认方案 → 预处理 → 检查质控 → 功能连接**。原始 NIfTI 只需 BOLD 和同一人的 T1；同名采集 JSON 自动读取。DICOM 文件夹先识别序列，确认 BOLD 与 T1。输出目录自动安排。

所有计算通过 Python 包完成。ANTsPy 的编译内核随 wheel 安装，不需要 MATLAB、SPM、Docker、FreeSurfer 许可证或独立命令行工具。首次使用会下载约 1.5 MB 的 TemplateFlow 模板；Schaefer 图谱另行缓存。

## 最短 Python 用法

```python
from brainfc import preprocess_fmri

run = preprocess_fmri(
    "sub-01_task-rest_bold.nii.gz",
    "sub-01_T1w.nii.gz",
    "results/preprocessed-01",  # 必须是新目录
    progress=print,
)

# 先打开 results/preprocessed-01/qc.html，检查对齐、组织分割和头动。
result = run.extract("schaefer100", qc_reviewed=True)
result.save("results/connectome-01")
```

之后可在另一次 Python 会话继续，不必重复预处理：

```python
from brainfc import load_preprocessed

run = load_preprocessed("results/preprocessed-01")  # 验证输出完整性和 SHA-256
result = run.extract(qc_reviewed=True)
```

## 数据与参数确认

要求单回波、恒定 TR 的 4D 静息态 BOLD 和匹配的 3D T1，具有有效 qform/sform、毫米单位、正交体素轴。未实现多回波合并、变 TR / 稀疏采样、畸变校正和表面重建。原始 DWI 不属于此入口。成人 MNI 模板是否适用于儿童、明显病变等数据，需要独立确认。

TR 按实际采集 JSON / 影像头读取；数值冲突时停止。切片时间采用 BIDS 的**秒**，支持多带相同时间；负的 `SliceEncodingDirection` 会反转时间列表。切片维度由 JSON 或 NIfTI `dim_info` 读取。只有可靠元数据缺失时才需要补充；不按奇偶层数猜采集顺序。BIDS 继承元数据需先整理为该次扫描的独立 sidecar。

```python
from brainfc import PreprocessConfig, inspect_raw, preprocess_fmri

settings = PreprocessConfig(
    discard=5,             # 示例选择，按采集与研究方案确认；默认 0
    smoothing_fwhm=0,       # 默认不平滑
    # slice_axis=2,         # 仅在采集记录确认 k 为切片维度、文件头缺失时填写
    # slice_timing="skip",  # 仅在明确决定跳过时启用，并记录到结果
)
plan = inspect_raw("bold.nii.gz", "t1w.nii.gz", config=settings)
print(plan["ready"], plan["missing"])
run = preprocess_fmri("bold.nii.gz", "t1w.nii.gz", "preprocessed-02", config=settings)
```

`PreprocessConfig` 完整默认值：`t_r=None`、`slice_timing="auto"`、`slice_axis=None`、`reference=0.5`、`discard=0`、`smoothing_fwhm=0`、`seed=42`。`reference` 是 TR 的比例，不是切片编号。`auto` 遇到缺失切片元数据会停止确认。

## 实际算法与顺序

| 步骤 | 实现及输出 |
|---|---|
| DICOM 转换 | `pydicom` + `dicom2nifti`；联影 UIH 拼图按每层位置与时间解码；标准 TE/TR 毫秒转秒；不同序列与回波分开 |
| 层间时间校正 | SciPy FFT、两端各反射填充 T 帧；逐切片移到 `reference × TR`；保留全部帧索引 |
| 头动估计 | ANTs `BOLDRigid`；参考为去除指定开头帧后的均值；保存每帧刚体矩阵 |
| T1 与脑提取 | T1 工作网格 1.5 mm；N4 偏置校正；未给独立脑掩膜时，先做整头 SyN，再逆变换传播模板脑掩膜；脑内再 N4 |
| 组织分割 | ANTs Atropos，3 类 KMeans 初始化、MRF `[0.2,1x1x1]`、5 次迭代；按 T1 强度均值排序 CSF / GM / WM |
| 标准化 | 脑 T1 → MNI152NLin6Asym 的 SyN，非线性迭代 `(60,40,20)`；BOLD 参考 → T1 的刚体互信息配准 |
| 重采样 | 合成标准化、BOLD-to-T1 和每帧头动变换，从层间时间校正后的输入**只做一次最终空间插值**；2 mm、线性插值 |
| 脑覆盖 | EPI 信号掩膜变换到模板，与模板脑掩膜取交集；覆盖率 <50% 停止；其余仍需目视检查 |
| 混杂信号 | WM / CSF 概率 >0.9，T1 工作网格腐蚀 1 体素，最近邻变换后各至少 20 体素；从未平滑 BOLD 提取均值 |
| 可选平滑 | 逐帧三维高斯，FWHM 单位 mm；只影响 ROI 输入，混杂均值仍来自未平滑数据 |
| 时序与 FC | `run.extract()` 调用既有 Nilearn 联合回归/滤波，再计算完整有符号 Pearson 或所选相关矩阵、单独 Fisher-z |

ANTs 使用 LPS 物理坐标，NiBabel 使用 RAS；影像适配器通过 NIfTI 保存几何，已设旋转坐标往返测试。图像变换和点变换有不同方向约定，不能把变换列表反向后直接当成逆变换。

该实现参考教程的步骤组织，**不声称与 SPM、DPABI 或 fMRIPrep 数值等价**。切片插值边界、配准优化、组织分割和运动混杂模型均有明确差异。

配准种子通过 ANTsPy 0.6.3 的配置接口传入底层 ANTs；仅向 `registration()` 传旧版 `random_seed` 关键字在该版本不会生效。结果记录种子、库版本和 ITK 线程环境，跨平台或多线程计算不保证逐位一致。实际验证范围见 [0.5.0 验证记录](validation-v0.5.0.md)。

## 去噪设置

`run.extract()` 默认使用 0.01–0.1 Hz、去趋势和样本 z-score，回归 9 个旋转矩阵元素、3 个 LPS 仿射偏移及 WM/CSF 均值。这是 BrainFC 的可修改建议；不是数据集官方统一参数，也不是 SPM motion6 / Friston-24。矩阵列可能线性相关，提取会检查实际设计秩和残余自由度。

```python
from brainfc import Config

result = run.extract(
    config=Config(high_pass=0.01, low_pass=0.08, discard=5),
    qc_reviewed=True,
)
```

`discard` 应与预处理配置一致。TR 和空间由真实输出绑定。FD 默认不用于删帧；显式 `fd_threshold` 才启用。这里的 FD 是 **ANTs generalized FD，`fdOffset=50 mm`**，不是 Power FD；不能直接套用另一种 FD 的阈值。首行 FD/DVARS 未定义，写为 `n/a`。DVARS 为原始强度单位。全局信号提供为检查列，默认不回归。

## DICOM 与命令行

```shell
brainfc convert ./dicom --scan
brainfc convert ./dicom --series-id <上一步的序列ID> --kind bold --output ./bold-converted
brainfc convert ./dicom --series-id <T1序列ID> --kind t1w --output ./t1-converted
brainfc process ./bold-converted/image.nii.gz --t1w ./t1-converted/image.nii.gz --output ./preprocessed
```

Python 对应 `scan_dicom()`、`convert_dicom_python()`、`inspect_raw()`、`preprocess_fmri()`、`load_preprocessed()`；完整签名、错误、返回值见 [API 参考](api-reference.md)。`discover_raw()` 保留同一 subject/session 内的候选对，多 T1 不会随意选择。

通用 DICOM 由 dicom2nifti 的布局与几何校验决定是否支持，不能承诺所有厂商、压缩方式及私有格式都能转换。无可靠切片时间的布局不会伪造 `SliceTiming`。不支持的数据会报错。

## 质控与文件

输出包含标准空间 BOLD、脑掩膜、WM/CSF 掩膜、混杂表、`transforms/`、`work/` 中间影像、`qc.html`、`qc.json`、`preprocessing.json`、`run.json`、`output_hashes.json` 和 `stages.json`。失败输出保留供检查，但不能加载为成功结果。重跑需新目录。

检查脑提取完整性、脑室/皮层对齐、WM/CSF 所在组织、脑覆盖及 FD/DVARS。模板传播掩膜与模板的重叠不是独立分割精度；代码和界面不会以该数值自动宣告质量合格。

DICOM 元数据只输出处理需要的字段，但结构影像仍包含可识别解剖形态，处理输出也会记录本机输入路径。**转换和预处理不等于脱敏**；原始影像与此类结果应留在本地，不属于包内公开样例。

## 实现依据

- [ANTsPy 配准与变换接口](https://antspyx.readthedocs.io/en/stable/registration.html)
- [ANTsPy N4](https://antspyx.readthedocs.io/en/latest/utils.html)
- [ANTsPy Atropos](https://antspyx.readthedocs.io/en/latest/segmentation.html)
- [dicom2nifti](https://icometrix.github.io/dicom2nifti/)
- [BIDS 切片时间与方向定义](https://github.com/bids-standard/bids-specification/blob/master/src/schema/objects/metadata.yaml)
- [TemplateFlow MNI152NLin6Asym 定义](https://github.com/templateflow/tpl-MNI152NLin6Asym)
- [dcm2niix UIH 几何与切片时间实现参考](https://github.com/rordenlab/dcm2niix/blob/master/console/nii_dicom.cpp)
