"""Validated HTTP request/response contracts; scientific defaults come from Config."""

from dataclasses import fields
from typing import Any, Literal, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from ..models import Config


class RequestModel(BaseModel):
    """Reject unknown request keys instead of silently ignoring misspellings."""

    model_config = ConfigDict(extra="forbid")


class _ConfigRequest(RequestModel):
    @model_validator(mode="after")
    def scientific_settings(self):
        Config(**self.model_dump())
        return self


_DESCRIPTIONS = {
    "t_r": "Repetition time in seconds; null infers from scan JSON/header; conflicts are rejected.",
    "high_pass": "High-pass cutoff in Hz; null disables. Requires TR and cutoff below Nyquist.",
    "low_pass": "Low-pass cutoff in Hz; null disables. Must exceed high_pass when both are set.",
    "detrend": "Remove linear trends through Nilearn signal.clean.",
    "standardize": "Sample z-score of cleaned ROI time series (ddof=1).",
    "discard": "Number of initial original frames to remove, integer >=0.",
    "fd_threshold": "Censor FD > cutoff in mm, also undefined first FD; null disables FD censoring.",
    "min_samples": "Minimum retained frames (>=3), not a statistical power criterion.",
    "method": "pearson, spearman, or partial (Ledoit-Wolf shrinkage precision).",
    "data_space": "Exact source template name. All image inputs require a known space.",
    "atlas_space": "Atlas template name, must match source when atlas is supplied.",
    "preprocessed": "Explicit declaration that image motion correction/registration are complete.",
    "confound_columns": "Columns to regress; null selects complete motion6 + available WM/CSF.",
    "table_header": "Text first non-comment row contains ROI names; ignored for NPY/NPZ/MAT.",
    "transpose": "Transpose table input to time x ROI, discarding text column names.",
    "variable": "NPZ/MAT 2D numeric variable name; null requires one unambiguous variable.",
}
_types = get_type_hints(Config)
ConfigRequest = create_model(
    "ConfigRequest",
    __base__=_ConfigRequest,
    **{
        f.name: (_types[f.name], Field(default=f.default, description=_DESCRIPTIONS[f.name]))
        for f in fields(Config)
    },
)


class Guidance(RequestModel):
    """Optional GUI confirmation record; programmatic callers may omit it."""

    # The GUI also records acquisition comparisons; preserve those provenance fields.
    model_config = ConfigDict(extra="allow")
    dataset: str = Field(description="Catalog dataset id, e.g. custom or adni.")
    variant: str = Field(description="Exact variant id returned by /api/presets.")
    input_kind: str = Field(default="auto", description="Original route, such as auto or raw-bids.")
    source_confirmed: bool = False
    spatial_confirmed: bool = False
    denoise_confirmed: bool = False
    review_confirmed: bool = False
    confounds_decision: str | None = Field(
        default=None, description="upstream or skip when confounds absent."
    )
    reference_decision: str | None = Field(default=None, description="skip when reference absent.")
    raw_qc_confirmed: bool = False


class ExtractionRequest(RequestModel):
    """One source run, optional companion paths and scientific settings."""

    source: str = Field(min_length=1, description="Absolute or server-relative path to one fMRI/ROI file.")
    atlas: str | None = Field(default=None, description="Integer-label atlas in the source space.")
    rois: str | None = Field(
        default=None, description="ROI mapping CSV/TSV; exact IDs and optional RAS+ coordinates."
    )
    mask: str | None = Field(default=None, description="Same-space volume mask; positive voxels retained.")
    reference: str | None = Field(
        default=None, description="Display-only same-space brain mask/skull-stripped T1."
    )
    confounds: str | None = Field(
        default=None, description="Headered confounds TSV/CSV with all original frames."
    )
    config: ConfigRequest = Field(default_factory=ConfigRequest)
    guidance: Guidance | None = None


class PreflightRequest(ExtractionRequest):
    """Progressive validation; does not calculate the connectivity matrix."""

    stage: Literal["input", "spatial", "review"] = "review"


class PathRequest(RequestModel):
    """A local source path, not a URL or uploaded byte array."""

    path: str = Field(min_length=1, description="Local file for inspect; directory for discover.")


