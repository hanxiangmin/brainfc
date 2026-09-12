# 现有工具调研与实现选择

核查日期：2026-09-12。以下为官方说明与本项目实现选择，不将“支持读取”写成“已完成真实队列预处理”。

| 工具 | 能力 | 本项目参考方式 |
|---|---|---|
| [NiBabel](https://nipy.org/nibabel/reference/nibabel.cifti2.html) | NIfTI、CIFTI、GIFTI 等影像与坐标轴读取 | 直接依赖，检查 NIfTI affine、CIFTI 轴 |
| [Nilearn](https://nilearn.github.io/stable/modules/generated/nilearn.maskers.NiftiLabelsMasker.html) | 分区时序、去噪、连接计算、图谱与可视化 | 直接使用图谱下载和 signal.clean；分块求 ROI 均值以控制峰值内存 |
| [CONN](https://web.conn-toolbox.org/) | 成熟的图形化 fMRI 连接分析、去噪、质量控制 | 参考用户流程，不复制其 MATLAB 代码或统计结果 |
| [fMRIPrep](https://fmriprep.org/en/stable/) | 头动校正、配准、标准化及预处理报告 | 外部 Docker 适配器；本库不重新实现空间预处理 |
| [XCP-D](https://xcp-d.readthedocs.io/en/latest/) | 已预处理 fMRI 后处理 | 对照后处理边界；初版未集成 XCP-D runner |
| [NetPlotBrain](https://www.netplotbrain.org/) | Python 脑网络与多视角图形 | 参考八视图表达；渲染使用 Matplotlib |
| [dcm2niix](https://github.com/rordenlab/dcm2niix) | DICOM → NIfTI + 元数据 | 外部命令适配，不随 pip 包安装二进制 |
| [Hyper-Brain](https://github.com/hanxiangmin/Hyper-Brain) | 本地 Python / 3D 脑图与超图界面 | 直接复用当前项目的 BrainScene、viewerTypes、viewerAppearance 组件，保留许可 |

## 为什么单独做这个库

已有工具覆盖了主要计算环节。新库的价值是将常见文件入口、明确的空间/脑区映射、逐扫描提取、中文界面和既有三维模板接在一起，同时暴露可直接脚本调用的 Python API。默认不宣称“一条 pip 命令就完成所有原始 MRI 预处理”。

图像提取要求调用者确认预处理完成。图谱到影像的重采样只解决网格分辨率，不解决配准。同一模板名声明也需要上游配准质量检查，不能仅凭 affine 相似推断解剖对齐。

实现依据：[Nilearn signal.clean](https://nilearn.github.io/stable/modules/generated/nilearn.signal.clean.html)、[fMRIPrep 使用说明](https://fmriprep.org/en/stable/usage.html)。本库默认不过滤频带；用户明确指定过滤参数后，按 Nilearn 的去噪次序处理。
