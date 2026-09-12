# API 完整参考 · 0.3.0

由实际 Python 签名和源码 docstring 自动生成。修改接口后运行 `python scripts/generate_reference.py`；CI 检查文档是否同步。

共 **48 个类、函数和方法条目**；包括所有模块公开处理函数及 `_confounds` 的行为契约。HTTP 数据模型另见 [HTTP 完整接口](http-reference.md)。

推荐入口见 [Python 使用指南](python-api.md)。底层函数面向高级用户，完整校验仍由 `extract_connectome` 执行。

## Config 默认值

| 字段 | 实际默认值 |
|---|---|
| `t_r` | `None` |
| `high_pass` | `None` |
| `low_pass` | `None` |
| `detrend` | `True` |
| `standardize` | `True` |
| `discard` | `0` |
| `fd_threshold` | `None` |
| `min_samples` | `20` |
| `method` | `'pearson'` |
| `data_space` | `None` |
| `atlas_space` | `None` |
| `preprocessed` | `False` |
| `confound_columns` | `None` |
| `table_header` | `True` |
| `transpose` | `False` |
| `variable` | `None` |

## brainfc.models

### InputError

```python
InputError
```

```text
Input data or declared spatial/temporal metadata are not compatible.
```

源码：`src/brainfc/models.py`，第 9 行。

### Config

```python
Config(t_r: 'float | None' = None, high_pass: 'float | None' = None, low_pass: 'float | None' = None, detrend: 'bool' = True, standardize: 'bool' = True, discard: 'int' = 0, fd_threshold: 'float | None' = None, min_samples: 'int' = 20, method: 'str' = 'pearson', data_space: 'str | None' = None, atlas_space: 'str | None' = None, preprocessed: 'bool' = False, confound_columns: 'tuple[str, ...] | None' = None, table_header: 'bool' = True, transpose: 'bool' = False, variable: 'str | None' = None) -> None
```

```text
Single-run extraction settings, shared by Python, CLI and HTTP.

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
inside extract_connectome; construction alone does not validate a dataset.
```

源码：`src/brainfc/models.py`，第 14 行。

### Config.to_dict

```python
Config.to_dict(self)
```

```text
Return a new dataclass field dictionary.

Returns
-------
dict
    All settings including None values. A tuple of confound columns remains
    a tuple in Python; json.dumps serializes it as an array.
```

源码：`src/brainfc/models.py`，第 99 行。

### Connectome

```python
Connectome(timeseries: 'np.ndarray', connectivity: 'np.ndarray', fisher_z: 'np.ndarray', rois: 'list[dict]', sample_indices: 'np.ndarray', qc: 'dict', provenance: 'dict', geometry: 'dict | None' = None) -> None
```

```text
Result of one run, normally constructed by extract_connectome.

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
shape or consistency; prefer extract_connectome for a validated result.
```

源码：`src/brainfc/models.py`，第 111 行。

### Connectome.to_dict

```python
Connectome.to_dict(self, *, include_timeseries=False)
```

```text
Return schema-version-1 report data with arrays converted to lists.

Parameters
----------
include_timeseries : bool, default False
    Include cleaned time series, which may make the payload large.

Returns
-------
dict
    ROI metadata, matrices, frame indices, QC, provenance and geometry.
    Nested metadata dictionaries are shared, not deep-copied.
```

源码：`src/brainfc/models.py`，第 145 行。

### Connectome.save

```python
Connectome.save(self, directory: 'str | Path', *, figures=True, report=True)
```

```text
Export one complete result to a new directory.

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
ZIP creation is performed by the web service, not this method.
```

源码：`src/brainfc/models.py`，第 172 行。

### Connectome.plot_matrix

```python
Connectome.plot_matrix(self, path=None)
```

```text
Plot the complete signed connectivity matrix.

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
plotting to an existing filename overwrites that image.
```

源码：`src/brainfc/models.py`，第 203 行。

### Connectome.plot_views

