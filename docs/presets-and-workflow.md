# 0.2.0：少填写、按数据类型引导

常用入口为 **选择数据 → 确认处理方案 → 开始处理**。数据来源可以保持“自有数据 / 暂不指定”。选择一个主 BOLD 或 ROI 时序即可开始；本次扫描的 JSON、fMRIPrep confounds 和脑掩膜可以同时选择。大文件可展开“使用本地路径”免上传。

程序能从数据确定的信息会自动填入；需要研究者判断的内容保留确认。后续步骤不能提前跳转，修改上一步会清除后续复核。图谱路径、滤波、FD、丢弃帧数等放在高级设置中。缺少或冲突的必要信息会展开提示。

## 自动填写的依据

| 信息 | 自动填写依据 | 无法确定时 |
|---|---|---|
| 文件类型 | NiBabel 影像轴 / 文件内容 | 拒绝把 T1、连接方阵或非时序 CIFTI 当作 BOLD |
| 文本表头 | 首个非注释行是否为数值 | 数值 ROI 编号表头存在歧义，需在时序表选项中手动开启表头；不自动转置 |
| TR | 同名 JSON 与带明确秒单位的影像头 | 不一致则报错；方案参考与扫描值不同则采用扫描值并提示确认 |
| 数据空间 | 文件名 `space-*` 或此前同一文件的已确认记录 | 需确认模板 / 个体空间，不能从影像尺寸猜测 |
| confounds / mask | 同一次 fMRIPrep 扫描的精确实体匹配 | 不跨 subject、session、task、run、echo 匹配 |
| 解剖参考 | 同空间匹配的脑掩膜，或此前确认的参考文件 | 默认使用图谱包络或仅显示坐标，可另选参考 |
| 图谱 | 明确 MNI152NLin6Asym → 建议 Schaefer100；MNIColin27 → 建议 AAL SPM12 | 不猜其他空间；可展开高级设置换图谱。首次载入可能联网 |
| 上次空间与配套文件 | 输入及配套文件 SHA-256 校验一致 | 文件改变即不复用；不会自动复用上次去噪策略 |
| 原始数据输出目录 | 本地工作区中的新目录 | 可在高级设置修改；源文件不覆盖 |

图谱建议、默认 Pearson、默认不带通、基础 motion6 + WM/CSF 是本库的实现选择，**不称作数据集官方默认**。不按疾病名称自动确定预处理。没有 confounds 时，用户只需选择“上游已去噪，本次保留”或“明确跳过”；前者自动关闭重复滤波、去趋势、标准化和初始帧剔除。

## 官方方案参考

核对日期：2026-09-12。参考参数只适用于指定版本，需由用户确认实际扫描。

| 来源 / 版本 | 可预填的采集参考 | 适用边界与来源 |
|---|---|---|
| ABIDE I / II 原始数据 | TR 从扫描读取 | 多站点；查看 [ABIDE 项目](https://fcon_1000.projects.nitrc.org/indi/abide/) 的站点采集记录 |
| ABIDE PCP | 不设通用 TR 或去噪参数 | 区分 pipeline 和策略，参见 [PCP 官方仓库](https://github.com/preprocessed-connectomes-project/abide)；不得重复处理已去噪版本 |
| ADNI 3 Basic | 参考 TR 3 s | [ADNI 3 方案表](https://adni-lde.loni.usc.edu/wp-content/uploads/2017/07/ADNI3-MRI-protocols.pdf)给出近似方案参数；不能套用所有 ADNI 数据 |
| ADNI 3 Advanced | 参考 TR 0.6 s | 同上；实际实现随硬件 / 软件不同。[ADNI 采集说明](https://adni.loni.usc.edu/quick-start-guide-asset/MRI_tables.html)将 DICOM 头作为单次扫描参数的主要依据 |
| ADHD-200 Brown RawDataBIDS | TR 2 s | [Brown 官方 JSON](https://fcp-indi.s3.amazonaws.com/data/Projects/ADHD200/RawDataBIDS/Brown/task-rest_bold.json)。不推广到其他站点；时间点数按实际影像读取 |
| REST-meta-MDD 已处理时序 | 不设全项目通用 TR | [项目官方说明](https://rfmri.org/REST-meta-MDD)：DPARSF、参与者层面 Friston-24、组层面 mean FD；本库不把组层面校正当作单例删帧 |
| PPMI 2025 Multiband 主 BOLD | TR 1 s | [2025-01-22 MRI 手册](https://www.ppmi-info.org/sites/default/files/docs/PPMI_002_MRI_Imaging_Manual_Final_v1.0_20250122_Executed-1.pdf)表 3：600 次测量；反向 10 帧为畸变校正，不作为主 BOLD |
| PPMI 2025 非 Multiband 主 BOLD | TR 2.5 s | 同手册表 7：240 次测量。不得套用到任意历史 PPMI 扫描；手册也提示站点可有细微差异 |

预设只帮助确认已经采集的数据，不用于重新定义扫描采集。程序不会根据表格中的预计帧数裁切数据，也不会从“interleaved”文字猜完整 SliceTiming。

## 不同输入的流程

- 已处理 4D 影像：自动识别 → 确认上游预处理和空间 / 图谱 → 去噪选择 → 最终复核。配准必须已完成；重采样只匹配网格。
- ROI 时序：自动识别与表头解析 → 选择是否提供坐标 → 确认上游去噪 → 最终复核。没有坐标可生成矩阵，不猜测图谱。
- CIFTI：识别 SeriesAxis；dtseries 必须有匹配 BrainModelAxis 的 dlabel，ptseries 已有 ParcelsAxis，直接使用时序。
- GIFTI：单半球 func.gii 与 label.gii；必须确认表面、半球和顶点顺序一致。
- 原始 NIfTI / BIDS：整理 BIDS → BOLD/T1 基础检查 → fMRIPrep 正式校验及预处理 → 用户检查 HTML 报告 → 选择 derivatives 主扫描。
- DICOM：dcm2niix 转换 → 人工核对序列并整理 BIDS → 上述原始数据流程。允许明确选择已经在外部完成的步骤，但预处理输出和质控确认仍需检查。

必要的工具仍为外部 dcm2niix / Docker Linux / FreeSurfer 许可。本机没有完成真实 DICOM→fMRIPrep 全链路运行，自动引导不会把“命令生成”标作“预处理完成”。

## Python 接口

```python
from brainfc import dataset_presets, dataset_preset

catalog = dataset_presets()
hint = dataset_preset("adni", "adni3-basic")
print(hint["t_r"], hint["source"])  # 3.0；仅作确认参考
```

界面确认记录保存到 `provenance.workflow`，其中包括数据来源、版本、官方预设、明确跳过的选项和扫描 TR 的差异提示。Python / CLI 原有接口兼容，不强制模拟 UI 步骤状态；仍使用相同的严格提取核心。
