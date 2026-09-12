# BrainFC

[中文](README.md) · [Complete documentation](docs/index.md) · [Python API reference](docs/api-reference.md)

A standalone Python package for **single-run fMRI → ROI time series → signed functional connectivity → matrix, eight-view and interactive 3D reports**. The Python API, CLI and Chinese local GUI share one processing core. Apache-2.0.

Source is available at [hanxiangmin/brainfc](https://github.com/hanxiangmin/brainfc). Published distribution versions are listed on [PyPI](https://pypi.org/project/brainfc/); use the source installation below when a target version has not been uploaded yet.

## Install

Python 3.11+. From the source root:

```shell
python -m pip install .
brainfc serve
```

The default installation includes both the scientific API and local GUI. The GUI, offline manual and report assets are bundled; ordinary users do not need Node.js. Browse the local service at `http://127.0.0.1:8766`, the manual at `/reference/`, or the HTTP schema at `/docs`.

```shell
brainfc demo --output ./demo-001
```

This creates synthetic NIfTI inputs and an exported report in a new directory. No participant data are downloaded.

## Python

```python
from brainfc import Config, extract_connectome

result = extract_connectome(
    "signals.tsv",
    config=Config(detrend=False, standardize=False),
)
matrix = result.connectivity
result.save("results/run-001")
```

Text tables default to time × ROI, with a header and no numeric index/time column. For volume images, supply a same-space integer-label atlas and explicitly confirm `preprocessed=True`. See the [Python guide](docs/python-api.md) for NIfTI, CIFTI, GIFTI, confounds, batches and visualizations.

## Scope

- NiBabel volume formats, CIFTI dtseries/ptseries, paired GIFTI time-series/labels, CSV/TSV/TXT/1D/NPY/NPZ/MAT (excluding MAT v7.3).
- Explicit spatial declarations, ROI arithmetic means, Nilearn temporal cleaning, censoring and original-frame indices.
- Pearson, Spearman and Ledoit-Wolf partial correlation; separate clipped Fisher-z; full signed matrices retained.
- Source hashes, parameter/quality records and non-overwriting result exports.
- Threshold and selected ROI/edge synchronized between 3D and eight views. Display filtering does not alter numerical matrices.

Raw DICOM/BIDS requires external dcm2niix and fMRIPrep. The package provides command adapters, not an independent spatial preprocessing implementation. Full raw fMRIPrep execution has not been validated locally. No disease diagnosis, group inference, task GLM or structural tract reconstruction is performed.

The 3D viewer derives from [Hyper-Brain](https://github.com/hanxiangmin/Hyper-Brain); the scientific package works independently. See [NOTICE](NOTICE), [validation](docs/validation-v0.3.0.md), [contributing](CONTRIBUTING.md) and the [release guide](docs/release.md).
