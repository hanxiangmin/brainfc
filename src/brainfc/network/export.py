"""Self-contained reports and interoperable graph / hypergraph artifacts."""
from __future__ import annotations

import base64
import csv
import html
import io
import json
from pathlib import Path
import tempfile
import zipfile

import networkx as nx

from .types import ValidationError


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def _write_rows(path, rows):
    rows = list(rows)
    columns = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["id"]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            clean = {}
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                # Spreadsheet formula escaping does not affect the JSON source of truth.
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                    value = "'" + value
                clean[key] = value
            writer.writerow(clean)


def _csv_bundle(result, target):
    payload = result.to_dict()
    def safe_label(value):
        return "'" + value if value.startswith(("=", "+", "-", "@")) else value
    with (target / "connectivity.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["roi_id"] + [safe_label(roi) for roi in result.roi_ids])
        for roi, row in zip(result.roi_ids, result.connectivity):
            writer.writerow([safe_label(roi)] + row.tolist())
    _write_rows(target / "rois.csv", [{"roi_id": roi, "label": label,
        **({"x": result.coordinates[i, 0], "y": result.coordinates[i, 1], "z": result.coordinates[i, 2]}
           if result.coordinates is not None else {})}
        for i, (roi, label) in enumerate(zip(result.roi_ids, result.labels))])
    _write_rows(target / "graph_edges.csv", payload["graph"]["edges"])
    _write_rows(target / "graph_nodes.csv", payload["graph"]["metrics"]["nodes"])
    _write_rows(target / "hypergraph_nodes.csv", payload["hypergraph"]["metrics"]["nodes"])
    _write_rows(target / "hyperedge_members.csv", [{"hyperedge_id": edge["id"],
        "hyperedge_id_type": "integer" if isinstance(edge["id"], int) else "string", "roi_id": roi,
        "weight": edge.get("weight", 1)} for edge in payload["hypergraph"]["edges"] for roi in edge["members"]])
    _write_rows(target / "layout_coordinates.csv", [{"layout": name, "coordinate_space": "display",
        "units": layout.get("units", "unitless"), **node}
        for name, layout in payload.get("layouts", {}).items() for node in layout.get("nodes", [])])
    _write_rows(target / "global_metrics.csv", [{"structure": name, "metric": key, "value": value}
        for name in ("graph", "hypergraph") for key, value in payload[name]["metrics"]["global"].items()])
    (target / "provenance.json").write_text(_json({"metadata": payload["metadata"], "config": payload["config"],
        "warnings": payload["warnings"], "version": result.version}), encoding="utf-8")


def _html_report(result):
    from .visualization import plot_result, _PLOT_LOCK
    import matplotlib.pyplot as plt
    with _PLOT_LOCK:
        fig = plot_result(result)
        image = io.BytesIO()
        fig.savefig(image, format="png", dpi=140)
        plt.close(fig)
    payload = result.to_dict()
    metrics = "".join(f"<tr><td>{name}</td><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
        for name in ("graph", "hypergraph") for key, value in payload[name]["metrics"]["global"].items())
    warnings = "".join(f"<li>{html.escape(item)}</li>" for item in payload["warnings"])
    mapping = "".join(f"<tr><td>{i+1}</td><td>{html.escape(roi)}</td><td>{html.escape(label)}</td></tr>"
        for i, (roi, label) in enumerate(zip(result.roi_ids, result.labels)))
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>BrainFC network report</title>
<style>body{{font:15px/1.65 system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 24px;color:#173b4c;background:#f7f9fb}}h1{{font-size:32px}}h2{{margin-top:32px}}img{{width:100%;background:white;border-radius:12px}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{padding:9px 14px;text-align:left;border-bottom:1px solid #e0e7ec}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0f4;padding:20px}}small{{color:#536b79}}</style>
<h1>BrainFC · 脑网络结构报告</h1><p>{html.escape(result.metadata.get('source_name', 'local dataset'))} · {len(result.roi_ids)} ROI · v{result.version}</p>
<small>描述性结构分析。构建的超边不等同于不可约高阶交互；本报告不提供疾病诊断。图像索引与下方 ROI 表对应。</small>
<img alt="Connectivity, signed graph and native hyperedge incidence" src="data:image/png;base64,{base64.b64encode(image.getvalue()).decode()}">
<h2>全局指标</h2><table><tr><th>结构</th><th>指标</th><th>值</th></tr>{metrics}</table>
<h2>输入检查</h2><ul>{warnings or '<li>数值和维度检查通过。</li>'}</ul>
<h2>ROI 对应</h2><table><tr><th>图中索引</th><th>ROI ID</th><th>名称</th></tr>{mapping}</table>
<h2>方法与来源</h2><pre>{html.escape(_json({'config': payload['config'], 'metadata': payload['metadata']}))}</pre></html>'''


def export_result(result, path, format=None):
    """Export json, html, svg, png, pdf, graphml, hyperedges JSON or a complete ZIP.

    ``csv`` exports a ZIP containing complete labeled tables (multiple tables).
    Original source files/time series are not bundled, but processing metadata
    can contain local input paths (including those transferred from BrainFC).
    Review exported provenance before public sharing. The chosen destination
    is overwritten if it already exists; returns pathlib.Path.
    """
    path = Path(path)
    fmt = format or path.suffix.lstrip(".").lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path.write_text(_json(result.to_dict()), encoding="utf-8")
    elif fmt == "hyperedges":
        path.write_text(_json({"roi_ids": result.roi_ids, "edges": result.to_dict()["hypergraph"]["edges"]}), encoding="utf-8")
    elif fmt == "html":
        path.write_text(_html_report(result), encoding="utf-8")
    elif fmt in {"svg", "png", "pdf"}:
        from .visualization import plot_result
        plot_result(result, path, format=fmt)
    elif fmt == "graphml":
        graph = nx.Graph()
        graph.add_nodes_from((roi, {"label": label}) for roi, label in zip(result.roi_ids, result.labels))
        graph.add_weighted_edges_from((e["source"], e["target"], e["weight"]) for e in result.graph["edges"])
        nx.write_graphml(graph, path)
    elif fmt in {"zip", "csv"}:
        with tempfile.TemporaryDirectory(prefix="hicbrain-export-") as folder:
            target = Path(folder)
            _csv_bundle(result, target)
            if fmt == "zip":
                export_result(result, target / "result.json")
                export_result(result, target / "report.html")
                export_result(result, target / "network.graphml")
                export_result(result, target / "hyperedges.json", format="hyperedges")
                for image_format in ("svg", "png", "pdf"):
                    export_result(result, target / f"figure.{image_format}")
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for item in sorted(target.iterdir()):
                    archive.write(item, arcname=item.name)
    else:
        raise ValidationError(f"Unsupported export format: {fmt}")
    return path
