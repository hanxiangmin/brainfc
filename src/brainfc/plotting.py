"""Signed matrix and reproducible anatomical projections from the same result."""

from pathlib import Path
import threading
import numpy as np
from .models import InputError

PLOT_LOCK = threading.RLock()
VIEWS = [
    ("Left", 0, 180),
    ("Right", 0, 0),
    ("Anterior", 0, 90),
    ("Posterior", 0, -90),
    ("Superior", 90, -90),
    ("Inferior", -90, 90),
    ("Left oblique", 28, 135),
    ("Right oblique", 28, 45),
]


def edges_of(result, threshold=0.3, max_edges=200, selection=None):
    """Return display edges as (zero_based_row, zero_based_column, signed_weight).

    result must expose rois and connectivity. threshold (default .3) is inclusive
    in [0,1], but zero edges are omitted. max_edges (default 200) is nonnegative.
    selection is None, {'kind':'node','id':ROI_ID}, or {'kind':'edge','id':'i:j'}.
    Selection and threshold precede a stable descending-absolute-weight sort and
    cap; ties use upper-triangle row-major order. Original arrays are unchanged.
    Invalid settings or unknown selections raise InputError. An empty list is valid."""
    if (
        not np.isfinite(threshold)
        or not 0 <= threshold <= 1
        or not isinstance(max_edges, int)
        or max_edges < 0
    ):
        raise InputError("Display threshold must be in [0,1]; max_edges must be a nonnegative integer.")
    a, b = np.triu_indices(len(result.rois), 1)
    weights = result.connectivity[a, b]
    eligible_mask = (np.abs(weights) >= threshold) & (weights != 0)
    if selection:
        kind, selected = selection.get("kind"), str(selection.get("id"))
        ids = [str(r["roi_id"]) for r in result.rois]
        if kind == "node" and selected in ids:
            index = ids.index(selected)
            eligible_mask &= (a == index) | (b == index)
        elif kind == "edge" and selected in {f"{i}:{j}" for i, j in zip(a, b)}:
            i, j = map(int, selected.split(":"))
            eligible_mask &= (a == i) & (b == j)
        else:
            raise InputError("Unknown selected node or edge.")
    eligible = np.flatnonzero(eligible_mask)
    chosen = eligible[np.argsort(-np.abs(weights[eligible]), kind="stable")[:max_edges]]
    return [(int(a[i]), int(b[i]), float(weights[i])) for i in chosen]


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_matrix(result, path=None):
    """Functional form of Connectome.plot_matrix(result, path=None).

    Accepts a Connectome or compatible result object with connectivity, rois and
    provenance['method']. Returns a matplotlib Figure; optional path is saved at
    300 dpi and may overwrite an existing image. Uses a process-wide rendering lock.
    See Connectome.plot_matrix for display and figure-lifecycle details."""
    with PLOT_LOCK:
        plt = _pyplot()
        fig, ax = plt.subplots(figsize=(7.4, 6.4), layout="constrained")
        im = ax.imshow(result.connectivity, vmin=-1, vmax=1, cmap="RdBu_r", interpolation="nearest")
        ax.set(
            title=f"Functional connectivity · {result.provenance['method']}",
            xlabel="ROI column",
            ylabel="ROI row",
        )
        if len(result.rois) <= 20:
            labels = [r["roi_id"] for r in result.rois]
            ax.set_xticks(range(len(labels)), labels, rotation=90, fontsize=8)
            ax.set_yticks(range(len(labels)), labels, fontsize=8)
        fig.colorbar(im, ax=ax, label="Correlation coefficient", shrink=0.85)
        if path:
            fig.savefig(path, dpi=300)
            plt.close(fig)
        return fig


