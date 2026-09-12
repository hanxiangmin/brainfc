# 命令行完整参数 · 0.3.0

由 argparse 自动生成，与 `brainfc --help` 一致。`python -m brainfc` 与安装后的 `brainfc` 入口等价。

详细使用例子见 [安装与上手](quickstart.md)；退出码：成功 0，参数/常见输入错误 2，其他未捕获错误非零。

```text
usage: brainfc [-h] [--version]
               {serve,inspect,atlas,demo,extract,batch,dicom,preprocess} ...

fMRI → ROI time series → functional connectivity

positional arguments:
  {serve,inspect,atlas,demo,extract,batch,dicom,preprocess}
    serve               Start the local graphical interface
    inspect             Inspect an image or discover BIDS derivatives
    atlas               Explicitly download a supported standard atlas
    demo                Extract a bundled synthetic or de-identified resting-
                        state example
    extract             Extract one run
    batch               Extract each fMRIPrep run separately; failed runs are
                        recorded
    dicom               Plan or run dcm2niix conversion
    preprocess          Plan or run external fMRIPrep (requires Docker)

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

`extract` 中显式的 `--tr` / 空间 / `--preprocessed` 覆盖 JSON 的同名字段；其余处理选项通过 `--config` 提供。`dicom` 与 `preprocess` 默认只显示命令，`--run` 才执行。`batch` 每个 run 单独处理，失败保留在 `batch.json` 中；已有输出目录拒绝覆盖。