class SuggestionsRequest(RequestModel):
    """Inspect one file and infer conservative defaults."""

    source: str = Field(min_length=1)
    overrides: ConfigRequest | None = Field(
        default=None, description="Only explicitly supplied fields override inference."
    )


class AtlasRequest(RequestModel):
    """Queue an explicit supported-atlas download into the workspace cache."""

    name: Literal["schaefer100", "schaefer200", "schaefer400", "aal116"]


class DicomRequest(RequestModel):
    """Plan/run external conversion; both paths are local directories."""

    source: str = Field(min_length=1, description="Existing DICOM source directory.")
    output: str = Field(min_length=1, description="New directory, outside and separate from source.")


class PreprocessRequest(RequestModel):
    """Pinned Docker fMRIPrep parameters; no patient data are uploaded by this API."""

    bids_dir: str = Field(min_length=1, description="Existing raw BIDS directory with BOLD/T1.")
    output_dir: str = Field(
        min_length=1, description="Separate derivatives directory; existing output may resume."
    )
    license_file: str = Field(min_length=1, description="Existing FreeSurfer license path.")
    participant: str | None = Field(default=None, description="One subject label, with optional sub- prefix.")
    space: str = "MNI152NLin6Asym"
    image: str = "nipreps/fmriprep:25.2.5"


class JobState(BaseModel):
    """Persistent job state, returned immediately on submission and during polling."""

    model_config = ConfigDict(extra="allow")
    id: str
    status: Literal["queued", "running", "complete", "failed", "interrupted"]
    message: str
    kind: Literal["extract", "demo", "atlas", "dicom", "preprocess"]
    example_kind: Literal["rest01", "synthetic"] | None = Field(
        default=None, description="Example identity for demo jobs; old jobs may omit this field."
    )
    error_type: str | None = None
    result_dir: str | None = None
    qc: dict[str, Any] | None = None
    atlas: dict[str, Any] | None = None


class CommandResponse(BaseModel):
    """Inspectable command argv plus shell renderings; no execution on plan routes."""

    argv: list[str]
    description: str
    powershell: str
    posix: str
    inventory: dict[str, Any] | None = None


class UploadResponse(BaseModel):
    path: str = Field(description="Server-local saved path; use as source or companion in later requests.")
    size_bytes: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    workspace: str


class SetupResponse(BaseModel):
    conversion_output: str
    preprocessing_output: str
    license_file: str = Field(description="Existing FS_LICENSE path or empty string.")


class RunRecord(BaseModel):
    bold: str
    confounds: str | None
    mask: str | None
    subject: str | None
    session: str | None
    task: str | None
    run: str | None
    sidecar: str | None
    t_r: float | None
    space: str | None


class InputInfo(BaseModel):
    """Format-dependent inspection/preflight fields; absent fields are omitted."""

    model_config = ConfigDict(extra="allow")
    format: Literal["directory", "volume", "cifti", "gifti", "timeseries-table"]
    path: str | None = None
    size_bytes: int | None = None
    sidecar: str | None = None
    t_r: float | None = None
    space: str | None = None
    shape: list[int] | None = None
    affine: list[list[float]] | None = None
    orientation: list[str] | None = None
    units: list[str] | None = None
    axes: list[str] | None = None
    arrays: list[list[int]] | None = None
    variables: dict[str, list[int]] | None = None
    runs: list[RunRecord] | None = None
    n_frames: int | None = None
    n_rois: int | None = None
    needs_atlas: bool | None = None
    header_t_r: float | None = None
    tr_source: str | None = None
    n_retained: int | None = None
    confound_columns: list[str] | None = None
    effective_tr: float | None = None
    validated: bool | None = None


class SuggestionsResponse(BaseModel):
    info: InputInfo
    config: dict[str, Any] = Field(
        description="Only inferred/overridden Config fields, not a full default Config."
    )
    paths: dict[str, str] = Field(
        description="Matched atlas/rois/confounds/mask/reference paths when available."
    )
    notes: list[str]


class PresetVariant(BaseModel):
    id: str
    name: str
    source: str
    t_r: float | None
    notes: str
    upstream: str
    input_kind: str


class DatasetEntry(BaseModel):
    id: str
    name: str
    variants: list[PresetVariant]


class PresetsResponse(BaseModel):
    version: str = Field(description="Catalog date, independent of software version.")
    datasets: list[DatasetEntry]
    policy: str
