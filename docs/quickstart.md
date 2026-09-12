# 安装与上手

## 包名与安装方式

分发名、Python 导入名和命令行均为 `brainfc`。安装 PyPI 已发布版本并启动：

```shell
pip install -U brainfc
brainfc serve
```

可用版本以 [PyPI 项目页](https://pypi.org/project/brainfc/) 为准。如果目标版本尚未发布，或需要源码版，按下方本地方式安装。

## 从源码或本地安装包安装

需要 Python 3.11 或更高版本，Windows / Linux × Python 3.11 / 3.12 已通过 CI 验证。

在解压后的源码根目录执行：

```shell
python -m venv .venv
# Windows
.venv\Scripts\python -m pip install .
.venv\Scripts\brainfc serve
# macOS / Linux：改用 .venv/bin/python 和 .venv/bin/brainfc
```

已激活自己的虚拟环境时，只需 `python -m pip install .` 和 `brainfc serve`。默认安装已包含全部 Python API 和本地网页依赖，不需要另外选择 extras。

本地 wheel 安装：

```shell
python -m pip install "brainfc-0.4.0-py3-none-any.whl"
brainfc --version
brainfc serve
```

wheel 内含网页和离线手册。普通使用不需要 Node.js；首次安装仍需获取 Python 依赖。完全断网安装需提前准备依赖 wheel 或已有依赖环境。

## 第一次运行

服务默认打开 `http://127.0.0.1:8766`。点击“打开真实样例”使用包内经脱敏核查的 rest01 静息态 ROI 时序、混杂变量和脑组织参考掩膜，实际运行去噪、矩阵计算和图像导出。无需下载或手填参数；100 个脑区、TR 2 秒，处理后保留 145 帧。

自己的数据按 **选择数据 → 确认处理方案 → 开始处理** 操作。可一次选择主文件和配套 JSON/confounds/mask。TR、空间及配套文件能明确识别时自动填入；剩余高级参数可展开调整。不能确定空间或预处理状态的影像须先核对。

默认工作目录是 `~/brainfc-workspace`。自定义端口/目录：

```shell
brainfc serve --port 8767 --workspace ./workspace --no-browser
```

同一工作目录只使用一个服务进程。关闭服务可能中断正在处理的任务；下次启动时遗留任务标为 `interrupted`，需要新建任务重新运行。

## 不用界面的最短演示

```shell
brainfc demo --kind rest01 --output ./demo-001
```

`demo-001` 必须不存在。`input/` 是包内真实样例的副本，`result/` 包含数组、CSV/TSV、PNG/SVG/PDF、质控、来源和离线 `report.html`。

详见[真实样例与处理范围](real-example.md)。开发者仍可显式运行 `brainfc demo --kind synthetic --output ./synthetic-demo`。为兼容已有脚本，Python `create_demo()` 和 CLI 省略 `--kind` 时仍返回合成夹具；网页默认使用 rest01。

Python 可执行例子在源码的 `examples/quickstart.py` 和 `examples/roi_timeseries.py`，两者均不需要网络。完整函数说明见 [API 参考](api-reference.md)。

## 原始扫描入口

```shell
brainfc dicom ./dicom --output ./converted
# 加 --run 才执行；需预先安装 dcm2niix。
brainfc preprocess ./bids --output ./derivatives --license ./license.txt --participant 01
# 核对命令后加 --run；需 Docker Linux 容器。
```

转换完成后需要按采集信息组织 BIDS。fMRIPrep 完成并检查报告后，将 `desc-preproc_bold` 输入本库。具体输入责任见 [格式说明](formats.md)，处理边界见 [方法说明](processing.md)。

## 常见错误

| 错误 | 处理方式 |
|---|---|
| `preprocessed=True` | 确认已完成运动校正/空间配准，再设置声明；原始扫描走预处理入口 |
| 空间不一致 | 核对完整模板名称；重采样不能替代配准 |
| TR 冲突 | 比对本次扫描 JSON/影像头，不用数据集参考值覆盖真实扫描 |
| ROI absent / mapping mismatch | 核对真实标签值、覆盖范围、mask 与 ROI 表 |
| 零方差或保留帧过少 | 检查信号、混杂和删帧；库不伪造零相关结果 |
| 输出已存在 | 为本次运行选择新目录/文件，旧结果保留 |
| 没有三维或八视图 | 为所有 ROI 提供同空间 RAS+ mm 坐标；时序表不会猜图谱 |
| 缺少网页依赖 | 在相同 Python 环境重新安装 BrainFC wheel 或源码，并让 pip 安装依赖；默认安装已包含界面 |
