![BrainFC: functional connectivity, made visible](https://raw.githubusercontent.com/hanxiangmin/brainfc/main/docs/assets/brainfc-hero.png)

# BrainFC

**Resting-state fMRI (rs-fMRI) → functional connectivity → brain networks and hypergraphs.**

Neuroimaging, connectome visualization and network analysis in one Python package, with a local GUI and complete API. Requires Python 3.11–3.13.

## Install and launch

```shell
pip install -U brainfc
brainfc serve
```

Choose **打开真实样例** to try the bundled rest01 example. No files or parameters to supply.

## Python API

```python
from brainfc import Config, extract_connectome

# A TSV with a header: rows are time points, columns are ROI signals.
result = extract_connectome(
    "signals.tsv",
    config=Config(detrend=False, standardize=False),
)
matrix = result.connectivity
result.save("results/run-001")
```

The destination must be new. For volume images, supply an integer-label atlas in the same explicitly named space and confirm that spatial preprocessing is complete. Filtering, confound regression and censoring must match the provenance of the input signals; the example above does not add temporal denoising.

## Capabilities

- Read supported NiBabel volume containers, CIFTI time series, paired GIFTI data/labels, and CSV/TSV/TXT/1D/NPY/NPZ/MAT tables (excluding MAT v7.3).
- Extract ROI means; apply confound regression, temporal cleaning and censoring while retaining original frame indices.
- Compute Pearson, Spearman or Ledoit-Wolf partial correlations, with a separate Fisher-z matrix.
- Export arrays, tables, quality records, input fingerprints, figures and an offline interactive report.
- Synchronize selected connections and display thresholds between the 3D viewer and eight anatomical views. Display filtering does not modify the complete signed matrix.

Raw BOLD + T1 and supported DICOM series have an in-process Python preprocessing route with ANTsPy, followed by visual QC and connectivity extraction. No MATLAB or Docker is required. Susceptibility-distortion correction is not implemented. This package does not provide disease diagnosis or cohort-level inference.

## Documentation and source

- [Quickstart](https://github.com/hanxiangmin/brainfc/blob/main/docs/quickstart.md)
- [Raw fMRI to brain networks: methods, functions, parameters and QC](https://github.com/hanxiangmin/brainfc/blob/main/docs/python-preprocessing.md)
- [Complete Python API](https://github.com/hanxiangmin/brainfc/blob/main/docs/api-reference.md)
- [Python usage guide](https://github.com/hanxiangmin/brainfc/blob/main/docs/python-api.md)
- [Input formats and processing contract](https://github.com/hanxiangmin/brainfc/blob/main/docs/formats.md)
- [Source code and issues](https://github.com/hanxiangmin/brainfc)

Licensed under Apache-2.0. The 3D viewer is adapted from Hyper-Brain; BrainFC runs independently. Dataset and atlas licenses remain with their original providers.

## Network analysis

Choose **进入网络分析** after extraction to explore graphs, native hypergraphs and network metrics. The matrix and ROI mapping transfer automatically.

```python
from brainfc.network import AnalysisConfig

network = result.analyze_network(AnalysisConfig(k=5))
```

[Network guide](https://github.com/hanxiangmin/brainfc/blob/main/docs/network-analysis.md) · [Compatibility guide](https://github.com/hanxiangmin/brainfc/blob/main/docs/hyper-brain-migration.md)
