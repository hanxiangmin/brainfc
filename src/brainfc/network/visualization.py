"""Offline, publication-exportable views of the same computed results."""
from __future__ import annotations

from pathlib import Path
import threading

import numpy as np

_PLOT_LOCK = threading.RLock()


def plot_result(result, path=None, format=None):
    """Render FC, a signed graph and native incidence. Returns a Matplotlib figure.

    For readability the network panel shows the 200 strongest edges, and
    incidence shows the first 80 hyperedges. All numerical exports are complete.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    with _PLOT_LOCK:
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), layout="constrained")
        fig.set_facecolor("#f7f9fb")
        n = len(result.roi_ids)
        index = {roi: i for i, roi in enumerate(result.roi_ids)}
        im = axes[0].imshow(result.connectivity, cmap="RdBu_r", vmin=-1, vmax=1,
                            interpolation="nearest", rasterized=True)
        axes[0].set(title="Functional connectivity", xlabel="ROI column", ylabel="ROI row")
        fig.colorbar(im, ax=axes[0], shrink=.72, label="Correlation")
        saved = {node["id"]: (node["x"], node["y"])
                 for node in result.layouts.get("graph_2d", {}).get("nodes", [])}
        if all(roi in saved for roi in result.roi_ids):
            xy = np.array([saved[roi] for roi in result.roi_ids])
        else:
            theta = np.linspace(0, 2 * np.pi, n, endpoint=False) - np.pi / 2
            xy = np.column_stack((np.cos(theta), np.sin(theta)))
        edges = sorted(result.graph.get("edges", []), key=lambda edge: -abs(edge["weight"]))[:200]
        segments, colors = [], []
        for edge in edges:
            segments.append([xy[index[edge["source"]]], xy[index[edge["target"]]]])
            colors.append("#b95e69" if edge["weight"] < 0 else "#187f86")
        if segments:
            axes[1].add_collection(LineCollection(segments, colors=colors, linewidths=.65, alpha=.4))
        axes[1].scatter(xy[:, 0], xy[:, 1], s=max(3, 350/n), color="#163e53", zorder=3)
        axes[1].set(xlim=(-1.15, 1.15), ylim=(1.15, -1.15), aspect="equal",
                    title="Signed graph · strongest 200 edges")
        axes[1].axis("off")
        hedges = result.hypergraph.get("edges", [])[:80]
        if hedges:
            incidence = np.zeros((n, len(hedges)))
            for j, edge in enumerate(hedges):
                for roi in edge["members"]:
                    incidence[index[roi], j] = 1
            axes[2].imshow(incidence, cmap="Blues", interpolation="nearest", aspect="auto", rasterized=True)
            axes[2].set(xlabel="Hyperedge", ylabel="ROI row")
        else:
            axes[2].text(.5, .5, "No hyperedges", ha="center", transform=axes[2].transAxes)
            axes[2].axis("off")
        axes[2].set_title("Native incidence · first 80 hyperedges")
        fig.suptitle(f"Hyper-Brain | {n} ROIs | {result.metadata.get('source_name', 'local dataset')}", fontsize=13)
        if path is not None:
            destination = Path(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(destination, format=format, dpi=180, metadata={"Creator": "Hyper-Brain"} if (format or destination.suffix[1:]) in {"pdf", "svg"} else None)
            plt.close(fig)
        return fig


def write_html(result, path):
    """Write a self-contained HTML report with inline images and exact parameters."""
    from .export import export_result
    return export_result(result, path, format="html")
