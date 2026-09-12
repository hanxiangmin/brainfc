# README artwork and workflow

`brainfc-hero.png` is conceptual product artwork generated with the built-in imagegen tool, revised to a warm ivory/sage background. It is not a screenshot or measured scientific result. The final editing prompt is preserved in `hero-prompt.txt`.

`viewer.png`, `matrix.png` and `eight-views.png` are actual BrainFC outputs using a Schaefer 100 atlas, a reference brain and synthetic fMRI signals. The viewer and eight projections use the same 200 displayed edges at |r| ≥ 0.30. The complete matrix is not thresholded. No participant data or source paths are embedded in these images.

## Detailed pipeline

`processing.dataflow.json` is the editable specification for the compact four-column, twelve-node pipeline, drawn with **archify skill 2.16**. `processing.html` is the checked interactive artifact; `processing.svg` and `processing.png` are its clean viewer exports, without toolbar, page header or footer. The skill attribution is inside the diagram.

| Diagram stage | Source of behavior |
| --- | --- |
| External raw-image preparation | `brainfc.preprocessing.dicom_plan`, `fmriprep_plan`; external tools and report inspection are required. |
| Image and table loading | `brainfc.io`, `brainfc.imaging`; CIFTI axes and volume labels are checked; surface vertex correspondence remains a caller declaration. |
| ROI means and signal order | `volume_timeseries`, `cifti_timeseries`, `gifti_timeseries`, `numeric_table`; no spatial registration is estimated. |
| Frame mask and joint cleaning | `brainfc.pipeline._confounds`, `extract_connectome`; initial discard precedes Nilearn joint filtering/confound regression with `sample_mask`. |
| Connectivity | Pearson sample correlation, Spearman rank correlation, or normalized Ledoit–Wolf precision; clipped Fisher-z is separate. |
| Full result and display subset | `Connectome`, `brainfc.export`, `brainfc.plotting.edges_of`; frontend selection is shared by 3D and eight projections. |

The three input boxes are alternative entry points, not a requirement to supply all formats. Confounds and censoring settings are optional and must match the upstream processing history. Correlation display thresholds are not significance thresholds. Coordinates and a declared space are required for 3D. The raw fMRIPrep chain is not claimed as fully validated in this release.

The compact receipt in `processing.receipt.json` records specification/artifact hashes, deterministic validation, browser coverage, and a separate visual review. It contains no workstation paths. To reproduce the diagram with archify installed, run its `deliver dataflow` and `visual-check` commands against this specification. `frontend/capture-readme.cjs` exports its SVG/PNG and optionally captures a supplied BrainFC report.

Archify is distributed under MIT; see `ARCHIFY-LICENSE`. See the repository `NOTICE` for the remaining software credits.