```python
Connectome.plot_views(self, path=None, *, threshold=0.3, max_edges=200, selection=None, opacity=0.28, theme='paper')
```

```text
Plot eight fixed anatomical projections using one filtered edge set.

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
are unchanged. Static materials differ from the GUI's WebGL renderer.
```

源码：`src/brainfc/models.py`，第 225 行。

### Connectome.view

```python
Connectome.view(self, path='connectome.html', *, open_browser=False)
```

```text
Write a self-contained interactive HTML report.

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
the report still shows matrix/QC. Requires browser WebGL for the 3D view.
```

源码：`src/brainfc/models.py`，第 273 行。

### Connectome.to_hicbrain

```python
Connectome.to_hicbrain(self)
```

```text
Create a connectivity BrainDataset in separately installed Hyper-Brain.

Returns
-------
hicbrain.BrainDataset
    A copy of the signed matrix with ROI IDs, names, optional coordinates and
    brainfc provenance in metadata. No hyperedges are inferred.

Raises
------
ImportError
    The independent hicbrain import is unavailable. Hyper-Brain is optional.
```

源码：`src/brainfc/models.py`，第 308 行。

## brainfc.pipeline

### fingerprint

```python
fingerprint(path)
```

```text
Hash one input file in 4 MiB chunks.

Parameters
----------
path : str or pathlib.Path
    Existing file, expanded and resolved.

Returns
-------
dict
    Absolute path, lowercase SHA-256 and size_bytes. Does not copy the file.
    Compound image partner files are not automatically enumerated.
```

源码：`src/brainfc/pipeline.py`，第 30 行。

### _confounds

```python
_confounds(path, n, config)
```

```text
Build the regression design and original-frame keep mask.

Parameters
----------
path : str, pathlib.Path or None
    TSV/CSV with exactly n original rows; None means no regression design.
n : int
    Number of original time points, before discard/censoring.
config : Config
    Controls initial discard, FD cutoff and explicit/default regression columns.

Returns
-------
tuple
    (design or None, keep_mask of shape (n,), quality_dict).

Notes
-----
Nonsteady outlier columns censor nonzero rows. FD means/max use all finite
original FD rows, including rows later excluded. Counts may overlap; use the
combined keep mask for unique exclusions. Only first-row derivative1 NaNs
are filled with zero, and each fill is recorded. An intercept-inclusive design
rank/residual check occurs later in extract_connectome.
```

源码：`src/brainfc/pipeline.py`，第 51 行。

### extract_connectome

```python
extract_connectome(source, *, atlas=None, rois=None, mask=None, reference=None, confounds=None, config=None, progress=None)
```

```text
Extract, clean and correlate one fMRI run or an ROI time-series file.

Parameters
----------
source : str or pathlib.Path
    One supported time-series file. Directories and DICOM are not accepted.
atlas : str, pathlib.Path or None, default None
    3D nonnegative integer label image for volume; matching single-map dlabel
    for dense CIFTI; label.gii for GIFTI. Not used for tables/ptseries.
rois : str, pathlib.Path or None, default None
    CSV/TSV mapping. Label images match by label_value; tables/ptseries by
    roi_id. Must exactly cover extracted IDs. Optional x/y/z are RAS+ mm.
mask : str, pathlib.Path or None, default None
    Same-space volume mask. Positive values retain voxels; nearest-neighbor
    resampled. Not accepted for tables, CIFTI or GIFTI. Not used as reference
    unless also passed to reference.
reference : str, pathlib.Path or None, default None
    Same-space 3D brain mask or skull-stripped reference for display only.
    The caller establishes registration; no transform is estimated.
confounds : str, pathlib.Path or None, default None
    Headered TSV/CSV aligned to all original frames. See Config for selection.
config : Config or None, default None
    None constructs Config(). Does not accept a configuration dict directly.
progress : callable or None, default None
    Called synchronously with a human-readable str at processing milestones.

Returns
-------
Connectome
    Cleaned time x ROI signals, signed R x R connectivity, Fisher-z, ROI order,
    retained original indices, QC, provenance and optional display geometry.

Raises
------
InputError
    Incompatible dimensions/axes/spaces/TR, missing ROIs, invalid confounds,
    insufficient retained frames/residual rank, nonfinite/constant ROI signals.
OSError, ValueError
    Underlying file/parser failures may also propagate.

Notes
-----
Image input requires preprocessed=True. Grid resampling is not registration.
Processing: ROI means -> initial discard -> Nilearn joint filtering/regression/
censoring -> correlation -> Fisher-z -> geometry/provenance. No files are
written and no atlas is downloaded. Table numeric content is interpreted as
time series; check_input additionally rejects suspected symmetric matrices.
No group inference, disease classification or raw spatial preprocessing occurs.
```

