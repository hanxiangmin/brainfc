"""Generate API/CLI/OpenAPI reference and a bundled offline manual from source.

Run from a development installation: python scripts/generate_reference.py.
Use --check in CI to reject stale generated API contracts.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import fields
import html
import importlib
import inspect
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MODULES = [
    "models",
    "pipeline",
    "io",
    "imaging",
    "atlases",
    "plotting",
    "export",
    "demo",
    "preprocessing",
    "presets",
    "workflow",
    "cli",
    "web.app",
    "network.types", "network.bridge", "network.analysis", "network.io",
    "network.connectivity", "network.graph", "network.hypergraph",
    "network.statistics", "network.export", "network.visualization",
    "network.atlas", "network.atlas_sources", "network.view", "network.cli",
]
PAGES = [
    ("index", "文档导航"),
    ("quickstart", "安装与上手"),
    ("real-example", "真实静息态样例"),
    ("privacy-review", "样例隐私核查"),
    ("uih-metadata", "UIH 参数核验"),
    ("python-api", "Python 使用指南"),
    ("network-analysis", "网络与超图分析"),
    ("hyper-brain-migration", "Hyper-Brain 合并说明"),
    ("network-http-reference", "网络分析 HTTP 接口"),
    ("api-reference", "全部函数与参数"),
    ("processing", "处理顺序与方法"),
    ("formats", "输入格式与空间"),
    ("outputs", "结果文件与质控"),
    ("http-api", "HTTP 使用指南"),
    ("http-reference", "HTTP 完整接口"),
    ("cli-reference", "命令行完整参数"),
    ("presets-and-workflow", "数据集预设"),
    ("release", "开源与发布"),
    ("validation-v0.4.0", "本次验证范围"),
]


def _write(path, text, check):
    text = text.rstrip() + "\n"
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            raise SystemExit(f"Stale generated file: {path.relative_to(ROOT)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def generate(check=False):
    from brainfc import Config, __version__
    from brainfc.cli import _parser
    from brainfc.web.app import create_app

    inventory = []
    out = [
        f"# API 完整参考 · {__version__}",
        "由实际 Python 签名和源码 docstring 自动生成。修改接口后运行 `python scripts/generate_reference.py`；CI 检查文档是否同步。",
        "推荐入口见 [Python 使用指南](python-api.md)。底层函数面向高级用户，完整校验仍由 `extract_connectome` 执行。",
        "## Config 默认值",
        "| 字段 | 实际默认值 |",
        "|---|---|",
    ]
    out[-2:] = ["\n".join(out[-2:] + [f"| `{f.name}` | `{f.default!r}` |" for f in fields(Config)])]
    count = 0
    for name in MODULES:
        module = importlib.import_module("brainfc." + name)
        source = Path(module.__file__)
        tree = ast.parse(source.read_text(encoding="utf-8"))
        out.append(f"## brainfc.{name}")
        for node in tree.body:
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            targets = [(node.name, getattr(module, node.name), node)]
            if isinstance(node, ast.ClassDef):
                targets += [
                    (node.name + "." + child.name, getattr(getattr(module, node.name), child.name), child)
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not child.name.startswith("_")
                ]
            for local_name, obj, item in targets:
                public = not local_name.startswith("_")
                documented = public or local_name == "_confounds"
                doc = inspect.getdoc(obj) or ""
                signature = ""
                if not isinstance(obj, property) and not (inspect.isclass(obj) and issubclass(obj, Exception)):
                    signature = str(inspect.signature(obj))
                record = {
                    "name": f"brainfc.{name}.{local_name}",
                    "signature": signature,
                    "public": public,
                    "documented": documented,
                    "source": source.relative_to(ROOT).as_posix(),
                    "line": item.lineno,
                }
                inventory.append(record)
                if not documented:
                    continue
                if not doc:
                    raise SystemExit(f"Missing API documentation: {record['name']}")
                count += 1
                out.extend(
                    [
                        f"### {local_name}",
                        f"```python\n{local_name}{signature}\n```",
                        f"```text\n{doc}\n```",
                        f"源码：`{record['source']}`，第 {item.lineno} 行。",
                    ]
                )
    out.insert(
        2,
        f"共 **{count} 个类、函数和方法条目**；包括所有模块公开处理函数及 `_confounds` 的行为契约。HTTP 数据模型另见 [HTTP 完整接口](http-reference.md)。",
    )
    _write(DOCS / "api-reference.md", "\n\n".join(out), check)
    _write(DOCS / "api-inventory.json", json.dumps(inventory, ensure_ascii=False, indent=2), check)

    parser = _parser()
    cli = [
        f"# 命令行完整参数 · {__version__}",
        "由 argparse 自动生成，与 `brainfc --help` 一致。`python -m brainfc` 与安装后的 `brainfc` 入口等价。",
        "详细使用例子见 [安装与上手](quickstart.md)；退出码：成功 0，参数/常见输入错误 2，其他未捕获错误非零。",
        "```text\n" + parser.format_help().rstrip() + "\n```",
    ]
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, command in action.choices.items():
                cli.extend([f"## {name}", "```text\n" + command.format_help().rstrip() + "\n```"])
    cli.append(
        "`extract` 中显式的 `--tr` / 空间 / `--preprocessed` 覆盖 JSON 的同名字段；其余处理选项通过 `--config` 提供。`dicom` 与 `preprocess` 默认只显示命令，`--run` 才执行。`batch` 每个 run 单独处理，失败保留在 `batch.json` 中；已有输出目录拒绝覆盖。"
    )
    _write(DOCS / "cli-reference.md", "\n\n".join(cli), check)

    with tempfile.TemporaryDirectory() as directory:
        app = create_app(directory)
        schema = app.openapi()
    _write(DOCS / "openapi.json", json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True), check)
    http = [
        f"# HTTP 完整接口 · {__version__}",
        "从实际 FastAPI OpenAPI 生成。运行服务后可在 `/docs`、`/redoc` 查看交互说明；机器可读定义在 `/openapi.json`，离线副本为 [openapi.json](openapi.json)。",
        "响应与轮询示例见 [HTTP 使用指南](http-api.md)。",
    ]
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            http.extend(
                [
                    f"## {method.upper()} {path}",
                    operation.get("summary", ""),
                    "```json\n"
                    + json.dumps(
                        {
                            k: v
                            for k, v in operation.items()
                            if k in {"parameters", "requestBody", "responses"}
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n```",
                ]
            )
    http.append("## 请求与响应数据模型")
    for name, model in schema.get("components", {}).get("schemas", {}).items():
        http.extend([f"### {name}", "```json\n" + json.dumps(model, ensure_ascii=False, indent=2) + "\n```"])
    _write(DOCS / "http-reference.md", "\n\n".join(http), check)
    from brainfc.network.web.app import create_app as create_network_app
    with tempfile.TemporaryDirectory() as directory:
        network_schema = create_network_app(directory).openapi()
    _write(DOCS / "network-openapi.json", json.dumps(network_schema, ensure_ascii=False, indent=2, sort_keys=True), check)
    network_http = ["# 网络分析 HTTP 完整接口", "运行 `brainfc serve` 后，以下路由位于 `/networks` 下。交互说明在 `/networks/docs`，实际 OpenAPI 在 `/networks/openapi.json`。",
                    "提取结果转入接口 `POST /api/jobs/{job_id}/network-input` 见主 HTTP 参考。矩阵上传、任务、图谱、统计请求示例见 [网络分析指南](network-analysis.md)。以下签名来自实际网络服务的 OpenAPI。",
                    "机器可读定义：[network-openapi.json](network-openapi.json)。"]
    for path, operations in network_schema['paths'].items():
        for method, operation in operations.items():
            if method not in {'get', 'post', 'put', 'delete', 'patch'}:
                continue
            network_http.extend([f"## {method.upper()} /networks{path}",
                                 "```json\n"+json.dumps(operation, ensure_ascii=False, indent=2)+"\n```"])
    network_http.extend(["## 数据模型", "```json\n"+json.dumps(network_schema.get('components', {}), ensure_ascii=False, indent=2)+"\n```"])
    _write(DOCS / 'network-http-reference.md', '\n\n'.join(network_http), check)
    return count, len(schema["paths"]) + len(network_schema['paths'])


def site(check=False):
    import markdown

    destination = ROOT / "src/brainfc/web/static/reference"
    # Also render linked legacy evidence/dataset pages so the offline guide is self-contained.
    pages = list(PAGES) + [(p.stem, p.stem) for p in DOCS.glob("*.md") if p.stem not in dict(PAGES)]
    pages += [(p.relative_to(DOCS).with_suffix('').as_posix(), p.stem) for p in (DOCS / "network").glob("*.md")]
    style = "body{margin:0;background:#f5f8fa;color:#243849;font:16px/1.7 system-ui,sans-serif}aside{position:fixed;width:225px;inset:0 auto 0 0;background:#005f7d;padding:26px 20px;overflow:auto}aside a{display:block;color:#dbecef;text-decoration:none;padding:7px 0}aside b{color:#fff}main{margin-left:265px;max-width:1080px;padding:36px 48px}a{color:#007da3}h1,h2,h3{line-height:1.35;scroll-margin:24px}h2{margin-top:42px;border-bottom:1px solid #d1dce2;padding-bottom:12px}pre{overflow:auto;background:#eaf0f3;padding:18px;border-radius:8px;font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}code{font-size:.9em}table{border-collapse:collapse;width:100%;display:block;overflow:auto}th,td{border:1px solid #cdd9df;padding:9px 12px;vertical-align:top}img{max-width:100%}blockquote{border-left:3px solid #0096c3;margin:20px 0;padding-left:18px} @media(max-width:850px){aside{position:static;width:auto}aside a{display:inline-block;margin-right:15px}main{margin:0;padding:20px}}"
    # Long qualified Python names must wrap with every platform's system font.
    style += "body{overflow-wrap:anywhere}main{min-width:0}pre,table{max-width:100%;box-sizing:border-box}"
    for name, title in pages:
        prefix = "../" * name.count("/")
        links = "".join(f'<a href="{prefix}{key}.html">{label}</a>' for key, label in PAGES)
        source = DOCS / (name + ".md")
        body = markdown.markdown(
            source.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "toc"]
        )
        body = re.sub(
            r'href="([^"#]+)\.md(#[^"]*)?"', lambda m: 'href="' + m[1] + ".html" + (m[2] or "") + '"', body
        )
        page = f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>{html.escape(title)} · BrainFC</title><style>{style}</style><aside><b>BrainFC · 开发与使用文档</b>{links}</aside><main>{body}</main></html>'
        _write(destination / (name + ".html"), page, check)
    for filename in ("openapi.json", "network-openapi.json", "api-inventory.json", "interface-preview.png", "eight-views-v02.png", "network/upstream.json"):
        source = DOCS / filename
        target = destination / filename
        if check:
            if not target.is_file() or target.read_bytes() != source.read_bytes():
                raise SystemExit(f"Stale manual asset: {filename}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count, paths = generate(args.check)
    site(args.check)
    print(f"Reference verified: {count} API entries, {paths} HTTP paths, {len(PAGES)} main manual pages.")
