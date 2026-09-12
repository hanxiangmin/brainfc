from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import math
import numpy as np


class InputError(ValueError):
    """Input data or declared spatial/temporal metadata are not compatible."""


@dataclass(frozen=True)
class Config:
    """Single-run extraction settings, shared by Python, CLI and HTTP.

    Parameters
    ----------
    t_r : float or None, default None
        Repetition time in seconds. Infer from sidecar/recognized header when None;
        conflicting explicit or inferred values raise InputError (rtol=atol=1e-4).
    high_pass, low_pass : float or None, default None
        Cutoffs in Hz. None disables that cutoff. Positive, high_pass < low_pass,
        and each enabled cutoff must be below 1/(2*t_r).
    detrend : bool, default True
        Remove linear trends through Nilearn signal.clean.
    standardize : bool, default True
        Apply sample z-score (ddof=1) to cleaned ROI time series.
    discard : int, default 0
        Remove this many leading original frames before temporal cleaning.
    fd_threshold : float or None, default None
        Censor frames with framewise_displacement > this threshold in mm.
        A missing first FD is also censored when enabled. Requires confounds.
    min_samples : int, default 20
        Minimum retained frames; must be >=3. Not a statistical power criterion.
    method : {'pearson', 'spearman', 'partial'}, default 'pearson'
        Signed Pearson, tied-average-rank Spearman, or Ledoit-Wolf partial correlation.
    data_space, atlas_space : str or None, default None
        Exact named spaces. Images require a declared/inferred data space; when
        an atlas is supplied the names must match. No registration is estimated.
    preprocessed : bool, default False
        Required caller declaration for every image, including CIFTI/GIFTI.
        Does not perform or automatically verify motion correction/registration.
    confound_columns : tuple of str or None, default None
        Explicit nonempty columns to regress. None selects motion6 plus available
        white_matter/csf. Nonsteady-state/FD censoring is considered independently.
    table_header : bool, default True
        Read first non-comment text row as ROI names. Ignored for NPY/NPZ/MAT.
    transpose : bool, default False
        Transpose table input to time x ROI; discards text column names.
    variable : str or None, default None
        NPZ/MAT numeric 2D variable; None requires exactly one eligible variable.

    Notes
    -----
    Frozen dataclass: attributes cannot be reassigned. This is not raw-image
    preprocessing. Filtering and censoring require further input-dependent checks
    inside extract_connectome; construction alone does not validate a dataset."""

    t_r: float | None = None
    high_pass: float | None = None
    low_pass: float | None = None
    detrend: bool = True
    standardize: bool = True
    discard: int = 0
    fd_threshold: float | None = None
    min_samples: int = 20
    method: str = "pearson"
    data_space: str | None = None
    atlas_space: str | None = None
    preprocessed: bool = False
    confound_columns: tuple[str, ...] | None = None
    table_header: bool = True
    transpose: bool = False
    variable: str | None = None

    def __post_init__(self):
        for key in ("t_r", "high_pass", "low_pass", "fd_threshold"):
            value = getattr(self, key)
            if value is not None and (isinstance(value, bool) or not math.isfinite(value) or value <= 0):
                raise InputError(f"{key} must be a positive finite number.")
        if self.high_pass and self.low_pass and self.high_pass >= self.low_pass:
            raise InputError("high_pass must be smaller than low_pass.")
        for key, minimum in (("discard", 0), ("min_samples", 3)):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise InputError(f"{key} must be an integer >= {minimum}.")
        if self.method not in {"pearson", "spearman", "partial"}:
            raise InputError("method must be pearson, spearman or partial (Ledoit-Wolf).")
        for key in ("preprocessed", "detrend", "standardize", "table_header", "transpose"):
            if not isinstance(getattr(self, key), bool):
                raise InputError(f"{key} must be boolean.")
        if self.confound_columns is not None:
            if not self.confound_columns or any(
                not isinstance(c, str) or not c for c in self.confound_columns
            ):
                raise InputError("confound_columns must be a nonempty sequence of column names.")

    def to_dict(self):
        """Return a new dataclass field dictionary.

        Returns
        -------
        dict
            All settings including None values. A tuple of confound columns remains
            a tuple in Python; json.dumps serializes it as an array."""
        return asdict(self)