源码：`src/brainfc/pipeline.py`，第 144 行。

## brainfc.io

### numeric_table

```python
numeric_table(path, *, header=True, variable=None, transpose=False)
```

```text
Read a real finite time x ROI table and optional column IDs.

Parameters
----------
path : str or pathlib.Path
    CSV (comma), TSV (tab), TXT/1D (whitespace), NPY, NPZ or pre-v7.3 MAT.
header : bool, default True
    Text first row is column names; '#' lines are comments. False retains the
    first numeric row. Binary formats ignore this setting.
variable : str or None, default None
    NPZ/MAT 2D numeric variable; infer only when exactly one exists.
transpose : bool, default False
    Transpose values and discard inferred column names.

Returns
-------
tuple[numpy.ndarray, list[str] or None]
    Float array and column IDs. Requires at least two rows and columns.

Raises
------
InputError
    Complex, nonfinite, non-2D data, ambiguous variable or unsupported MAT v7.3.

Notes
-----
Only ROI columns may be supplied; numeric time/index columns are not detected
automatically. NPY/NPZ use allow_pickle=False. No symmetric-matrix check here.
```

源码：`src/brainfc/io.py`，第 17 行。

### sidecar_path

```python
sidecar_path(path)
```

```text
Return the adjacent JSON candidate for a source filename.

For *.nii[.gz], *.dtseries.nii and *.ptseries.nii replace the imaging suffix
with .json. For other formats append .json (for example signals.tsv.json).
Returns pathlib.Path without checking existence; BIDS inheritance is not used.
```

源码：`src/brainfc/io.py`，第 94 行。

### metadata

```python
metadata(path)
```

```text
Read adjacent JSON RepetitionTime and the filename's BIDS space entity.

Returns a dict with sidecar (absolute path or None), t_r (seconds or None),
and space (str or None). Missing JSON yields no TR; malformed JSON propagates
JSONDecodeError. Header TR is handled by check_input/extract_connectome.
```

源码：`src/brainfc/io.py`，第 104 行。

### inspect_input

```python
inspect_input(path)
```

```text
Inspect file structure or discover preprocessed volume runs in a directory.

Parameters
----------
path : str or pathlib.Path
    Existing source file or derivative directory.

Returns
-------
dict
    Common file keys: path, size_bytes, sidecar, t_r, space, format.
    Volume adds shape/affine/orientation/units when available; CIFTI shape/axes;
    GIFTI array shapes; NPZ/MAT variable shapes. Directory returns format/runs.

Raises
------
InputError
    Missing path or unreadable image. Low-level table/JSON errors may propagate.

Notes
-----
Inspection alone does not validate numerical signals, ROI coverage or cleaning
feasibility. Use check_input/preflight or extract_connectome for deeper checks.
```

源码：`src/brainfc/io.py`，第 121 行。

### discover_bids

```python
discover_bids(root)
```

```text
List separate fMRIPrep preprocessed volume runs below root.

Parameters
----------
root : str or pathlib.Path
    Recursively scanned for *_desc-preproc_bold.nii* in sorted path order.

Returns
-------
list[dict]
    Each record has bold, confounds, mask, subject, session, task, run, sidecar,
    t_r, space. Missing companions/entities are None. No matches yields [].

Raises
------
InputError
    More than one matching mask or confounds file makes a run ambiguous.

Notes
-----
Companions must be in the same directory with exactly matching entities after
excluding space/res/den/desc; masks additionally match space/res. No merging,
raw BIDS conversion, multi-echo combination or full BIDS metadata inheritance.
```

