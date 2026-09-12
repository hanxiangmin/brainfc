# 命令行完整参数 · 0.5.0

由 argparse 自动生成，与 `brainfc --help` 一致。`python -m brainfc` 与安装后的 `brainfc` 入口等价。

详细使用例子见 [安装与上手](quickstart.md)；退出码：成功 0，参数/常见输入错误 2，其他未捕获错误非零。

```text
usage: brainfc [-h] [--version]
               {serve,inspect,atlas,demo,extract,network,batch,dicom,preprocess,process,convert}
               ...

fMRI → ROI time series → functional connectivity

positional arguments:
  {serve,inspect,atlas,demo,extract,network,batch,dicom,preprocess,process,convert}
    serve               Start the local graphical interface
    inspect             Inspect an image or discover BIDS derivatives
    atlas               Explicitly download a supported standard atlas
    demo                Extract a bundled synthetic or de-identified resting-
                        state example
    extract             Extract one run
    network             Analyze a saved connectome, matrix or ROI time series
    batch               Extract each fMRIPrep run separately; failed runs are
                        recorded
    dicom               Plan or run dcm2niix conversion
    preprocess          Plan or run external fMRIPrep (requires Docker)
    process             Preprocess raw BOLD/T1 in Python; inspect QC before
                        extracting FC
    convert             Convert one selected MR DICOM series entirely in
                        Python

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## serve

```text
usage: brainfc serve [-h] [--port PORT] [--workspace WORKSPACE] [--no-browser]

options:
  -h, --help            show this help message and exit
  --port PORT
  --workspace WORKSPACE
  --no-browser
```

## inspect

```text
usage: brainfc inspect [-h] source

positional arguments:
  source

options:
  -h, --help  show this help message and exit
```

## atlas

```text
usage: brainfc atlas [-h] [--data-dir DATA_DIR]
                     {schaefer100,schaefer200,schaefer400,aal116}

positional arguments:
  {schaefer100,schaefer200,schaefer400,aal116}

options:
  -h, --help            show this help message and exit
  --data-dir DATA_DIR
```

## demo

```text
usage: brainfc demo [-h] --output OUTPUT [--kind {synthetic,rest01}]

options:
  -h, --help            show this help message and exit
  --output OUTPUT
  --kind {synthetic,rest01}
```

## extract

```text
usage: brainfc extract [-h] [--atlas ATLAS] [--rois ROIS]
                       [--confounds CONFOUNDS] [--mask MASK]
                       [--reference REFERENCE] [--config CONFIG] --output
                       OUTPUT [--preprocessed] [--data-space DATA_SPACE]
                       [--atlas-space ATLAS_SPACE] [--tr TR] [--no-report]
                       [--no-figures]
                       source

positional arguments:
  source

options:
  -h, --help            show this help message and exit
  --atlas ATLAS
  --rois ROIS
  --confounds CONFOUNDS
  --mask MASK
  --reference REFERENCE
  --config CONFIG       Config JSON
  --output OUTPUT
  --preprocessed
  --data-space DATA_SPACE
  --atlas-space ATLAS_SPACE
  --tr TR
  --no-report
  --no-figures
```

## network

```text
usage: brainfc network [-h] [--kind {auto,timeseries,connectivity}]
                       [--matrix-kind {auto,correlation,fisher_z,covariance}]
                       [--variable VARIABLE] [--roi-columns ROI_COLUMNS]
                       [--config CONFIG] [--metadata METADATA] --output OUTPUT
                       source

positional arguments:
  source                BrainFC result folder/result.json, or a numeric data
                        file

options:
  -h, --help            show this help message and exit
  --kind {auto,timeseries,connectivity}
  --matrix-kind {auto,correlation,fisher_z,covariance}
  --variable VARIABLE
  --roi-columns ROI_COLUMNS
  --config CONFIG       Network AnalysisConfig JSON
  --metadata METADATA   ROI IDs, labels, coordinates and metadata JSON
  --output OUTPUT       New ZIP or JSON result; existing files refused
```

## batch

```text
usage: brainfc batch [-h] --atlas ATLAS [--rois ROIS] --config CONFIG --output
                     OUTPUT
                     bids_dir

positional arguments:
  bids_dir

options:
  -h, --help       show this help message and exit
  --atlas ATLAS
  --rois ROIS
  --config CONFIG
  --output OUTPUT
```

## dicom

```text
usage: brainfc dicom [-h] --output OUTPUT [--run] source

positional arguments:
  source

options:
  -h, --help       show this help message and exit
  --output OUTPUT
  --run
```

## preprocess

```text
usage: brainfc preprocess [-h] --output OUTPUT --license LICENSE
                          [--participant PARTICIPANT] [--space SPACE] [--run]
                          bids_dir

positional arguments:
  bids_dir

options:
  -h, --help            show this help message and exit
  --output OUTPUT
  --license LICENSE
  --participant PARTICIPANT
  --space SPACE
  --run
```

## process

```text
usage: brainfc process [-h] --t1w T1W [--sidecar SIDECAR] [--t1-mask T1_MASK]
                       [--config CONFIG] --output OUTPUT [--inspect]
                       bold

positional arguments:
  bold               Raw 4D BOLD NIfTI

options:
  -h, --help         show this help message and exit
  --t1w T1W          Matching 3D T1 NIfTI
  --sidecar SIDECAR  Acquisition JSON; defaults to same-stem sidecar
  --t1-mask T1_MASK  Optional independent mask on the exact T1 grid
  --config CONFIG    PreprocessConfig JSON
  --output OUTPUT    New preprocessing output directory
  --inspect          Only inspect geometry and acquisition readiness
```

## convert

```text
usage: brainfc convert [-h] [--output OUTPUT] [--series-id SERIES_ID]
                       [--kind {bold,t1w}] [--scan]
                       source

positional arguments:
  source

options:
  -h, --help            show this help message and exit
  --output OUTPUT
  --series-id SERIES_ID
                        Opaque series ID from --scan
  --kind {bold,t1w}
  --scan                Only list available MR series
```

`extract` 中显式的 `--tr` / 空间 / `--preprocessed` 覆盖 JSON 的同名字段；其余处理选项通过 `--config` 提供。`dicom` 与 `preprocess` 默认只显示命令，`--run` 才执行。`batch` 每个 run 单独处理，失败保留在 `batch.json` 中；已有输出目录拒绝覆盖。