def plot_views(
    result, path=None, *, threshold=0.3, max_edges=200, selection=None, opacity=0.28, theme="paper"
):
    """Functional form of Connectome.plot_views with identical display options.

    Accepts a Connectome or compatible object with rois/connectivity/qc/geometry.
    Requires coordinates for every ROI. Returns a matplotlib Figure; path saves
    PNG/SVG/PDF (or other Matplotlib format) and closes it, potentially overwriting.
    See Connectome.plot_views for selection ID conventions, limits, opacity,
    theme, rasterized shell and figure-lifecycle details."""
    if not all(r.get("coordinates") is not None for r in result.rois):
        raise InputError("Eight anatomical views require an explicit ROI coordinate table.")
    with PLOT_LOCK:
        from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

        plt = _pyplot()
        xyz = np.array([r["coordinates"] for r in result.rois])
        edges = edges_of(result, threshold, max_edges, selection)
        if not np.isfinite(opacity) or not 0 <= opacity <= 1 or theme not in {"paper", "midnight"}:
            raise InputError("Invalid opacity or theme.")
        shown = set(range(len(xyz))) if not selection else {n for a, b, _ in edges for n in (a, b)}
        if selection and selection["kind"] == "node":
            shown.add(next(i for i, r in enumerate(result.rois) if str(r["roi_id"]) == selection["id"]))
        shown = sorted(shown)
        dark = theme == "midnight"
        background, foreground = ("#111d2e", "#deebf7") if dark else ("#f8fafc", "#23364b")
        fig = plt.figure(figsize=(16, 8.8), layout="constrained")
        fig.set_facecolor(background)
        mesh = (result.geometry or {}).get("brain", {})
        vertices = np.array(mesh.get("positions", [])).reshape(-1, 3)
        faces = np.array(mesh.get("indices", []), dtype=int).reshape(-1, 3)
        allpts = np.vstack([xyz, vertices]) if len(vertices) else xyz
        center = (allpts.min(axis=0) + allpts.max(axis=0)) / 2
        radius = max(np.ptp(allpts, axis=0)) * 0.55
        for i, (name, elevation, azimuth) in enumerate(VIEWS):
            ax = fig.add_subplot(2, 4, i + 1, projection="3d", proj_type="ortho")
            ax.set_facecolor(background)
            if len(faces):
                surface = Poly3DCollection(
                    vertices[faces],
                    facecolors="#8da9b5",
                    edgecolors="none",
                    alpha=opacity * 0.15,
                    rasterized=True,
                )
                ax.add_collection3d(surface)
            if edges:
                ax.add_collection3d(
                    Line3DCollection(
                        [[xyz[a], xyz[b]] for a, b, _ in edges],
                        colors=["#c46c38" if w > 0 else "#397ab8" for _, _, w in edges],
                        linewidths=[0.45 + abs(w) * 1.1 for _, _, w in edges],
                        alpha=0.72,
                    )
                )
            ax.scatter(
                *xyz[shown].T,
                c=[result.rois[j].get("color") or ("#307e90" if xyz[j, 0] < 0 else "#997abd") for j in shown],
                s=24,
                depthshade=True,
                edgecolors="white",
                linewidths=0.3,
            )
            for k, setter in enumerate([ax.set_xlim, ax.set_ylim, ax.set_zlim]):
                setter(center[k] - radius, center[k] + radius)
            ax.set_box_aspect((1, 1, 1))
            ax.view_init(elev=elevation, azim=azimuth, roll=0)
            ax.set_title(name, fontsize=11, pad=0, color=foreground)
            ax.set_axis_off()
        fig.suptitle(
            f"Eight anatomical views | {result.qc['n_rois']} ROIs | |r| ≥ {threshold:g} | {len(edges)} displayed edges",
            fontsize=14,
            color=foreground,
        )
        note = (
            "Orange: positive · Blue: negative · Same edges in all views; full matrix remains unthresholded"
        )
        fig.text(0.5, 0.025, note, ha="center", fontsize=9, color="#425466")
        if path:
            fig.savefig(Path(path), dpi=300)
            plt.close(fig)
        return fig