源码：`src/brainfc/io.py`，第 185 行。

## brainfc.imaging

### roi_table

```python
roi_table(path)
```

```text
Read and validate an optional CSV/TSV ROI mapping.

Returns pandas.DataFrame, or None when path is None. Requires unique nonempty
roi_id. Optional label_value must be unique finite integers; coordinates must
include all of x/y/z with finite numeric values. Empty text is preserved.
Exact correspondence to extracted labels is checked later by make_rois.
```

源码：`src/brainfc/imaging.py`，第 12 行。

### make_rois

```python
make_rois(ids, names=None, coords=None, table=None, *, by_value=True)
```

```text
Construct canonical ROI records in the supplied extraction order.

Parameters
----------
ids : sequence
    Actual integer label values when by_value=True, otherwise string IDs.
names : sequence of str or None
    Fallback labels; defaults to 'ROI {value}'.
coords : numpy.ndarray or None
    Fallback (R,3) coordinates in RAS+ mm.
table : pandas.DataFrame or None
    Validated mapping; name, coordinates and metadata override fallbacks.
by_value : bool, default True
    Match mapping on label_value, otherwise roi_id; exact ID set is required.

Returns
-------
list[dict]
    roi_id, label_value, name, abbreviation, hemisphere, network, coordinates.
    For already-parcellated input, label_value is a 1-based ordinal.

Raises
------
InputError
    Missing/extra mapping IDs or duplicate final roi_id values.

Notes
-----
Input mapping row order does not reorder results. Fallback hemisphere is based
on x sign (L/R/M); without coordinates it is M, not an anatomical inference.
```

源码：`src/brainfc/imaging.py`，第 38 行。

### validate_volume

```python
validate_volume(img, *, ndim=None)
```

```text
Validate a NiBabel spatial image without resampling it.

img must be a SpatialImage with finite invertible affine. Optional ndim checks
exact dimension count. Requires mm/unknown units and consistent coded qform/
sform (numpy.allclose atol=1e-3, default rtol). Returns None or raises InputError.
When ndim=None, this helper does not independently restrict dimension count.
```

源码：`src/brainfc/imaging.py`，第 107 行。

### label_values

```python
label_values(data)
```

```text
Return sorted positive integer ROI labels from a numeric array.

Requires nonnegative, finite integer values; zero is background. Returns a
1D integer numpy.ndarray with 2 to 2000 labels, otherwise raises InputError.
Probabilistic atlases are not accepted.
```

源码：`src/brainfc/imaging.py`，第 133 行。

### volume_timeseries

```python
volume_timeseries(img, atlas_path, mask_path=None, table=None)
```

```text
Compute arithmetic ROI means on one 4D NiBabel volume.

img is a loaded spatial image; atlas_path is a 3D integer-label filename.
mask_path optionally restricts labels by positive mask values. table is an
optional validated pandas ROI mapping. Atlas/mask are nearest-neighbor
resampled to the BOLD grid; coordinate centroids use the original atlas.

Returns (time_x_roi_array, roi_records, image_qc, aligned_atlas_image).
QC includes voxel counts, resampling flag, orientation, shape and units.
Reads BOLD in 8-frame slabs, casts slabs to float32 and accumulates means in
float64. All original atlas ROIs must remain after resampling/masking.
Raises InputError on geometry/coverage/nonfinite-ROI failures. This low-level
function does not check named spaces, preprocessing status or temporal settings.
```

源码：`src/brainfc/imaging.py`，第 149 行。

### cifti_timeseries

```python
cifti_timeseries(img, atlas_path=None, table=None)
```

