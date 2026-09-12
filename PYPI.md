![BrainFC: functional connectivity, made visible](https://raw.githubusercontent.com/hanxiangmin/brainfc/main/docs/assets/brainfc-hero.png)

# BrainFC

**fMRI → ROI time series → functional connectivity → matrix, eight-view and interactive 3D reports.**

BrainFC is a Python library with a command-line interface and a local graphical interface. Both interfaces use the same processing core. The default installation includes the GUI and an offline API manual. Python 3.11 or newer is required; ordinary users do not need Node.js.

## Install and launch

```shell
pip install brainfc
brainfc serve
```

The interface opens at `http://127.0.0.1:8766`. Choose the built-in demo to generate synthetic NIfTI inputs and a complete report without downloading participant data. The offline manual is available at `/reference/` and the HTTP API schema at `/docs`.

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

Raw DICOM/BIDS spatial preprocessing requires external dcm2niix/fMRIPrep. BrainFC provides command adapters; it does not implement that preprocessing itself. The complete external raw-data chain has not been validated in this release. This package does not provide disease diagnosis or cohort-level inference.

## Documentation and source

- [Quickstart](https://github.com/hanxiangmin/brainfc/blob/main/docs/quickstart.md)
- [Complete Python API](https://github.com/hanxiangmin/brainfc/blob/main/docs/api-reference.md)
- [Python usage guide](https://github.com/hanxiangmin/brainfc/blob/main/docs/python-api.md)
- [Input formats and processing contract](https://github.com/hanxiangmin/brainfc/blob/main/docs/formats.md)
- [Source code and issues](https://github.com/hanxiangmin/brainfc)

Licensed under Apache-2.0. The 3D viewer is adapted from Hyper-Brain; BrainFC runs independently. Dataset and atlas licenses remain with their original providers.

## Integrated network analysis (0.4.0)

Hyper-Brain's graph, native-hypergraph, atlas, statistics and network workbench
are included in BrainFC. Use `result.analyze_network(AnalysisConfig(...))`,
`brainfc network result-folder --output network.zip`, or the **进入网络分析**
button after extraction. Existing `hicbrain` imports are compatibility aliases.
Remove an old `hic-brain` distribution before upgrading in the same environment.
See the [network guide](https://github.com/hanxiangmin/brainfc/blob/main/docs/network-analysis.md).
