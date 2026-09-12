# 更新记录

## 0.4.0 — 源码合并版，尚未发布到 PyPI

- 合入 Hyper-Brain 的普通图、原生超图、结构指标、组间统计、图谱管理和完整网络工作台。
- 新增 `brainfc.network`、`Connectome.to_network()` / `analyze_network()` 和 `brainfc network`。
- `brainfc serve` 同时提供提取和 `/networks/` 网络分析；提取结果自动携带矩阵、ROI 顺序、坐标和处理记录，免重新上传。
- 保留 `hicbrain` 导入与命令兼容层；升级已有环境前请移除旧 `hic-brain` distribution，避免共享文件冲突。

- 新增经授权、去除直接身份标识的静息态样例 `rest01`，可通过 Python 或 `brainfc demo --kind rest01` 运行。
- 记录像素文字、文件头、公开文件与发行物的隐私核查范围；原始 DICOM、个体 T1/BOLD 和本地影像压缩包不公开。
- 提供有对照实验证据的 UIH TE/读出参数核验脚本，保留源文件并拒绝未知冲突。
- README 矩阵和同步脑网络图改用真实 rest01 结果；标注原始脑区顺序、网络边界与固定色标，并提供绘图脚本。

## 0.3.0 — 2026-09-12

- 正式采用分发名 `brainfc`、Python 导入名 `brainfc`、命令行 `brainfc`。
- 默认安装包含科学计算和本地网页，无需额外选择 `[web]`。
- 原有函数、处理顺序与结果契约保持不变；完整 API 和示例同步新名称。
- 源码单独存放于新的 `brainfc` 目录，旧发行包及结果保留。
- 已发布到 PyPI；后续源码增强见上方“未发布”部分。

## 0.2.1 — 2026-09-12

原名 fMRI Connect 的本地开源发布准备版本。

- 补全 Python 处理函数、Config 参数、Connectome 方法的源码 docstring 与自动生成参考。
- 增加中文使用指南、格式/方法/输出契约、命令行全参数、本地 HTTP 指南、离线手册和可运行示例。
- HTTP 请求增加明确的字段模型，缺失/未知字段返回 422；OpenAPI 提供实际参数定义。
- 补齐 `fisher_z.npy`、`timeseries.npy`、`manifest.json` 的直接下载入口。
- 包版本、命令行、HTTP 和结果 provenance 使用同一版本来源，修复旧版本硬编码。
- 修复预检查对 MGZ 头信息的 NIfTI 假设，并允许沿用文件名已明确的空间；未知预检查阶段会报错。
- 准备独立源码发布包、许可证/第三方说明、贡献说明、引用信息与 GitHub CI/手动 PyPI 发布流程。

数值估计与去噪算法未作更改。现有完整输出目录保留原来的数据和来源记录。

## 0.2.0 — 2026-09-12

- 三步引导、自动读取元数据/配套文件、来源明确的 ABIDE/ADNI/ADHD-200/MDD/PPMI 方案提示。
- 平滑脑壳、前方 ROI 悬停名称和与 3D 同步的八视图筛选。
- 44 项 Python 测试和本地浏览器交互验证；原始 fMRIPrep 全流程未实跑。

## 0.1.0 — 2026-09-12

- 单 run 体积/CIFTI/GIFTI/表格读取、ROI 均值、混杂回归、删帧、Pearson/Spearman/偏相关与 Fisher-z。
- Python API、CLI、本地网页、矩阵/八视图/离线报告、来源指纹与外部预处理适配器。