```text
Extract a loaded CIFTI time series with exact axis matching.

img requires SeriesAxis in SECOND followed by BrainModelAxis or ParcelsAxis.
Dense input requires atlas_path: one LabelAxis map whose BrainModelAxis equals
the input axis. Parcel input is read directly in ParcelsAxis name order.
table optionally maps labels/parcel IDs and supplies display coordinates.

Returns (time_x_roi_array, roi_records, {'t_r': seconds, 'format':'cifti'}, None).
Dense data uses 16-frame slabs and unweighted grayordinate means. No CIFTI
display centroids or surface mesh are inferred. InputError reports invalid
axes/atlas/nonfinite dense data; pipeline validates parcel signals afterwards.
Low-level extraction does not validate named spaces/preprocessing status.
```

源码：`src/brainfc/imaging.py`，第 215 行。

### gifti_timeseries

```python
gifti_timeseries(img, atlas_path, table=None)
```

```text
Extract loaded GIFTI functional arrays using one LABEL-intent atlas.

atlas_path must have one label array with matching vertex count. Functional
arrays must have TIME_SERIES intent: one vertices x time array or one 1D
vertex array per frame. table optionally supplies label mapping/coordinates.
Returns (time_x_roi_array, roi_records, {'format':'gifti'}, None).
Arithmetic means use the complete dense array in memory. TR is not inferred
from GIFTI metadata. InputError reports incompatible intents/counts or nonfinite
signals. The caller must establish same hemisphere/template/vertex ordering.
```

源码：`src/brainfc/imaging.py`，第 274 行。

### brain_geometry

```python
brain_geometry(atlas_img=None, reference=None, *, space='unknown')
```

```text
Build a display mesh from atlas coverage or an explicit reference.

atlas_img is an optional loaded 3D spatial image; reference is an optional
3D brain-mask/skull-stripped-reference filename taking precedence. space labels
the output; this function does not prove alignment to that named space.

Returns a dict with space, units='mm', orientation='RAS+', brain (flat positions/
indices), parcels={} and source. With no image returns an empty mesh, preserving
coordinate-only visualization. Positive voxels undergo closing/hole filling,
Gaussian interpolation (sigma=0.65 voxel), marching cubes and RAS+ transform.
Only display geometry changes; no ROI extraction data are modified.
InputError reports invalid/empty references. Atlas coverage is not a pial surface.
```

源码：`src/brainfc/imaging.py`，第 322 行。

## brainfc.atlases

### fetch_atlas

```python
fetch_atlas(name='schaefer100', *, data_dir=None)
```

```text
Explicitly download/cache one supported integer-label atlas.

Parameters
----------
name : {'schaefer100','schaefer200','schaefer400','aal116'}
    Default 'schaefer100'. Schaefer: 7 networks, 2 mm, MNI152NLin6Asym.
    AAL: SPM12 116 regions, MNIColin27. These spaces are not interchangeable.
data_dir : str, pathlib.Path or None, default None
    Cache root; default ~/.cache/brainfc/atlases.

Returns
-------
dict
    atlas (image path), rois (TSV path), space, name, source URL, n_rois.

Notes
-----
Creates cache directories; Nilearn downloads only as required. Regenerates
name_rois.tsv and name.json in that cache. ROI centroid coordinates are mm
from the atlas affine. Network/download failures propagate. No download at
import time; dataset/atlas licenses remain those of their providers.
```

源码：`src/brainfc/atlases.py`，第 10 行。

## brainfc.plotting

### edges_of

```python
edges_of(result, threshold=0.3, max_edges=200, selection=None)
```

```text
Return display edges as (zero_based_row, zero_based_column, signed_weight).

result must expose rois and connectivity. threshold (default .3) is inclusive
in [0,1], but zero edges are omitted. max_edges (default 200) is nonnegative.
selection is None, {'kind':'node','id':ROI_ID}, or {'kind':'edge','id':'i:j'}.
Selection and threshold precede a stable descending-absolute-weight sort and
cap; ties use upper-triangle row-major order. Original arrays are unchanged.
Invalid settings or unknown selections raise InputError. An empty list is valid.
```

源码：`src/brainfc/plotting.py`，第 21 行。

