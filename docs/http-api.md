# 本地 HTTP API 使用指南

安装本库后运行 `brainfc serve`。基址默认 `http://127.0.0.1:8766`。浏览器访问 `/docs`（Swagger）、`/redoc` 或 `/reference/`；下载 `/openapi.json` 获取机器可读参数定义。

路径始终是服务所在电脑的文件路径。POST JSON 使用 `Content-Type: application/json`；文件上传使用 multipart。无需先操作界面即可使用 API，不要求填写 `guidance`。

Swagger/ReDoc 默认使用外部 CDN 资源；完全断网时使用随包的 `/reference/` 手册及 `/openapi.json`，它们不依赖外部页面资源。

## 用标准库运行一个完整任务

```python
import json
import time
from urllib.request import Request, urlopen

base = "http://127.0.0.1:8766"
def request(path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as response:
        return json.load(response)

job = request("/api/demo", {})  # 默认：包内已脱敏的真实静息态样例 rest01
deadline = time.monotonic() + 300
while job["status"] in {"queued", "running"}:
    if time.monotonic() > deadline:
        raise TimeoutError("任务仍在服务端执行，可稍后按 id 查询")
    time.sleep(1)
    job = request("/api/jobs/" + job["id"])
if job["status"] != "complete":
    raise RuntimeError(job["message"])
result = request(f"/api/jobs/{job['id']}/files/result.json")
print(result["qc"]["n_rois"])
```

完整可执行客户端：`examples/http_client.py`。轮询超时只结束客户端等待，不取消服务端任务。

## 真实提取请求

```json
{
  "source": "D:/data/sub-01_task-rest_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz",
  "atlas": "D:/atlas/schaefer100.nii.gz",
  "rois": "D:/atlas/schaefer100_rois.tsv",
  "confounds": "D:/data/sub-01_task-rest_desc-confounds_timeseries.tsv",
  "config": {
    "preprocessed": true,
    "data_space": "MNI152NLin6Asym",
    "atlas_space": "MNI152NLin6Asym"
  }
}
```

先 POST 同一请求到 `/api/preflight`，通过后 POST `/api/jobs`。提交任务通常返回 `queued`，线程启动很快时也可能是 `running` 或终态，不能把 200 响应当作计算成功。没有 guidance 的提交不会同步执行所有输入校验，数值/文件错误可在任务中体现为 `failed`。

配置字段与 Python `Config` 一致；HTTP 使用 JSON null / true / false / 列名数组。未知字段返回 422，避免拼写错误被忽略。Pydantic 可以对部分 JSON 数字/布尔类型进行转换，转换后仍运行 Config 的科学条件检查。`overrides` 只有明确提供的键参与覆盖，不补默认值去覆盖自动识别。

## 端点用途与副作用

| 方法 / 路径 | 输入 | 返回 / 行为 |
|---|---|---|
| GET `/api/health` | 无 | status、version、workspace |
| GET `/api/setup` | 无 | 建议的新输出路径、可用 FS_LICENSE；不创建建议目录 |
| GET `/api/presets` | 无 | 数据集和协议来源、采集参数提示 |
| POST `/api/inspect` | `{ "path": "..." }` | 格式/维度/元数据，或目录 runs |
| POST `/api/discover` | 同上，目录 | fMRIPrep run 列表 |
| POST `/api/input-suggestions` | source、可选 overrides | info/config/paths/notes；可按明确空间下载建议图谱到缓存 |
| POST `/api/preflight` | 提取请求；可选 stage | 输入/空间/复核检查，默认 review |
| POST `/api/upload` | multipart file、session | 保存路径和字节数；不覆盖 |
| POST `/api/jobs` | 提取请求 | 入队，返回 JobState |
| POST `/api/demo` | 可选查询 `kind=rest01`（默认）或 `kind=synthetic` | 包内样例入队，返回含 example_kind 的 JobState；真实样例携带原有方法与质控记录 |
| POST `/api/atlas` | name | 图谱下载入队，结束在 job.atlas 取路径 |
| POST `/api/dicom/plan` | source、output | 命令 argv 和两种 shell 表达，无执行 |
| POST `/api/dicom/run` | 同上 | 外部转换入队 |
| POST `/api/preprocess/plan` | bids_dir、output_dir、license_file 等 | 命令和最小 BOLD/T1 库存 |
| POST `/api/preprocess/run` | 同上 | 外部 fMRIPrep 入队 |
| GET `/api/jobs` | 无 | 最后修改排序，最多 100 个任务 |
| GET `/api/jobs/{job_id}` | id | 当前状态 |
| GET `/api/jobs/{job_id}/files/{name}` | id、文件名 | 白名单结果文件，缺少时 404 |
| GET `/api/jobs/{job_id}/views` | id、筛选查询参数 | 生成/缓存当前八视图文件 |