@dataclass
class Connectome:
    """Result of one run, normally constructed by extract_connectome.

    Attributes
    ----------
    timeseries : numpy.ndarray, shape (T_retained, R)
        Cleaned ROI signals in the same column order as rois.
    connectivity : numpy.ndarray, shape (R, R)
        Symmetric signed coefficients, diagonal 1. No display threshold applied.
    fisher_z : numpy.ndarray, shape (R, R)
        atanh(clip(connectivity, -1+1e-7, 1-1e-7)); diagonal 0.
    rois : list of dict
        ROI ID/name/label/hemisphere/network/abbreviation and coordinates or None.
    sample_indices : numpy.ndarray, shape (T_retained,)
        Zero-based frame positions in the original source, in increasing order.
    qc, provenance : dict
        Quality counts/warnings and resolved configuration, hashes and versions.
    geometry : dict or None
        Display-only mesh and spatial metadata; None without complete coordinates.

    Notes
    -----
    Arrays/dictionaries are mutable. Direct construction does not validate their
    shape or consistency; prefer extract_connectome for a validated result."""

    timeseries: np.ndarray
    connectivity: np.ndarray
    fisher_z: np.ndarray
    rois: list[dict]
    sample_indices: np.ndarray
    qc: dict
    provenance: dict
    geometry: dict | None = field(default=None, repr=False)

    def to_dict(self, *, include_timeseries=False):
        """Return schema-version-1 report data with arrays converted to lists.

        Parameters
        ----------
        include_timeseries : bool, default False
            Include cleaned time series, which may make the payload large.

        Returns
        -------
        dict
            ROI metadata, matrices, frame indices, QC, provenance and geometry.
            Nested metadata dictionaries are shared, not deep-copied."""
        result = {
            "schema_version": 1,
            "rois": self.rois,
            "connectivity": self.connectivity.tolist(),
            "fisher_z": self.fisher_z.tolist(),
            "sample_indices": self.sample_indices.tolist(),
            "qc": self.qc,
            "provenance": self.provenance,
            "geometry": self.geometry,
        }
        if include_timeseries:
            result["timeseries"] = self.timeseries.tolist()
        return result

    def save(self, directory: str | Path, *, figures=True, report=True):
        """Export one complete result to a new directory.

        Parameters
        ----------
        directory : str or pathlib.Path
            New destination; parents are created. Existing destinations are refused.
        figures : bool, default True
            Save matrix PNG/SVG/PDF and eight views when all ROIs have coordinates.
        report : bool, default True
            Save bundled, self-contained interactive report.html.

        Returns
        -------
        pathlib.Path
            Absolute output directory, promoted from a temporary sibling on success.

        Raises
        ------
        FileExistsError
            Destination already exists. Temporary exports are removed on failure.

        Notes
        -----
        Always writes numeric arrays/tables, ROI/frame tables, QC/provenance/result JSON
        and a SHA-256 manifest. Static views use threshold=0.3 and max_edges=200.
        ZIP creation is performed by the web service, not this method."""
        from .export import save_result

        return save_result(self, directory, figures=figures, report=report)

    def plot_matrix(self, path=None):
        """Plot the complete signed connectivity matrix.

        Parameters
        ----------
        path : str, pathlib.Path or None, default None
            Optional image filename; suffix determines format. Parent must exist.

        Returns
        -------
        matplotlib.figure.Figure
            Figure, closed after saving when path is supplied. With None the caller
            owns the figure and should close it after use.

        Notes
        -----
        Uses Agg and a fixed [-1, 1] color range. Saves at 300 dpi. Unlike save/view,
        plotting to an existing filename overwrites that image."""
        from .plotting import plot_matrix

        return plot_matrix(self, path)

    def plot_views(
        self, path=None, *, threshold=0.3, max_edges=200, selection=None, opacity=0.28, theme="paper"
    ):
        """Plot eight fixed anatomical projections using one filtered edge set.

        Parameters
        ----------
        path : str, pathlib.Path or None, default None
            Image filename (may overwrite) or return an unsaved figure.
        threshold : float, default 0.3
            Inclusive absolute coefficient cutoff in [0,1]; exact zero edges excluded.
        max_edges : int, default 200
            Nonnegative cap after filtering; 0 shows nodes without connections.
        selection : dict or None, default None
            {'kind':'node','id':roi_id} selects incident edges. Edge selection uses
            {'kind':'edge','id':'i:j'} with zero-based row indices i < j. IDs are strings.
        opacity : float, default 0.28
            Display control in [0,1]; Matplotlib shell alpha is opacity*0.15.
        theme : {'paper', 'midnight'}, default 'paper'
            Light or dark background.

        Returns
        -------
        matplotlib.figure.Figure
            2x4 orthographic views, closed if saved. Shell is rasterized even in SVG/PDF.

        Raises
        ------
        InputError
            Missing ROI coordinates, invalid selection or invalid display settings.

        Notes
        -----
        Filter by threshold and selection, then stable-sort by descending absolute
        strength and cap. Ties retain upper-triangle row-major order. Original matrices
        are unchanged. Static materials differ from the GUI's WebGL renderer."""
        from .plotting import plot_views

        return plot_views(
            self,
            path,
            threshold=threshold,
            max_edges=max_edges,
            selection=selection,
            opacity=opacity,
            theme=theme,
        )

    def view(self, path="connectome.html", *, open_browser=False):
        """Write a self-contained interactive HTML report.

        Parameters
        ----------
        path : str or pathlib.Path, default 'connectome.html'
            New HTML file. Parent directories are created; overwrite is refused.
        open_browser : bool, default False
            Ask the operating system browser to open the new local file.

        Returns
        -------
        pathlib.Path
            Absolute HTML path. No running web server is needed for the export.

        Raises
        ------
        FileExistsError
            Output already exists.
        InputError
            Bundled frontend assets are missing.

        Notes
        -----
        Embeds matrices and provenance including local input paths. Without coordinates
        the report still shows matrix/QC. Requires browser WebGL for the 3D view."""
        from .export import write_report

        target = write_report(self, path)
        if open_browser:
            import webbrowser

            webbrowser.open(target.as_uri())
        return target

    def to_network(self):
        """Copy this result into the integrated brainfc.network BrainDataset.

        Returns
        -------
        brainfc.network.BrainDataset
            Complete signed connectivity, original ROI order, coordinates, frame
            indices, QC and provenance. No temporal reprocessing is performed.

        Raises
        ------
        brainfc.network.ValidationError
            Invalid matrix, ROI identities/order, or coordinates. All processing
            and display metadata is copied. No separate installation is needed.
        """
        from .network import from_connectome

        return from_connectome(self)

    def analyze_network(self, config=None, progress=None):
        """Analyze graphs/hypergraphs directly from this run's full matrix.

        Parameters
        ----------
        config : brainfc.network.AnalysisConfig, dict or None
            None uses density=0.1 graph and k=5 FC-profile hypergraph defaults.
            Prefer an explicit configuration for reproducible research.
        progress : callable or None
            Optional callback receiving (percent, message).

        Returns
        -------
        brainfc.network.AnalysisResult
            Signed graph edges, native hyperedges, metrics and source metadata.
            The original Connectome is unchanged. Constructed hyperedges are
            descriptive structures, not evidence of higher-order interactions.

        Raises
        ------
        brainfc.network.ValidationError
            Invalid connectome or analysis configuration.
        """
        from .network import analyze

        return analyze(self.to_network(), config, progress=progress)

    def to_hicbrain(self):
        """Compatibility alias for to_network, retained for existing scripts.

        Returns brainfc.network.BrainDataset (also exposed as hicbrain.BrainDataset).
        No separate Hyper-Brain installation is needed; new code should use
        to_network or analyze_network. Validation and copying match to_network.
        """
        return self.to_network()