### plot_matrix

```python
plot_matrix(result, path=None)
```

```text
Functional form of Connectome.plot_matrix(result, path=None).

Accepts a Connectome or compatible result object with connectivity, rois and
provenance['method']. Returns a matplotlib Figure; optional path is saved at
300 dpi and may overwrite an existing image. Uses a process-wide rendering lock.
See Connectome.plot_matrix for display and figure-lifecycle details.
```

源码：`src/brainfc/plotting.py`，第 65 行。

### plot_views

```python
plot_views(result, path=None, *, threshold=0.3, max_edges=200, selection=None, opacity=0.28, theme='paper')
```

```text
Functional form of Connectome.plot_views with identical display options.

Accepts a Connectome or compatible object with rois/connectivity/qc/geometry.
Requires coordinates for every ROI. Returns a matplotlib Figure; path saves
PNG/SVG/PDF (or other Matplotlib format) and closes it, potentially overwriting.
See Connectome.plot_views for selection ID conventions, limits, opacity,
theme, rasterized shell and figure-lifecycle details.
```

源码：`src/brainfc/plotting.py`，第 92 行。

## brainfc.export

### write_report

```python
write_report(result, path, *, view_image=None)
```

```text
Write self-contained HTML and return its absolute pathlib.Path.

result is a Connectome; path must not exist. Optional view_image is a PNG path
embedded as the initial static preview. Parent directories are created.
Interactive JS/CSS and result data are embedded, with JSON escaped for safe
script embedding. Raises FileExistsError on overwrite or InputError if bundled
assets are missing. Does not open a browser; see Connectome.view.
```

源码：`src/brainfc/export.py`，第 19 行。

### save_result

```python
save_result(result, directory, *, figures=True, report=True)
```

```text
Export a Connectome to a new directory and return its absolute Path.

directory, figures=True and report=True have exactly the same contract as
Connectome.save. Writes a temporary sibling directory, removes it on errors,
and renames it on success. No ZIP is created. manifest.json hashes all other
exported files, excluding itself. See docs/outputs.md for schemas and file list.
```

源码：`src/brainfc/export.py`，第 54 行。

## brainfc.demo

### create_demo

```python
create_demo(directory, *, kind='synthetic')
```

```text
Copy or generate bundled example inputs in a new directory.

Returns a dict of source/atlas/rois/confounds paths plus a plain config dict.
Use Config(**spec.pop('config')) before passing spec to extract_connectome.
kind='synthetic' (default): seed 42, 160 frames, 12 artificial ROIs, TR=2 s
in synthetic-demo space. kind='rest01': a de-identified single-participant
resting-state example, with 150 preprocessed time points in 100 Schaefer ROIs,
confounds and a brain-only display mask. The latter includes an example.json
methods/QC record; it has no slice-timing or susceptibility-distortion correction.
Its returned spec also includes reference, and omits atlas (table input).
Creates inputs only, without network access or computing connectivity.
Existing directories raise FileExistsError; invalid kind raises ValueError.
When exporting, mark provenance['synthetic'] according to kind (the CLI does so).
```

源码：`src/brainfc/demo.py`，第 11 行。

## brainfc.preprocessing

### CommandPlan

```python
CommandPlan(argv: list[str], description: str) -> None
```

```text
An external command represented as argv and a human description.

argv is list[str]; description is str. Construction itself does not execute
anything. Plans from this module bind original BIDS and license read-only.
Calling run explicitly executes the command and may download Docker images
or templates; these dependencies are not bundled in the pip distribution.
```

源码：`src/brainfc/preprocessing.py`，第 13 行。

### CommandPlan.to_dict

```python
CommandPlan.to_dict(self)
```

```text
Return argv, description, powershell and posix command renderings.

Shell renderings are for review/pasting. run executes argv with shell=False,
so paths and arguments are not interpolated into a shell command.
```

源码：`src/brainfc/preprocessing.py`，第 24 行。

### CommandPlan.run

```python
CommandPlan.run(self, *, log=None)
```

