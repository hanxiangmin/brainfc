"""Python/ANTs volumetric fMRI preprocessing; no MATLAB, Docker or command runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from contextlib import contextmanager
from importlib.metadata import version
import json
import os
from pathlib import Path
import time
import threading

import nibabel as nib
import numpy as np
import pandas as pd
from scipy.ndimage import binary_erosion, binary_fill_holes, label

from ..models import Config, InputError
from .templates import SPACE, ASSETS, fetch_template
from .temporal import slice_time_correct

MOTION_COLUMNS = tuple(f"motion_matrix_{i}{j}" for i in range(3) for j in range(3)) + tuple(
    f"motion_offset_{a}" for a in "xyz"
)
CONFOUND_COLUMNS = MOTION_COLUMNS + ("white_matter", "csf")
_ANTS_LOCK = threading.RLock()


@dataclass(frozen=True)
class PreprocessConfig:
    """Settings for one raw single-echo BOLD run and a matching whole-head T1.

    t_r is seconds, inferred from JSON/header when None; disagreement is rejected.
    slice_timing='auto' corrects when timing AND axis are known, otherwise stops
    for an explicit 'skip' decision. 'require' always requires valid timing.
    slice_axis optionally supplies 0/1/2 when neither JSON nor header specifies
    the slice dimension; conflicting declarations are rejected. reference is a
    fraction of TR in [0,1), default 0.5. discard removes no spatial input frames:
    it excludes leading frames from the reference and is passed to extraction.
    smoothing_fwhm is optional spatial Gaussian FWHM in mm (default 0, disabled);
    nuisance signals always use unsmoothed data. seed is an ANTs registration seed;
    floating-point results are not guaranteed bitwise identical across platforms.

    Adult MNI152NLin6Asym 2 mm is fixed to match the default Schaefer atlas.
    No susceptibility distortion correction, multi-echo combination, surface
    reconstruction or pediatric template is implemented. These are reported as
    unperformed, never inferred from a dataset name. Visual QC remains necessary.
    """

    t_r: float | None = None
    slice_timing: str = "auto"
    slice_axis: int | None = None
    reference: float = 0.5
    discard: int = 0
    smoothing_fwhm: float = 0.0
    seed: int = 42

    def __post_init__(self):
        if self.slice_timing not in {"auto", "require", "skip"}:
            raise InputError("slice_timing must be auto, require or skip.")
        if self.slice_axis is not None and (type(self.slice_axis) is not int or self.slice_axis not in (0, 1, 2)):
            raise InputError("slice_axis must be null, 0, 1 or 2.")
        if self.t_r is not None and (isinstance(self.t_r, bool) or not np.isfinite(self.t_r) or self.t_r <= 0):
            raise InputError("t_r must be positive seconds.")
        for name in ("reference", "smoothing_fwhm"):
            value = getattr(self, name)
            if isinstance(value, bool) or not np.isfinite(value) or value < 0:
                raise InputError(f"{name} must be finite and nonnegative.")
        if self.reference >= 1:
            raise InputError("reference must be a fraction of TR in [0,1).")
        for name in ("discard", "seed"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise InputError(f"{name} must be a nonnegative integer.")


@dataclass
class PreprocessedRun:
    """Completed spatial preprocessing with paths, metadata, and a QC report.

    directory is the output Path; run is the discoverable BOLD/companions mapping;
    qc and provenance record actual methods. Completion does not certify visual
    alignment or suitability for a study. Original temporal indices are retained.
    """

    directory: Path
    run: dict
    qc: dict
    provenance: dict

    def extract(self, atlas="schaefer100", *, config=None, qc_reviewed=False, progress=None):
        """Extract a connectome after inspecting qc.html and setting qc_reviewed=True.

        atlas is a fetch_atlas name in MNI152NLin6Asym (Schaefer100/200/400).
        config is Config or None. None uses 0.01–0.1 Hz filtering, detrending,
        standardization and recorded motion-matrix/WM/CSF regression; no FD
        threshold is assumed. TR, spaces and the spatial discard count are bound
        to the actual run. Conflicting TR/spaces/columns or discard are rejected.
        Returns Connectome, including the preprocessing provenance and QC. The
        proposed defaults are BrainFC choices, not official dataset parameters.
        """
        from ..atlases import fetch_atlas
        from ..pipeline import extract_connectome

        if not qc_reviewed:
            raise InputError("Inspect qc.html, then explicitly set qc_reviewed=True.")
        cfg = config or Config(high_pass=0.01, low_pass=0.1, discard=self.provenance["config"]["discard"])
        for key in ("data_space", "atlas_space"):
            if getattr(cfg, key) not in (None, SPACE):
                raise InputError("Extraction must use the actual MNI152NLin6Asym space.")
        if cfg.t_r is not None and not np.isclose(cfg.t_r, self.run["t_r"], rtol=1e-4, atol=1e-4):
            raise InputError("Extraction TR conflicts with preprocessed BOLD.")
        if cfg.discard != self.provenance["config"]["discard"]:
            raise InputError("Use the same discard setting as spatial preprocessing.")
        cfg = replace(cfg, t_r=self.run["t_r"], data_space=SPACE, atlas_space=SPACE,
                      preprocessed=True, confound_columns=cfg.confound_columns or CONFOUND_COLUMNS)
        info = fetch_atlas(atlas)
        if info["space"] != SPACE:
            raise InputError("The requested atlas uses a different template space.")
        result = extract_connectome(self.run["bold"], atlas=info["atlas"], rois=info["rois"],
                                    confounds=self.run["confounds"], mask=self.run["mask"],
                                    reference=self.run["mask"], config=cfg, progress=progress)
        result.provenance["raw_preprocessing"] = self.provenance
        result.provenance["raw_qc_reviewed"] = True
        result.qc["raw_preprocessing"] = self.qc
        result.qc["warnings"].extend(self.qc["limitations"])
        return result


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def load_preprocessed(directory):
    """Load a completed preprocessing folder and verify exported artifact hashes.

    directory must contain stages.json with status='complete', run.json, QC,
    preprocessing.json and output_hashes.json. Raises InputError for incomplete,
    modified, missing or escaping paths. Returns PreprocessedRun with paths
    rebound to the current directory, so completed folders can be moved. The
    original provenance retains original input/transform paths for traceability.
    Loading does not bypass .extract(qc_reviewed=True).
    """
    from ..pipeline import fingerprint
    root = Path(directory).expanduser().resolve()
    if not (root / "stages.json").is_file() or json.loads((root / "stages.json").read_text(encoding="utf-8"))["status"] != "complete":
        raise InputError("Preprocessing is incomplete; inspect stages.json.")
    hashes = json.loads((root / "output_hashes.json").read_text(encoding="utf-8"))
    for name, digest in hashes.items():
        p = root / name
        if p.resolve().parent != root or not p.is_file() or fingerprint(p)["sha256"] != digest:
            raise InputError(f"Preprocessing artifact is missing or modified: {name}")
    run = json.loads((root / "run.json").read_text(encoding="utf-8"))
    for key in ("bold", "confounds", "mask", "reference", "sidecar"):
        name = Path(str(run[key]).replace("\\", "/")).name
        if name not in hashes:
            raise InputError("Preprocessing run refers to an unverified artifact.")
        run[key] = str(root / name)
    return PreprocessedRun(root, run, json.loads((root / "qc.json").read_text(encoding="utf-8")),
                           json.loads((root / "preprocessing.json").read_text(encoding="utf-8")))


def _check_image(path, dimensions):
    try:
        image = nib.load(str(path))
    except (OSError, nib.filebasedimages.ImageFileError) as exc:
        raise InputError(f"Cannot read a NIfTI image: {Path(path).name}") from exc
    if not isinstance(image, (nib.Nifti1Image, nib.Nifti2Image)) or len(image.shape) != dimensions:
        raise InputError(f"Expected a {dimensions}D NIfTI image: {Path(path).name}")
    if any(n < 4 for n in image.shape[:3]) or not np.isfinite(image.affine).all():
        raise InputError("Invalid image geometry.")
    if not (image.header["sform_code"] or image.header["qform_code"]):
        raise InputError("Raw NIfTI requires a valid qform or sform orientation.")
    if image.header["sform_code"] and image.header["qform_code"]:
        if not np.allclose(image.get_sform(), image.get_qform(), atol=1e-3, rtol=1e-5):
            raise InputError("qform and sform disagree; reconcile the original image geometry before processing.")
    if image.header.get_xyzt_units()[0] != "mm":
        raise InputError("Raw image spatial units must explicitly be millimetres.")
    directions = image.affine[:3, :3] / np.linalg.norm(image.affine[:3, :3], axis=0)
    if not np.allclose(directions.T @ directions, np.eye(3), atol=1e-4):
        raise InputError("Sheared NIfTI grids are unsupported by the ANTs/ITK adapter.")
    return image


def discover_raw(bids_dir):
    """List raw BIDS BOLD/T1 candidate pairs within the same subject/session.

    Returns mappings of bold, t1w, same-stem sidecar (or None), and a relative
    label. Excludes derivatives and already-preprocessed filenames. Multiple T1
    candidates remain separate choices; no contrast or subject identity is
    inferred. Session BOLD may use a T1 in the subject-level anat directory when
    its session has none. BIDS JSON inheritance is not resolved here: materialize
    an acquisition sidecar before preprocessing when metadata are inherited.
    Raises InputError if the directory or eligible pairs are absent.
    """
    root = Path(bids_dir).expanduser().resolve()
    if not root.is_dir():
        raise InputError("Raw BIDS directory does not exist.")
    runs = []
    for path in sorted(root.rglob("*_bold.nii*")):
        if path.parent.name != "func" or "derivatives" in path.relative_to(root).parts or "_desc-preproc_" in path.name:
            continue
        scope = path.parent.parent
        if not scope.name.startswith(("sub-", "ses-")):
            continue
        candidates = sorted((scope / "anat").glob("*_T1w.nii*"))
        if not candidates and scope.name.startswith("ses-"):
            candidates = sorted((scope.parent / "anat").glob("*_T1w.nii*"))
        sidecar = Path(str(path).removesuffix(".gz")).with_suffix(".json")
        for t1 in candidates:
            runs.append({"bold": str(path), "t1w": str(t1), "sidecar": str(sidecar) if sidecar.exists() else None,
                         "label": f"{path.relative_to(root)} · {t1.name}"})
    if not runs:
        raise InputError("No matching raw BOLD/T1 candidates in subject/session anat/func directories.")
    return runs


def inspect_raw(bold, t1w, *, sidecar=None, config=None):
    """Read raw NIfTI geometry and acquisition metadata without running algorithms.

    bold is one 4D single-echo NIfTI; t1w is a matching 3D T1. Paths must exist.
    sidecar is optional JSON; otherwise the BOLD's same-stem JSON is read. BIDS
    inherited metadata must first be resolved into a sidecar. config defaults to
    PreprocessConfig. Returns geometry, resolved seconds/axis/times, readiness,
    missing confirmations, and the planned steps. No subject identity is inferred.
    Invalid/conflicting TR, timing or orientation raises InputError. Missing slice
    timing/axis is returned as a blocker unless explicitly skipped.
    """
    cfg = config or PreprocessConfig()
    b, t = _check_image(bold, 4), _check_image(t1w, 3)
    if b.shape[-1] < 20 or cfg.discard >= b.shape[-1] - 19:
        raise InputError("At least 20 BOLD frames must remain after discard.")
    js = Path(sidecar) if sidecar else Path(str(bold).removesuffix(".gz")).with_suffix(".json")
    meta = json.loads(js.read_text(encoding="utf-8-sig")) if js.is_file() else {}
    if sidecar and not js.is_file():
        raise InputError("Specified acquisition JSON does not exist.")
    time_units = b.header.get_xyzt_units()[1]
    scale = {"sec": 1, "msec": .001, "usec": .000001}.get(time_units)
    header_tr = float(b.header.get_zooms()[3])*scale if scale else None
    choices = [v for v in (cfg.t_r, meta.get("RepetitionTime"), header_tr) if v is not None]
    if not choices or any(not np.isfinite(v) or v <= 0 for v in choices):
        raise InputError("Supply a positive TR in seconds from the acquisition record.")
    if not np.allclose(choices, choices[0], rtol=1e-4, atol=1e-4):
        raise InputError("TR disagrees between JSON, image header or explicit setting; verify the acquisition.")
    if "VolumeTiming" in meta:
        raise InputError("Variable-volume timing is not supported in this constant-TR pipeline.")
    tr = float(choices[0])
    direction = meta.get("SliceEncodingDirection")
    if direction is not None and direction not in {"i", "i-", "j", "j-", "k", "k-"}:
        raise InputError("Invalid SliceEncodingDirection.")
    axes = [a for a in (cfg.slice_axis, "ijk".index(direction[0]) if direction else None,
                        b.header.get_dim_info()[2]) if a is not None]
    if len(set(axes)) > 1:
        raise InputError("Slice dimension disagrees between JSON, NIfTI and explicit setting.")
    axis = axes[0] if axes else None
    times = meta.get("SliceTiming")
    if times is not None:
        times = np.asarray(times, dtype=float)
        if times.ndim != 1 or not np.isfinite(times).all() or np.any((times < 0) | (times >= tr)):
            raise InputError("SliceTiming must be a vector of seconds in [0, TR).")
        if axis is not None and len(times) != b.shape[axis]:
            raise InputError("SliceTiming length disagrees with the declared slice dimension.")
        if direction and direction.endswith("-"):
            times = times[::-1]
    missing = []
    if cfg.slice_timing != "skip":
        if times is None:
            missing.append("缺少切片采集时间；补充采集 JSON，或明确跳过层间时间校正。")
        if axis is None:
            missing.append("缺少切片维度；确认原始 NIfTI 的切片维度，或跳过层间时间校正。")
    return {"bold": str(Path(bold).resolve()), "t1w": str(Path(t1w).resolve()),
            "shape": list(b.shape), "t1_shape": list(t.shape), "t_r": tr,
            "slice_axis": axis, "slice_times": times.tolist() if times is not None else None,
            "slice_timing_applied": cfg.slice_timing != "skip" and not missing,
            "sidecar": str(js.resolve()) if js.exists() else None,
            "ready": not missing, "missing": missing, "space": SPACE,
            "steps": ["核对采集参数", "层间时间校正" if cfg.slice_timing != "skip" else "跳过层间时间校正",
                      "刚体头动校正", "T1 偏置校正与脑提取", "组织分割", "BOLD 与 T1 配准",
                      "标准空间配准与重采样", "运动 / WM / CSF 混杂与质控", "检查质控后提取功能连接"]}


def _ants():
    # Set only a missing value, before loading ITK. Respect the user's environment.
    os.environ.setdefault("ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS", "4")
    import ants
    return ants


@contextmanager
def _ants_session(seed):
    # ANTsPy 0.6.3 no longer consumes registration(random_seed=...). Its
    # supported package configuration sets --random-seed. Serialize our calls
    # and restore package state; do not enable its global RNG/thread overrides.
    with _ANTS_LOCK:
        ants = _ants()
        before = (ants.config._deterministic, ants.config._random_seed)
        ants.config.set_ants_deterministic(on=False, seed_value=seed)
        try:
            yield ants
        finally:
            ants.config._deterministic, ants.config._random_seed = before


def _like(ants, array, reference):
    return ants.from_numpy(np.asarray(array, dtype=np.float32), origin=reference.origin,
                           spacing=reference.spacing, direction=reference.direction)


def _largest(mask):
    components, n = label(mask)
    if not n:
        raise InputError("Brain mask is empty.")
    sizes = np.bincount(components.ravel())
    sizes[0] = 0
    return binary_fill_holes(components == np.argmax(sizes))


def _motion_table(ants, transforms, fd):
    rows = []
    for paths in transforms:
        if paths == "NA" or len(paths) != 1:
            raise InputError("A BOLD volume has no valid rigid motion transform.")
        tx = ants.read_transform(paths[0])
        pars, center = np.asarray(tx.parameters), np.asarray(tx.fixed_parameters[:3])
        matrix = pars[:9].reshape(3, 3)
        if not np.allclose(matrix.T @ matrix, np.eye(3), atol=1e-3) or np.linalg.det(matrix) < 0:
            raise InputError("Motion correction returned a non-rigid transform.")
        rows.append(np.r_[matrix.ravel(), pars[9:12] + center - matrix @ center])
    frame = pd.DataFrame(rows, columns=MOTION_COLUMNS)
    frame["framewise_displacement"] = np.asarray(fd, dtype=float)
    frame.loc[0, "framewise_displacement"] = np.nan
    return frame


def preprocess_fmri(bold, t1w, output, *, sidecar=None, config=None, t1_mask=None,
                    template_dir=None, progress=None):
    """Preprocess one single-echo run entirely through installed Python libraries.

    Parameters
    ----------
    bold, t1w : str or pathlib.Path
        Raw 4D BOLD and matching whole-head 3D T1 in mm, with valid NIfTI geometry.
    output : str or pathlib.Path
        New directory; never reuse an existing directory or place inputs inside it.
    sidecar : str or pathlib.Path or None
        Acquisition JSON. None reads the BOLD's same-stem JSON. See inspect_raw.
    config : PreprocessConfig or None
        Defaults to PreprocessConfig(); unknown slice timing requires an explicit
        skip decision. Conflicting metadata stops before image processing.
    t1_mask : str or pathlib.Path or None
        Optional independently reviewed T1 brain mask on the exact T1 grid.
        None uses whole-head template registration to propagate the template mask.
        Atlas-derived masks require visual QC and are not independent validation.
    template_dir : str or pathlib.Path or None
        Cache for the fixed, checksum-verified adult MNI152NLin6Asym 2 mm template.
    progress : callable(str) or None
        Optional synchronous progress message callback.

    Returns
    -------
    PreprocessedRun
        Standard-space BOLD, brain/tissue masks, all-frame confounds, saved ANTs
        transforms, acquisition JSON, provenance, stage record, QC PNG/HTML.
        Call .extract(qc_reviewed=True) after reviewing the alignment report.

    Notes
    -----
    Fourier slice timing → ANTs rigid motion → T1 N4 → atlas-mask propagation
    (unless mask provided) → Atropos 3-class tissue estimation → brain SyN to MNI
    → rigid BOLD-to-T1 → composed per-frame resampling (linear, once from the
    slice-time-corrected source) → optional Gaussian smoothing. WM/CSF signals
    use unsmoothed data. FD is ANTs generalized FD at fdOffset=50 mm, not Power FD.
    No SDC or slice-to-volume correction. No claim of numerical SPM equivalence.
    Failures preserve a failed stage record and partial outputs for inspection;
    incomplete outputs are never returned as a successful PreprocessedRun.
    """
    from ..pipeline import fingerprint
    from .._version import __version__
    from .quality import write_qc

    cfg = config or PreprocessConfig()
    info = inspect_raw(bold, t1w, sidecar=sidecar, config=cfg)
    if not info["ready"]:
        raise InputError(" ".join(info["missing"]))
    dest = Path(output).expanduser().resolve()
    for item in (bold, t1w, sidecar, t1_mask):
        if item and (Path(item).resolve() == dest or dest in Path(item).resolve().parents):
            raise InputError("Output must not contain an input file.")
    if dest.exists():
        raise FileExistsError("Preprocessing requires a new output directory.")
    if t1_mask:
        mask_nii, t1_nii = _check_image(t1_mask, 3), nib.load(str(t1w))
        if mask_nii.shape != t1_nii.shape or not np.allclose(mask_nii.affine, t1_nii.affine, atol=1e-4):
            raise InputError("The independent T1 mask must be on the exact T1 grid.")
    templates = fetch_template(template_dir)
    dest.mkdir(parents=True)
    work = dest / "work"
    work.mkdir()
    txdir = dest / "transforms"
    txdir.mkdir()
    stages = []
    start = time.monotonic()

    def say(message):
        stages.append({"message": message, "elapsed_seconds": round(time.monotonic() - start, 2)})
        _json(dest / "stages.json", {"status": "running", "stages": stages})
        if progress:
            progress(message)

    try:
        with _ants_session(cfg.seed) as ants:
            say("1/8 核对原始信号与层间时间")
            nii = nib.load(str(bold))
            arr = nii.get_fdata(dtype=np.float32)
            if not np.isfinite(arr).all() or any(np.var(arr[..., k]) <= 0 for k in range(arr.shape[-1])):
                raise InputError("BOLD contains nonfinite values or an empty/constant volume.")
            t1data = nib.load(str(t1w)).get_fdata(dtype=np.float32)
            if not np.isfinite(t1data).all() or np.var(t1data) <= 0:
                raise InputError("T1 contains nonfinite values or no intensity variation.")
            del t1data
            if info["slice_timing_applied"]:
                arr = slice_time_correct(arr, info["slice_times"], info["t_r"],
                                         axis=info["slice_axis"], reference=cfg.reference)
            # Fresh headers avoid copying NIfTI free text into derivatives. This does
            # not remove identifying anatomy; outputs remain private by default.
            native_path = work / "bold_timing.nii"
            fresh = nib.Nifti1Image(arr, nii.affine)
            fresh.header.set_xyzt_units("mm", "sec")
            fresh.header.set_zooms((*nii.header.get_zooms()[:3], info["t_r"]))
            nib.save(fresh, native_path)
            del arr, fresh
            series = ants.image_read(str(native_path))
            refdata = series.numpy()[..., cfg.discard:].mean(axis=-1)
            ref = ants.from_numpy(refdata, origin=series.origin[:3], spacing=series.spacing[:3],
                                  direction=series.direction[:3, :3])
            say("2/8 估计每一帧的刚体头动")
            motion = ants.motion_correction(series, fixed=ref, type_of_transform="BOLDRigid",
                                             outprefix=str(txdir / "motion"),
                                             fdOffset=50, verbose=False)
            conf = _motion_table(ants, motion["motion_parameters"], motion["FD"])
            ref = _like(ants, motion["motion_corrected"].numpy()[..., cfg.discard:].mean(axis=-1), ref)
            del motion["motion_corrected"]
            ants.image_write(ref, str(work / "bold_reference.nii.gz"))

            say("3/8 T1 偏置校正与脑提取")
            head = ants.image_read(str(templates["head"]))
            tm = ants.image_read(str(templates["mask"]))
            template = head * tm
            t1 = ants.image_read(str(t1w))
            t1 = ants.resample_image(t1, (1.5, 1.5, 1.5), use_voxels=False, interp_type=0)
            t1 = ants.n4_bias_field_correction(t1, shrink_factor=2,
                                               convergence={"iters": [30, 20, 10], "tol": 1e-6})
            if t1_mask:
                bm = ants.resample_image_to_target(ants.image_read(str(t1_mask)), t1, interp_type="nearestNeighbor")
                mask_method = "independent supplied T1 mask"
            else:
                initial = ants.registration(head, t1, type_of_transform="SyN", reg_iterations=(60, 40, 20),
                                            outprefix=str(txdir / "head_to_template_"))
                bm = ants.apply_transforms(t1, tm, initial["invtransforms"],
                                           interpolator="nearestNeighbor", whichtoinvert=[True, False])
                mask_method = "template mask propagated via inverse whole-head SyN; not independent QC"
            bm = _like(ants, _largest(bm.numpy() > .5), t1)
            t1 = ants.n4_bias_field_correction(t1, mask=bm, shrink_factor=2,
                                               convergence={"iters": [30, 20, 10], "tol": 1e-6}) * bm
            ants.image_write(t1, str(work / "t1_brain.nii.gz"))
            ants.image_write(bm, str(work / "t1_mask.nii.gz"))

            say("4/8 T1 组织分割与标准空间配准")
            seg = ants.atropos(a=t1, x=bm, i="KMeans[3]", m="[0.2,1x1x1]", c="[5,0]")
            labels = seg["segmentation"].numpy()
            means = {k: float(t1.numpy()[labels == k].mean()) for k in (1, 2, 3)}
            if not np.isfinite(list(means.values())).all():
                raise InputError("T1 tissue segmentation did not produce three finite classes.")
            order = sorted(means, key=means.get)
            reg = ants.registration(template, t1, type_of_transform="SyN", mask=tm,
                                    reg_iterations=(60, 40, 20),
                                    outprefix=str(txdir / "t1_to_template_"))
            ants.image_write(reg["warpedmovout"], str(work / "t1_mni.nii.gz"))

            say("5/8 BOLD 与 T1 刚体配准")
            # Nilearn's EPI mask is an explicit signal-coverage heuristic, not a T1
            # skull-stripper. The visual QC report shows the resulting alignment.
            from nilearn.masking import compute_epi_mask
            epi_nii = compute_epi_mask(str(work / "bold_reference.nii.gz"), opening=1)
            nib.save(epi_nii, work / "bold_mask.nii.gz")
            epi_mask = ants.image_read(str(work / "bold_mask.nii.gz"))
            if epi_mask.sum() < 100:
                raise InputError("Cannot estimate a nonempty BOLD signal mask.")
            coreg = ants.registration(t1, ref * epi_mask, type_of_transform="Rigid",
                                      aff_iterations=(1000, 500, 250, 100),
                                      outprefix=str(txdir / "bold_to_t1_"))
            ants.image_write(coreg["warpedmovout"], str(work / "bold_reference_t1.nii.gz"))
            chain = reg["fwdtransforms"] + coreg["fwdtransforms"]
            standard_mask = ants.apply_transforms(template, epi_mask, chain, interpolator="nearestNeighbor")
            allowed = (standard_mask.numpy() > .5) & (tm.numpy() > .5)
            coverage = float(allowed.sum() / (tm.numpy() > .5).sum())
            if coverage < .5:
                raise InputError(f"BOLD covers only {coverage:.1%} of the template brain; inspect registration/field of view.")

            say("6/8 合成变换并逐帧重采样到标准空间")
            # One final spatial interpolation per source frame: normalisation +
            # coregistration + motion. ANTs uses pull image transforms in LPS space.
            resampled = np.lib.format.open_memmap(work / "unsmoothed.npy", mode="w+", dtype="float32",
                                                  shape=(*template.shape, series.shape[-1]))
            for k, transforms in enumerate(motion["motion_parameters"]):
                volume = ants.slice_image(series, axis=3, idx=k)
                warp = ants.apply_transforms(template, volume, chain + transforms,
                                              interpolator="linear", singleprecision=True)
                values = warp.numpy()
                if not np.isfinite(values).all():
                    raise InputError(f"Nonfinite resampled signal at frame {k}.")
                resampled[..., k] = np.where(allowed, values, 0)
                if progress and k % 20 == 0:
                    progress(f"6/8 标准空间重采样：{k + 1}/{series.shape[-1]} 帧")
            resampled.flush()
            del series
            say("7/8 提取组织混杂、FD 与 DVARS")
            tissue_voxels = {}
            for name, tissue in (("csf", order[0]), ("white_matter", order[-1])):
                probability = seg["probabilityimages"][tissue - 1].numpy()
                native = _like(ants, binary_erosion(probability > .9, iterations=1), t1)
                mask = ants.apply_transforms(template, native, reg["fwdtransforms"], interpolator="nearestNeighbor")
                selected = (mask.numpy() > .5) & allowed
                if selected.sum() < 20:
                    raise InputError(f"Insufficient {name} voxels after segmentation/registration.")
                tissue_voxels[name] = int(selected.sum())
                conf[name] = resampled[selected].mean(axis=0)
                ants.image_write(_like(ants, selected, template), str(dest / f"{name}_mask.nii.gz"))
            signal = resampled[allowed]
            conf["dvars"] = np.r_[np.nan, np.sqrt(np.mean(np.diff(signal, axis=-1).astype(float) ** 2, axis=0))]
            conf["global_signal"] = signal.mean(axis=0)
            del signal
            stem = "sub-01_task-rest"
            bp = dest / f"{stem}_space-{SPACE}_desc-preproc_bold.nii.gz"
            mp = dest / f"{stem}_space-{SPACE}_desc-brain_mask.nii.gz"
            cp = dest / f"{stem}_desc-confounds_timeseries.tsv"
            jp = Path(str(bp).removesuffix(".nii.gz") + ".json")
            template_nii = nib.load(str(templates["head"]))
            nib.save(nib.Nifti1Image(allowed.astype("uint8"), template_nii.affine), mp)
            if cfg.smoothing_fwhm:
                from scipy.ndimage import gaussian_filter
                final = np.empty_like(resampled)
                for k in range(resampled.shape[-1]):
                    final[..., k] = gaussian_filter(resampled[..., k], cfg.smoothing_fwhm / np.sqrt(8*np.log(2)) / 2)
                final[~allowed] = 0
            else:
                final = resampled
            result_image = nib.Nifti1Image(final, template_nii.affine)
            result_image.header.set_xyzt_units("mm", "sec")
            result_image.header.set_zooms((2, 2, 2, info["t_r"]))
            nib.save(result_image, bp)
            conf.to_csv(cp, sep="\t", index=False, na_rep="n/a")
            limitations = ["No susceptibility-distortion correction (fieldmap/reverse-PE not implemented).",
                           "Atropos intensity-ordered tissue classes and registration require visual review.",
                           "Adult MNI152NLin6Asym template; validate suitability for age/anatomy.",
                           "Generalized ANTs FD (50 mm sampling offset), not Power FD."]
            if not info["slice_timing_applied"]:
                limitations.append("Slice-timing correction explicitly skipped.")
            warped_bm = ants.apply_transforms(template, bm, reg["fwdtransforms"], interpolator="nearestNeighbor")
            a, b = warped_bm.numpy() > .5, tm.numpy() > .5
            qc = {"visual_review_required": True, "bold_template_coverage": coverage,
                  "t1_mask_overlap_dice": float(2*(a & b).sum()/(a.sum()+b.sum())),
                  "t1_mask_independent": bool(t1_mask), "mask_method": mask_method,
                  "fd_mean_mm": float(conf.framewise_displacement.mean()),
                  "fd_max_mm": float(conf.framewise_displacement.max()), "tissue_voxels": tissue_voxels,
                  "n_frames": info["shape"][-1], "limitations": limitations}
            provenance = {"engine": "BrainFC Python / ANTsPy", "versions": {"brainfc": __version__, **{
                p: version(p) for p in ("antspyx", "nibabel", "numpy", "scipy", "nilearn")}},
                "config": asdict(cfg), "registration_seed_applied": ants.config._random_seed,
                "itk_threads_environment": os.environ.get("ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"),
                "resolved": {k: info[k] for k in ("t_r", "slice_axis", "slice_times", "slice_timing_applied")},
                "space": SPACE, "template_sha256": {k: v[1] for k, v in ASSETS.items()},
                "inputs": {k: fingerprint(p) for k, p in {"bold": bold, "t1w": t1w,
                           "sidecar": info["sidecar"], "t1_mask": t1_mask}.items() if p},
                "motion": {"method": "BOLDRigid", "confounds": "row-major rotation matrix and LPS offset t+c-Rc",
                           "fd": "ANTs generalized FD, fdOffset=50 mm; first row undefined"},
                "tissue": {"method": "Atropos KMeans[3], MRF [0.2,1x1x1], iterations [5,0]",
                           "csf_class": order[0], "wm_class": order[-1], "probability_threshold": .9, "erosion_voxels": 1},
                "normalization": "SyN (60,40,20); T1 work grid 1.5 mm; target 2 mm",
                "spatial_interpolation": "linear; per-frame motion + BOLD-to-T1 + T1-to-template composed",
                "susceptibility_distortion_correction": False, "confound_columns": list(CONFOUND_COLUMNS),
                "elapsed_seconds": round(time.monotonic()-start, 1)}
            _json(jp, {"RepetitionTime": info["t_r"], "TaskName": "rest", "SpatialReference": SPACE,
                       "SliceTimingCorrected": info["slice_timing_applied"], "BrainFCPreprocessing": "preprocessing.json"})
            _json(dest / "preprocessing.json", provenance)
            _json(dest / "qc.json", qc)
            run = {"bold": str(bp), "confounds": str(cp), "mask": str(mp), "reference": str(mp),
                   "sidecar": str(jp), "t_r": info["t_r"], "space": SPACE,
                   "confound_columns": list(CONFOUND_COLUMNS), "discard": cfg.discard}
            say("8/8 生成配准叠加与质量报告")
            write_qc(dest, templates["head"], template_nii.affine, resampled, allowed, conf, qc)
            _json(dest / "run.json", run)
            _json(dest / "output_hashes.json", {p.name: fingerprint(p)["sha256"] for p in
                  (bp, mp, cp, jp, dest / "preprocessing.json", dest / "qc.json", dest / "run.json")})
            _json(dest / "stages.json", {"status": "complete", "stages": stages})
            return PreprocessedRun(dest, run, qc, provenance)
    except Exception as exc:
        _json(dest / "stages.json", {"status": "failed", "stages": stages,
                                     "error_type": type(exc).__name__, "error": str(exc)})
        raise
