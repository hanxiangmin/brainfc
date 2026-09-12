![BrainFC — functional connectivity, made visible](docs/assets/brainfc-hero.png)

<p align="center"><b>Resting-state fMRI (rs-fMRI), functional connectivity and brain network analysis.</b><br>Connectome visualization, graphs and native hypergraphs. Python API + local GUI.</p>

<p align="center"><a href="README.md">中文</a> · <b>English</b> · <a href="docs/index.md">Documentation</a> · <a href="docs/api-reference.md">API reference</a> · <a href="https://pypi.org/project/brainfc/">PyPI</a></p>

## Install

Requires **Python 3.11–3.13**.

```bash
pip install -U brainfc
brainfc serve
```

Choose **打开真实样例** in the browser to try the bundled real example. No files or parameters to supply. The GUI is in Chinese; Python API docstrings are in English.

## Use

### 1. Start with ROI time series

For signals that already received the required upstream denoising. The TSV has a header, one time point per row, and ROI signal columns only.

```python
from brainfc import Config, extract_connectome

result = extract_connectome(
    "roi_timeseries.tsv",
    config=Config(detrend=False, standardize=False),
)
fc = result.connectivity
z = result.fisher_z
result.save("results/roi-001")
```

Use `table_header=False` for headerless text. Matrix computation and plotting work without coordinates; 3D and eight-view rendering require complete ROI coordinates and a declared space.

### 2. Extract from preprocessed fMRI

Replace the filenames with your BOLD run and row-aligned confound table. The BOLD must already be registered to the declared space.

```python
from brainfc import Config, extract_connectome, fetch_atlas

atlas = fetch_atlas("schaefer100")  # Downloads once, then reuses its cache.
result = extract_connectome(
    "sub-01_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz",
    atlas=atlas["atlas"],
    rois=atlas["rois"],
    confounds="sub-01_desc-confounds_timeseries.tsv",
    config=Config(
        preprocessed=True,
        data_space="MNI152NLin6Asym",
        atlas_space=atlas["space"],
    ),
)
```

Defaults include detrending and standardization, with no band-pass filter or FD-threshold censoring. Select temporal options according to the upstream processing history. Atlas grid resampling does not perform spatial registration.

### 3. Visualize and export

Continue with the image result above:

```python
result.plot_matrix("matrix.svg")
result.plot_views("eight_views.pdf", threshold=0.4, max_edges=150)
result.view("brain-network.html", open_browser=True)
result.save("results/sub-01")
```

`save()` requires a new directory. It exports arrays, tables, ROI order, original frame indices, quality/provenance records, figures, and a self-contained HTML report.

[Runnable example](examples/quickstart.py) · [Batch example](examples/batch_derivatives.py) · [Python guide](docs/python-api.md) · [Complete API](docs/api-reference.md) · [CLI](docs/cli-reference.md) · [HTTP API](docs/http-api.md)

## Graphs and native hypergraphs

Continue with the extracted `result`:

```python
from brainfc.network import AnalysisConfig
from brainfc.network.export import export_result

# result is the Connectome returned by extract_connectome above.
network = result.analyze_network(AnalysisConfig(
    graph_method="density", density=0.1,
    hypergraph_method="multiscale", hypergraph_ks=[5, 10],
))
export_result(network, "network-result.zip")
```

Choose **进入网络分析** after extraction. The matrix, ROI order, coordinates and processing records transfer automatically.

[Network guide](docs/network-analysis.md) · [Runnable example](examples/network_analysis.py)

## Features

| Capability | What it provides |
| :--- | :--- |
| Multiple inputs | Supported NiBabel volume containers, CIFTI, paired GIFTI, ROI tables/arrays, and fMRIPrep run discovery. |
| Scientific processing | ROI means; joint Nilearn temporal cleaning and censoring; Pearson, Spearman, or Ledoit–Wolf partial correlation. |
| Guided setup | Metadata suggestions, ordered confirmation steps, and source-linked ABIDE/ADNI/ADHD-200/MDD/PPMI presets. |
| Synchronized views | Matrix-to-ROI selection; shared thresholds, edge limits, and ROI/edge selections in 3D and eight views. |
| Traceable results | Full signed matrices, separate Fisher-z, parameters, QC, input hashes, ROI order, and original frame indices. |
| Local operation | Shared Python/CLI/GUI core, local data processing, and offline interactive reports. |

![Actual BrainFC 3D interface](docs/assets/viewer.png)

<table>
<tr><th width="50%">Full connectivity matrix</th><th width="50%">Synchronized eight views</th></tr>
<tr><td><a href="docs/assets/matrix.png"><img src="docs/assets/matrix.png" alt="Full Schaefer-100 matrix"></a></td><td><a href="docs/assets/eight-views.png"><img src="docs/assets/eight-views.png" alt="Eight projections of the same displayed connections"></a></td></tr>
</table>

These results use the [de-identified rest01 example](docs/real-example.md): 100 ROIs and 145 retained frames. The matrix preserves complete Pearson correlations; 3D and eight-view displays share the selected edges. The header is conceptual artwork. [Processing and QC](docs/real-example.md) · [Privacy review](docs/privacy-review.md)

## Processing workflow

![Detailed processing workflow, drawn with the archify skill](docs/assets/processing.png)

[Vector SVG](docs/assets/processing.svg) · [Download interactive HTML](docs/assets/processing.html) · [Editable specification](docs/assets/processing.dataflow.json) · [Methods](docs/processing.md)

Raw BOLD + T1 and supported DICOM series can be processed through the Python pipeline, followed by visual QC and connectivity extraction. See the [raw fMRI guide](docs/python-preprocessing.md). No MATLAB or Docker is required. This pipeline does not perform susceptibility-distortion correction or claim SPM equivalence.

## License and credits

Copyright © 2026 BrainFC contributors. [Apache License 2.0](LICENSE). Citation metadata: [CITATION.cff](CITATION.cff).

Built on NumPy, SciPy, NiBabel, Nilearn, scikit-learn, Matplotlib, React, and Three.js. The 3D component is adapted from [Hyper-Brain](https://github.com/hanxiangmin/Hyper-Brain); BrainFC installs and runs independently. Workflow artwork uses the [archify skill](https://github.com/tt-a1i/archify). See [NOTICE](NOTICE) and [third-party licenses](src/brainfc/web/static/THIRD_PARTY_NOTICES.txt). Atlas and dataset licenses remain with their providers; participant data are not distributed here.

[Contributing](CONTRIBUTING.md) · [Release guide](docs/release.md) · [Issues](https://github.com/hanxiangmin/brainfc/issues)