```text
Execute argv synchronously, optionally writing a new combined log.

log is None (inherit terminal output), or a new filename whose parent exists.
Returns subprocess.CompletedProcess after a successful exit. Raises InputError
if the executable is missing, FileExistsError if log exists, or
subprocess.CalledProcessError when the external program exits unsuccessfully.
No timeout or automatic retry is applied.
```

源码：`src/brainfc/preprocessing.py`，第 38 行。

### dicom_plan

```python
dicom_plan(source, output, *, executable='dcm2niix')
```

```text
Plan dcm2niix conversion without running it or creating output.

source is an existing DICOM directory; output must be new and outside source
(neither directory can contain the other). executable defaults to 'dcm2niix'.
Returns CommandPlan with JSON output, anonymized sidecars and gzipped NIfTI.
InputError reports invalid directories. Planning does not test executable
availability. Output filenames are series-based and are not automatically BIDS.
```

源码：`src/brainfc/preprocessing.py`，第 66 行。

### convert_dicom

```python
convert_dicom(source, output, *, executable='dcm2niix', log=None)
```

```text
Create a new output directory and run dcm2niix synchronously.

source/output/executable follow dicom_plan; log follows CommandPlan.run.
Returns subprocess.CompletedProcess. Checks executable availability before
creating output. External failure may leave partial conversion files; choose
a new destination to retry. Conversion does not organize or validate BIDS.
```

源码：`src/brainfc/preprocessing.py`，第 85 行。

### fmriprep_plan

```python
fmriprep_plan(bids_dir, output_dir, license_file, *, participant=None, space='MNI152NLin6Asym', image='nipreps/fmriprep:25.2.5')
```

```text
Build a pinned Docker fMRIPrep invocation without running it.

Parameters
----------
bids_dir : str or pathlib.Path
    Existing raw BIDS root containing dataset_description.json.
output_dir : str or pathlib.Path
    Derivatives directory outside source; may already exist for resuming.
license_file : str or pathlib.Path
    Existing FreeSurfer license, mounted read-only.
participant : str or None, default None
    One alphanumeric subject label, with optional 'sub-' prefix; None processes
    all subjects. A specified subject directory must exist.
space : str, default 'MNI152NLin6Asym'
    Alphanumeric named template; output requested at res-2.
image : str, default 'nipreps/fmriprep:25.2.5'
    Must be a pinned numeric nipreps/fmriprep:X.Y.Z image.

Returns
-------
CommandPlan
    Docker command using --fs-no-reconall and one output space.

Notes
-----
Requires Docker Linux containers, license, CPU/RAM and template/image downloads
when run. This planner performs only basic path checks. The web route additionally
calls check_raw_bids; fMRIPrep performs full BIDS validation. Inspect external
reports before extraction. No DICOM-to-BIDS inference or surface reconstruction.
```

源码：`src/brainfc/preprocessing.py`，第 99 行。

## brainfc.presets

### dataset_presets

```python
dataset_presets()
```

```text
Return an independent copy of the source-attributed dataset catalog.

Returns dict with version, datasets and policy. Each dataset has id/name and
variants. Variants contain id/name/source, input_kind and acquisition hints/
notes. Includes custom, ABIDE, ADNI, ADHD-200, MDD and PPMI. Offline operation;
no participant files are fetched. Scan metadata must confirm TR hints.
```

源码：`src/brainfc/presets.py`，第 161 行。

### dataset_preset

```python
dataset_preset(dataset='custom', variant='custom')
```

```text
Return one dataset/protocol variant as an independent dictionary.

dataset and variant default to 'custom'. Use dataset_presets() for exact
case-sensitive identifiers. Returns dataset, dataset_name, catalog_version
and the selected variant's fields. Raises InputError for an unknown pair.
This is a reference record, not a Config or a guaranteed scan-specific protocol.
```

源码：`src/brainfc/presets.py`，第 175 行。

## brainfc.workflow

### input_suggestions

```python
input_suggestions(path, *, overrides=None)
```

