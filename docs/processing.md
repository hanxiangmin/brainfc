# 处理顺序与方法

这里描述本库当前实际执行的代码，方便复现和选择参数。

从原始数据开始请先读 [原始 fMRI → 脑网络：完整流程与参数](python-preprocessing.md)，其中说明空间预处理、质控和网络构建。本页详细定义 `extract_connectome()` 的 ROI 提取、时序清理和矩阵计算。

## 总流程

```text
原始 DICOM → Python 转换 → BOLD + T1 → Python 预处理 → 检查报告
                                                               ↓
已预处理体积 / CIFTI / GIFTI → 验证空间与标签 → ROI 均值 ──────────┤
已分区 ROI 时序 → 核对方向、表头与 ROI 顺序 ───────────────────────┘
    → 删除开头帧 → 联合时序清理与删帧 → 有符号相关矩阵 → Fisher-z
    → 质控与来源 → 保存 / 矩阵 / 八视图 / 交互 3D
```

## 空间处理和均值

体积输入要求 4D，整数标签图谱要求 3D。图谱与掩膜以最近邻插值到 BOLD 网格，只调整采样网格，不求配准变换。0 为背景；图谱的所有正标签必须在最终 BOLD/mask 内保留，否则停止。按原始标签数值升序生成 ROI。每个 ROI 是纳入体素的算术平均，不按概率加权。

实现按 8 帧读取体积，BOLD 块转为 float32，均值累加为 float64。体积 ROI 的显示质心从原始图谱计算，提供 ROI 表坐标时优先使用表中坐标。mask 不会移动显示质心。

CIFTI dense 要求完全相同 BrainModelAxis，按 16 帧读取并计算各标签灰坐标均值；ptseries 直接使用 ParcelsAxis 顺序。GIFTI 当前完整载入时间序列，按标签顶点均值分区。所有图谱只支持离散非负整数标签，至少 2、最多 2000 个非背景标签；已有分区时序没有同样的 2000 列上限。

## 初始帧、非稳态和 FD

先根据原始帧构造统一保留掩码，再从信号/混杂中移除前 `discard` 帧。混杂表的行数必须等于删帧前总帧数。

| 条件 | 行为 |
|---|---|
| 初始帧索引 `< discard` | 删除 |
| 任一 `non_steady_state_outlier*` 列非零 | 删除 |
| 启用 FD 且 `FD > fd_threshold` | 删除；等于阈值保留 |
| 启用 FD 且首帧 FD 缺失 | 删除首帧 |
| 除首帧之外 FD 缺失/非有限，或存在负 FD | 报错；即使未启用阈值，只要混杂表有 FD 列就检查 |
| 未启用 FD | 不按 FD 数值删除，仍计算已提供 FD 的均值/最大值 |

`fd_censored` 与 `nonsteady_censored` 可能重叠，也可能与初始帧重叠。最终唯一删帧数看 `n_censored`，原始保留位置看 `sample_indices`。平均 FD 使用所有原始有限 FD 值，不是仅保留帧的平均值。连续保留时长不能用 `n_retained × TR` 推断，该值只是保留样本的时间总量。

## 混杂回归

默认自动识别完整的 `trans_x/trans_y/trans_z/rot_x/rot_y/rot_z`，再加存在的 `white_matter`、`csf`。只出现部分 motion6 会报错；普通自定义混杂表需要明确列名。不会把文件中所有列自动回归。

只有名称含 `derivative1` 的被选列允许首行 NaN 填 0，填充值逐项记录。其他选中值必须有限。检查纳入截距后的保留帧混杂设计秩；保留帧数减设计秩小于 3 则停止。这是数值可行性检查，不代表统计自由度的完整估计，也未计入滤波/自相关造成的有效样本量变化。

## Nilearn 联合清理

本库固定依赖 `nilearn>=0.14,<0.15`。调用 `signal.clean` 时显式传入 detrend、`standardize='zscore_sample'` 或 False、`standardize_confounds=True`、两个截止频率、TR、sample_mask、`extrapolate=True`；有截止频率则使用 Butterworth，无则关闭滤波。

启用 Butterworth 和删帧时，被剔除位置参与插值/滤波安排，最后仅返回保留样本；不会把删帧后的不规则采样序列当成新的等间隔原始序列再次计算滤波。具体联合处理由 Nilearn 实现，参考 [signal.clean 官方说明](https://nilearn.github.io/stable/modules/generated/nilearn.signal.clean.html)。结果保存实际 Nilearn 版本和处理提示。

不额外提供插值、滤波阶数或滤波后残差自由度参数。保留点不足、短序列滤波失败、清理后 ROI 标准差 ≤1e−10 或非有限值均停止计算。

## 矩阵

| `method` | 实际算法 |
|---|---|
| `pearson` | 清理后 ROI 信号的 Pearson 相关（NumPy `corrcoef`） |
| `spearman` | 每列进行平均并列秩变换，再 Pearson 相关 |
| `partial` | scikit-learn `LedoitWolf` 估计精度矩阵 P；非对角线 `−Pij / sqrt(Pii × Pjj)` |

结果对称化、截到 [−1,1]，对角线设为 1。Fisher-z 单独保存：`atanh(clip(r, −1+1e−7, 1−1e−7))`，对角线 0。该转换对三种方法都执行，是数值转换，不附带显著性或正态分布保证。

没有 p 值、FDR、组间比较、疾病模型或随机图检验。球棍边表示功能相关，不表示结构纤维束或因果作用。

## 可视化

只取上三角非零边；先按绝对值阈值和选中脑区/边过滤，再稳定地按绝对强度降序取前 `max_edges` 条。相同强度按矩阵上三角顺序稳定排列。3D 与八视图使用同一条目集合，完整矩阵始终保留全部正负权重。

解剖参考的正值掩膜经过闭运算、填孔、0.65 体素 Gaussian 插值及 marching cubes；WebGL 继续平滑显示网格。这些操作只影响显示。没有参考时显示图谱覆盖包络；没有可用影像但有坐标时仅显示节点和边。静态 SVG/PDF 的脑壳是栅格层，线与点保持 Matplotlib 输出形式，不能宣称全部矢量化。

## 原始影像预处理

`preprocess_fmri()` 完成层间时间、头动、T1 N4 / 脑提取 / Atropos、SyN 标准化、逐帧合成变换和组织混杂。详细步骤、默认值、限制、DICOM 兼容与验证见 [Python 全流程](python-preprocessing.md)。

`extract_connectome()` 本身仍接收已处理影像，不会根据文件名自动再次预处理。旧 `preprocessing` 模块的外部 dcm2niix/fMRIPrep 适配器为兼容已有脚本保留；网页使用 Python 路线。
