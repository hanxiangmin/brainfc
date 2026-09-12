# 验证记录 · 0.1.0

日期：2026-09-12；Windows，Python 3.12.14。只记录实际完成的验证。

## 数值、格式和边界

`pytest`：**34 项通过**。覆盖：

- 有已知信号的 NIfTI，逐 ROI 均值与独立 NumPy 计算一致；非连续标签 3/17/91 及乱序 ROI 表仍保持正确映射。
- Pearson 与参考计算一致；Spearman / Ledoit–Wolf 偏相关的对称性、有限值、对角线和有符号结果。
- 混杂回归删除共同干扰、FD 删帧保留原始时间索引、滤波与删帧组合。
- 未预处理影像、空间冲突、TR 冲突、缺失脑区、非有限数据和零方差 ROI 被拒绝。
- NIfTI `.nii/.nii.gz`、NIfTI pair `.hdr/.img`、MGZ；CIFTI dense / parcel；GIFTI 配对功能/标签文件。
- CSV、TSV、TXT、1D、NPY、NPZ、MAT 的样本与相关计算；多变量选择；扩展名为 CSV 但实际 tab 分隔的 ADHD 混杂文件。
- CIFTI grayordinate 轴不一致被拒绝；表格缺坐标仅输出矩阵。
- Web 上传不覆盖已有文件、本机 Host/Origin 限制、导出避免覆盖、离线报告转义标签文本。

AFNI HEAD/BRIK 与旧式 Analyze 由 NiBabel 后端读取，**本次没有真实文件实测**，不纳入上述已验证列表。GIFTI 检查顶点数；同一表面/半球/顺序依赖调用者提供正确配对文件。

`ruff check src tests examples` 通过。前端 TypeScript 检查与 Vite 构建通过。第三方库存在弃用警告，不影响本次测试；依赖快照见 requirements-tested-windows-py312.txt。

## 实际浏览器

应用内 Browser 初始化被运行环境阻止（`node:process` 导入限制）。随后使用**独立 Playwright + 本机 Chrome 的 headless 实例**，不接入用户浏览器配置或登录态。

实际完成：点击合成演示启动后台提取、WebGL 场景、相机切换、深浅主题、PNG 下载、矩阵页、八视图加载、质控页、ZIP 下载、本地 file:// HTML 离线展示。未出现页面脚本错误。八视图 PNG 与界面截图已人工查看。

证据文件在 `.work/browser-qa/`：`validation.json`、界面截图、PNG 和 ZIP。其中发现并修复了后台任务完成与界面异步结果加载之间的竞态。

另对 Schaefer 100 场景、带 job 参数的结果直达链接和390 px移动宽度进行检查，无页面脚本错误或水平溢出。截图见 `interface-preview.png`；独立证据见 `standard-atlas.json`。

## 真实数据

### ADHD-200 原始样本：已下载并读取，未运行空间预处理

官方匿名 S3 下载 `Brown/sub-0026001` 的一个 BOLD、一个 T1 和适用 JSON：

- BOLD：`64 × 64 × 35 × 251`，3 mm，TR=2 s，LAS 方向。
- T1：`160 × 240 × 256`，1 mm，LAS 方向。
- 下载清单、文件 SHA-256 与头信息在 `.work/public-data/adhd200-raw/`。
- 官方 JSON 的 NumberofMeasurements=256，而下载 BOLD 有251帧；保持原文件，未据此补造帧。

当前系统有 Docker 客户端，但 Docker Linux engine 未运行，dcm2niix 也未安装。故本次**没有完成 DICOM 转换或完整 fMRIPrep 实跑**。已实现可检查、可执行的外部命令适配器；命令参数与目录边界由测试检查。

### ADHD 预处理影像：完成真实文件到 FC 的技术验证

通过 Nilearn 官方 `fetch_adhd(n_subjects=1)` 下载 NITRC 预处理样本 `0010042`，影像为 `61 × 73 × 61 × 176`，TR=2 s。

由于旧发布没有在现有说明中明确区分具体 MNI 模板版本，本次在影像自身网格定义**三个人工测试分区**，验证体素读取、均值提取、motion6 + WM/CSF 回归、矩阵与报告导出。176 帧全部保留。该结果是程序验证，**不是标准解剖网络结果或疾病分析**。

脚本：`examples/validate_real_adhd.py`。记录和结果在 `.work/real-adhd-validation/`。没有将该样本未经确认地绑定到 AAL/Schaefer 研究图谱。

## 标准图谱演示

成功下载并解析 Schaefer 100 / Yeo7 / 2 mm 图谱。生成该真实图谱上的合成 BOLD，并在4 mm网格提取120时间点、100脑区；使用现有 Hyper-Brain 缓存里匹配的 MNI152NLin6Asym 参考脑。八视图、完整矩阵和可旋转三维均已生成。

演示影像与信号是合成数据，不能作为人群研究结果。图谱、T1参考和坐标来自已标明的资源。脚本：`examples/prepare_atlas_demo.py`。

## 安装与发布

库在独立 `.venv` 中通过 pip 安装，依赖安装时默认 PyPI 文件源出现 TLS 错误，改用清华 PyPI 镜像后完成。此环境网络问题未通过关闭证书校验处理。

构建 wheel / sdist 并执行 twine 元数据检查；再从 wheel 安装到独立目标目录，确认导入与静态资源不依赖父仓库。实际文件清单与 SHA-256 见 `dist/build-manifest.json`。

本次未上传 PyPI、GitHub 或任何外部发布站点；原项目已跟踪文件无修改。
