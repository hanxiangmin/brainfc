# ABIDE / ADNI / REST-meta-MDD / ADHD-200：下载什么

官方入口核查日期：2026-09-12。数据集名称不决定文件格式、图谱或诊断编码；下面按实际发布层级分别处理。

| 数据源 | 能拿到哪类数据 | 获取入口及条件 | 交给本库的文件 |
|---|---|---|---|
| ABIDE I / II | 静息 BOLD、结构像和表型；另有 PCP 预处理影像/ROI 时序 | [官方数据库入口](https://fcon_1000.projects.nitrc.org/indi/abide/databases.html)，NITRC/IDA 等路径可能需账号；[ABIDE I](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html) 和 [ABIDE II](https://fcon_1000.projects.nitrc.org/indi/abide/abide_II.html) 有站点采集信息 | 原始 BOLD/T1 先做预处理；PCP 时序可从表格入口提取；PCP 影像需确认 pipeline、滤波、GSR 与空间 |
| ADHD-200 | BIDS 格式原始 BOLD + T1 + 站点级 JSON；另有预处理发布 | [官方 AWS 下载说明](https://fcon_1000.projects.nitrc.org/indi/adhd200/download_scripts/Download_Instructions_ADHD200.pdf) 指向匿名 `s3://fcp-indi/data/Projects/ADHD200/RawDataBIDS`；[项目页](https://fcon_1000.projects.nitrc.org/indi/adhd200/index.html) 有原有 NITRC 入口和使用说明 | 原始 `*_bold.nii.gz` + `*_T1w.nii.gz` 及继承 JSON，整理/验证 BIDS 后跑 fMRIPrep |
| ADNI | 纵向影像；fMRI 为静息扫描，原始发布可能是 DICOM | [数据申请入口](https://adni.loni.usc.edu/data-samples/adni-data/) 需审批后从 LONI IDA 下载；[FAQ](https://adni.loni.usc.edu/help-faqs/faqs/) 建议从 DICOM 头核查采集时序；[MRI Core 原始 DICOM 说明](https://adni.loni.usc.edu/support/experts-knowledge-base/question/?QID=444) 为历史官方答复，具体下载选项以当前账户内为准 | 完整 DICOM 序列 → dcm2niix → BIDS → fMRIPrep；保留 subject/visit/series 对应，不能把纵向访问当成独立患者 |
| REST-meta-MDD | 官方共享主要为 R-fMRI 指标和中间结果；不等同于原始4D影像开放发布 | [官方共享说明](https://rfmri.org/REST-meta-MDD)；[数据仓库 DOI](https://doi.org/10.57760/sciencedb.o00115.00013)。需签署 DUA，按官方说明索取解压密码与表型 | 若获授权包里含 ROI 时序（如 MAT），显式指定时序变量与图谱顺序；若只有指标图或已算好的连接矩阵，不能当作原始时序重新提取 |

## 首次建议准备

1. 先选一个 ADHD-200 或 ABIDE 受试者的一个静息 run，获取 BOLD、T1 和适用的采集 JSON。
2. 若要尽快验证“影像到连接”，提供同一 run 的已预处理 BOLD、空间说明、混杂表和掩膜。不能把 raw BOLD 标为 preprocessed 以跳过预处理。
3. REST-meta-MDD 先确认实际压缩包内文件、MAT 变量以及 ROI 排序，再决定时序入口或已有矩阵分析入口。
4. ADNI 先确认账号权限及 fMRI 序列，不需要为了验证本库下载完整纵向数据库。

## 本次匿名目录实测

ADHD-200 官方 S3 目录可匿名列举。实测包含：

- `Brown/sub-0026001/ses-1/func/sub-0026001_ses-1_task-rest_run-1_bold.nii.gz`：50,012,139 bytes。
- `Brown/sub-0026001/ses-1/anat/sub-0026001_ses-1_run-1_T1w.nii.gz`：7,263,588 bytes。
- 站点根目录 `dataset_description.json`、`T1w.json`、`participants.tsv`。采集 JSON 可位于站点层级，不能只找与 BOLD 同名的 JSON。

当前库的目录发现器针对 **fMRIPrep derivatives**，不是完整的 BIDS 元数据继承实现。原始 BIDS 的继承规则由 fMRIPrep/BIDS validator 处理。接收预处理单文件时，应提供最终有效的 TR/JSON。

## 数据保存与验证范围

所有真实样本保存在本库的忽略目录 `.work/`，不进入 wheel、源码包或 Git 发布。实际下载和读取结果以 [验证记录](validation.md) 为准。未代签协议或访问 ADNI/MDD 受限数据。
