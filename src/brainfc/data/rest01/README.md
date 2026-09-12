# rest01 — de-identified resting-state example

One participant, 150 frames, TR 2 s, TE 23 ms, 100 Schaefer parcels.
Data are provided as a software demonstration with the data provider's authorization.
No diagnosis, demographics, acquisition dates, DICOM identifiers or source paths are included.
The display mask contains binary brain tissue only, with no original MRI intensities.
Functional signals and brain anatomy remain; this is not a claim of irreversible anonymity.

The table contains spatially preprocessed ROI means, before temporal denoising.
BrainFC removes 5 initial frames, regresses 12 motion matrix/offset terms and WM/CSF means,
filters at 0.01–0.08 Hz, applies a 0.5 mm ANTs generalized-FD threshold, and computes Pearson FC.
ANTs generalized FD is not the Power FD formula. See example.json for exact settings and QC.
No slice-timing correction or susceptibility-distortion correction was performed.
This is a documented demonstration pipeline, not an fMRIPrep output or a clinical reference.

Usage (with a BrainFC build containing this sample):

    brainfc demo --kind rest01 --output my-rest-example

The separate local image bundle contains brain-only NIfTI images; large images and original
DICOM are not bundled with the Python package. These example data follow the repository's
Apache-2.0 license. Method/atlas references are listed in example.json.
The public release also excludes the individual T1/BOLD image bundle. See privacy-review.json
for the review scope and file hashes; the release checker rejects unreviewed sample files.