所有请求和响应模型的完整字段、默认值及 schema 见 [自动生成接口参考](http-reference.md)。`input-suggestions` 的 Python 同名函数没有 web 历史复用/下载功能；web 路由只对相同源路径且 SHA-256 一致的历史结果复用空间及指纹仍一致的配套文件。

## 上传

```shell
curl -F "session=123456781234123412341234567890ab" -F "file=@timeseries.tsv" http://127.0.0.1:8766/api/upload
```

session 要求 32–36 个小写十六进制数字/连字符，建议客户端使用 UUID；配套文件使用同一 session 以保留相邻关系。同文件名重复上传返回 409。单文件上限 4 GiB；大文件直接使用本地路径。文件被写入 `workspace/uploads/session/`。

## 八视图参数与下载

`threshold` 默认 0.3，范围 [0,1]；`max_edges` 默认 200，范围 0–10000；`opacity` 默认 0.28，范围 [0,1]；`theme` 为 `paper/midnight`；`format` 为 `svg/pdf/png`。

可选 `selection_kind=node&selection_id=ROI_A`，或 `selection_kind=edge&selection_id=0:1`。边 ID 使用零起始矩阵行列，而非 ROI 名称。选中对象仍须通过显示阈值；未知节点/边返回 422。

可下载文件：`result.zip`、`preprocessing.log`、`result.json`、`qc.json`、`provenance.json`、`manifest.json`、`report.html`、`rois.tsv`、`samples.tsv`、`connectivity.csv/.npy`、`fisher_z.csv/.npy`、`timeseries.tsv/.npy`、`matrix.png/.svg/.pdf`、`eight_views.png/.svg/.pdf`。并非每个任务都有这些文件：atlas/dicom/preprocess 不生成 result.json。

## 状态与错误

JobState 必有 `id/status/message/kind`，按任务类型可能包含 `qc/result_dir/atlas/error_type`。状态为 `queued → running → complete/failed`；服务重启后遗留的活动任务标为 `interrupted`。单 worker，最多 8 个活动/排队任务；没有取消、删除或多用户认证接口。

| 状态码 | 含义 |
|---|---|
| 200 | 请求处理成功或任务已提交，任务结果需看 status |
| 400 | Host 不在本地允许列表等 |
| 403 | Origin 与当前本地服务不一致 |
| 404 | 未知任务/文件或结果尚未生成 |
| 409 | 上传同名文件已存在 |
| 413 | 上传超过限制 |
| 422 | 输入/配置/请求模型不合法 |
| 429 | 队列已满 |
| 500 | 未捕获的服务端异常，例如某些底层文件解析错误 |

业务校验错误为 `{"detail":"说明"}`；请求模型错误的 `detail` 为带 loc/msg/type 的列表。异步计算错误记录在 JobState，而不是把轮询响应改成错误状态码。

服务读取运行账号可访问的本地路径，应保持默认回环绑定。上传和结果属于本地工作目录；atlas/template 首次下载和原始外部工具联网行为见相应函数说明。
