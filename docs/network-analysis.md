# 网络与超图分析

从 0.4.0 源码版起，Hyper-Brain 的计算和界面已合入 BrainFC；一次安装即可使用。`brainfc` 完成影像/时序到功能连接，`brainfc.network` 在矩阵上构建图、原生超图、计算指标和组间统计。矩阵、ROI 顺序和信号清理记录通过明确的数据接口连接。

## 在界面中操作

1. 启动 `brainfc serve`，在提取工作台完成一个 run。
2. 点击结果上方的 **进入网络分析**。已有矩阵、ROI 顺序、坐标、参考表面和处理记录自动带入，直接进入方法确认。
3. 选择普通图、超图或两者；确认方法后运行。默认普通图为绝对强度前 10%（保留截断处并列），超图为 FC 连接轮廓 kNN、k=5。这是可调整的演示默认值，不是适用于所有数据集的官方参数。
4. 在结果中切换节点连线、透明包络、矩阵和完整成员表。没有分区表面数据时，“脑区分区表面”不可选；原始图谱切片需要另有已安装的图谱数据。

已有连接矩阵或完成清理的 ROI 时序，可从页面顶部 **网络与超图分析** 直接进入 `/networks/`，上传 CSV/TSV/TXT/1D/NPY/NPZ/MAT。选择数据种类和矩阵含义；MAT/NPZ 有多变量时明确选择。矩阵大小不用于推断图谱。

网络界面处理时序不执行混杂回归、滤波和删帧。需要这些处理时，先在 BrainFC 提取流程中完成，再传入完整矩阵。显示阈值不改变数值矩阵；图构建密度/阈值属于分析参数，应与显示设置区分。

## 从提取结果继续

```python
from brainfc import Config, extract_connectome
from brainfc.network import AnalysisConfig
from brainfc.network.export import export_result

connectome = extract_connectome(
    "roi_timeseries.tsv",
    config=Config(detrend=False, standardize=False),
)
network = connectome.analyze_network(AnalysisConfig(
    graph_method="density", density=0.1,
    hypergraph_method="multiscale", hypergraph_ks=[5, 10],
))
export_result(network, "network-result.zip")
```

`analyze_network` 使用已经计算好的相关矩阵，不重复清理或估计相关性。`connectome.to_network()` 返回独立的 `BrainDataset` 副本，可供高级调用。原始 ROI ID、名称、坐标、保留帧号、QC 和来源保留在 `network.metadata`，可用参考表面也一并保留。

## 已保存的结果或独立矩阵

```python
from brainfc.network import AnalysisConfig, analyze, load_connectome, load_data

data = load_connectome("results/sub-01")  # Connectome.save 输出目录
result = analyze(data, AnalysisConfig(compute_hypergraph=False))

# 独立矩阵有明确含义和行顺序；这里的 ID 应换成自己对应的真实 ROI ID。
data = load_data(
    "connectivity.npy", kind="connectivity", matrix_kind="correlation",
    roi_ids=["roi_a", "roi_b", "roi_c"],
)
result = analyze(data, AnalysisConfig(
    graph_method="weighted", hypergraph_method="custom",
    custom_edges=[{"id": "H1", "members": ["roi_a", "roi_b", "roi_c"]}],
))
```

`matrix_kind="fisher_z"` 显式反变换为相关系数；`covariance` 根据正的方差对角线标准化。不得把 Fisher-z 数值当成相关系数阈值化。

## 图和超图的底层接口

```python
from brainfc.network.graph import build_graph, analyze_graph
from brainfc.network.hypergraph import build_hypergraph, to_payload

graph = build_graph(data.data, roi_ids=data.roi_ids, method="threshold", threshold=0.4)
metrics = analyze_graph(graph)  # NetworkX Graph -> 指标字典
hypergraph = build_hypergraph(data.data, roi_ids=data.roi_ids, method="knn", ks=[5])
payload = to_payload(hypergraph)  # XGI Hypergraph -> 原生超边与稀疏关联矩阵
```

低层 `build_graph`/`build_hypergraph` 的矩阵应已转换为预期权重；含 Fisher-z/协方差时优先通过 `analyze` 的完整校验与转换入口。

| 类别 | 定义 |
|---|---|
| 普通图 | weighted、threshold、density、kNN、最大绝对强度生成森林；保留连接正负号，去除自环和零边。 |
| 路径指标 | 正连接权重对应长度 1/w；不可达点对的效率贡献为 0。完整定义随结果导出。 |
| FC-profile 超图 | 将完整有符号 FC 的对角线置零后计算行间余弦相似度；中心节点加选中的 k 个邻居形成超边，边界并列全部保留。 |
| 自定义/模板超图 | 保留原始 ID 和成员集合；成员相同但 ID 不同的超边仍分别保留。绘制包络不能增加成员。 |
| 范围 | 描述性结构分析；由 FC 构建超边不能证明不可约高阶生理相互作用。 |

详尽方法见[迁入的算法说明](network/methods.md)。

## 组间统计

```python
import pandas as pd
from brainfc.network.statistics import compare_groups

table = pd.read_csv("subject_metrics.csv")
comparison = compare_groups(
    table, group_column="group", subject_column="subject_id",
    feature_columns=["global_efficiency", "mean_clustering"],
    covariates=["age"],
)
```

每行必须是独立且唯一的被试。两组无协变量时用 Welch；有协变量时用 OLS 和 HC3 标准误；输出完整病例排除记录、效应与置信区间，并对指定特征族做 BH-FDR。单被试样例不能运行组间推断。没有诊断预测模型。

## 命令行

```bash
brainfc network results/sub-01 --output network-result.zip
brainfc network connectivity.npy --kind connectivity --matrix-kind correlation --output network.json
brainfc network connectivity.npy --config network-config.json --metadata roi-metadata.json --output network.zip
```

JSON 配置字段来自 `AnalysisConfig`。新命令拒绝覆盖已有输出。Python `export_result` 保留旧 API 行为，会覆盖指定文件；调用者应选择新目标。ZIP 内含完整矩阵、ROI/边/超边成员表、图指标、GraphML、原生超边 JSON、来源和静态报告。来源可含本地输入路径，公开前需要审核。

## HTTP

统一服务器中，提取接口为 `/api/...`，网络分析接口为 `/networks/api/v1/...`。

```python
import time
import requests

base = "http://127.0.0.1:8766"
# extraction_job_id 来自已完成的提取任务。
handoff = requests.post(f"{base}/api/jobs/{extraction_job_id}/network-input")
handoff.raise_for_status()
job = requests.post(f"{base}/networks/api/v1/jobs", json={
    "file_ids": [handoff.json()["file"]["id"]],
    "analysis": {"graph_method": "density", "density": 0.1, "k": 5},
})
job.raise_for_status()
state = job.json()
while state["status"] in {"queued", "running"}:
    time.sleep(0.5)
    response = requests.get(f"{base}/networks/api/v1/jobs/{state['id']}")
    response.raise_for_status()
    state = response.json()
if state["errors"] or state["status"] != "completed":
    raise RuntimeError(state)
response = requests.get(f"{base}/networks/api/v1/results/{state['results'][0]['id']}")
response.raise_for_status()
network = response.json()
```

自动传入的矩阵语义和 ROI 元数据由服务器保存，界面默认值不会覆盖。独立输入用上传接口后提交 `input`/`analysis`，参见运行中的 `/networks/docs`。[完整 HTTP 参考](network-http-reference.md) · [全部 Python API](api-reference.md)。