```text
Suggest text header handling and exactly matched local companions.

path is a single-run file. overrides is an optional Config field dict taking
precedence over header inference. Returns {'info': check_input output,
'config': inferred/overridden settings, 'paths': matched files, 'notes': []}.
All-numeric first non-comment line is considered data; numeric ROI headers
require an explicit override. No downloads or history reuse in this Python
function; /api/input-suggestions adds those web-workspace features.
```

源码：`src/brainfc/workflow.py`，第 11 行。

### check_raw_bids

```python
check_raw_bids(payload)
```

```text
Check minimum raw BIDS BOLD/T1 inventory, without preprocessing.

payload requires bids_dir and may contain participant (with/without sub-).
Rejects DatasetType='derivative', absent BOLD/T1, or non-4D/short BOLD.
Returns {'bold_runs': int, 'scope': str}. Does not validate all JSON acquisition
fields or BIDS inheritance; fMRIPrep's full BIDS validator is still required.
```

源码：`src/brainfc/workflow.py`，第 47 行。

### check_input

```python
check_input(path, config=None)
```

```text
Inspect one run and add dimensions, TR source and atlas requirements.

path is a file; config is Config or None. Returns inspect_input metadata plus
n_frames, needs_atlas, t_r, tr_source, and n_rois for tables. Known image time
headers add header_t_r. Rejects symmetric square tables as suspected matrices,
wrong image/time axes and conflicting JSON/header TR. Numerical ROI coverage,
named-space matching and regression feasibility require further validation.
Unlike the extraction core, this preflight is conservative about symmetric tables.
```

源码：`src/brainfc/workflow.py`，第 84 行。

### preflight

```python
preflight(payload, *, stage='review')
```

```text
Validate a guided extraction request without calculating connectivity.

payload contains source, optional atlas/rois/mask/reference/confounds paths and
a plain config dict. stage='input' performs check_input only; 'spatial' also
checks preprocessing declaration, spaces and companion paths; 'review' further
checks TR, Nyquist, confound rows and retained-frame counts.
Returns input metadata; review adds n_retained, confound_columns, effective_tr
and validated=True. Raises InputError or file/parser errors on invalid inputs.
Full ROI coverage, CIFTI alignment and cleaned-signal variance are checked only
by extract_connectome. This function does not download or write files.
```

源码：`src/brainfc/workflow.py`，第 146 行。

### validate_guidance

```python
validate_guidance(payload)
```

```text
Validate optional GUI decisions attached to an extraction payload.

Returns None when guidance is absent (standard API clients need no UI clicks).
Otherwise requires recognized dataset/variant, source/spatial/denoise/review
confirmations, explicit skipped confounds/reference choices and raw-data QC
confirmation when applicable, then runs preflight. Returns a copy enriched
with official_preset. It never applies preset hints to Config automatically.
```

源码：`src/brainfc/workflow.py`，第 214 行。

## brainfc.cli

### main

```python
main(argv=None)
```

```text
Run the CLI with a list of arguments, or sys.argv when argv is None.

Returns 0 on success. argparse raises SystemExit(0) for help/version and
SystemExit(2) for usage, InputError and common path errors. Unexpected
library/external-process errors propagate; a failed batch exits with 2
after preserving successful run outputs and batch.json.
```

源码：`src/brainfc/cli.py`，第 61 行。

## brainfc.web.app

### create_app

```python
create_app(workspace=None)
```

```text
Create the optional local FastAPI application and its workspace.

workspace is a directory (default ~/brainfc-workspace). Creates jobs and
workspace folders. Persisted queued/running jobs are marked interrupted on
startup; use one server process per workspace. Returns fastapi.FastAPI.
GUI dependencies are included in the standard package install. Local Host and same-origin checks are applied; no
account authentication. Bind to loopback, as brainfc serve does.
The app uses one worker with at most eight active/queued jobs. /docs, /redoc
and /openapi.json describe HTTP contracts; see docs/http-api.md.
```

源码：`src/brainfc/web/app.py`，第 37 行。
