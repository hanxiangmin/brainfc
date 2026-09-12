"""Alignment and motion reports for local review, not automatic study approval."""

import html
import json

import nibabel as nib
import numpy as np


def write_qc(directory, template_path, affine, bold, mask, confounds, qc):
    """Write qc.html, alignment.png and motion.png into an existing output directory.

    Internal report helper: image geometry is prevalidated by preprocess_fmri.
    Shows native T1 mask, native BOLD-to-T1 edges, template-to-T1 edges, mean BOLD
    coverage, tissue-mask contours and all-frame FD/raw-unit DVARS. Images have
    fixed anatomical world-coordinate cuts; outputs contain sensitive anatomy.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from nilearn import plotting

    root = directory
    fig = plt.figure(figsize=(15, 12), facecolor="white")
    axes = [fig.add_subplot(4, 1, i + 1) for i in range(4)]
    t1 = str(root / "work/t1_brain.nii.gz")
    d = plotting.plot_anat(t1, axes=axes[0], display_mode="ortho", cut_coords=(0, -20, 20),
                           title="T1 brain mask / tissue estimates (native anatomy)", annotate=True)
    d.add_contours(str(root / "work/t1_mask.nii.gz"), levels=[.5], colors=["#0072bc"])
    d = plotting.plot_anat(t1, axes=axes[1], display_mode="ortho", cut_coords=(0, -20, 20),
                           title="BOLD edges on T1: inspect ventricles and brain outline")
    d.add_edges(str(root / "work/bold_reference_t1.nii.gz"), color="#0072bc")
    d = plotting.plot_anat(str(template_path), axes=axes[2], display_mode="ortho", cut_coords=(0, -20, 20),
                           title="Subject T1 edges on MNI152NLin6Asym template")
    d.add_edges(str(root / "work/t1_mni.nii.gz"), color="#0072bc")
    mean = nib.Nifti1Image(np.asarray(bold.mean(axis=-1), dtype="float32"), affine)
    d = plotting.plot_anat(mean, axes=axes[3], display_mode="ortho", cut_coords=(0, -20, 20),
                           title="Mean BOLD in MNI: WM (blue), CSF (cyan), coverage")
    d.add_contours(str(root / "white_matter_mask.nii.gz"), levels=[.5], colors=["#0072bc"])
    d.add_contours(str(root / "csf_mask.nii.gz"), levels=[.5], colors=["#50b9dd"])
    fig.savefig(root / "alignment.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(12, 4.5), sharex=True, layout="constrained")
    axes[0].plot(confounds.framewise_displacement, color="#005b9f", lw=1.2)
    axes[0].set_ylabel("ANTs FD (mm)")
    axes[1].plot(confounds.dvars, color="#0072bc", lw=1.2)
    axes[1].set_ylabel("DVARS (raw units)")
    axes[1].set_xlabel("Original frame (zero-based)")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=.15)
    fig.savefig(root / "motion.png", dpi=140)
    plt.close(fig)
    text = html.escape(json.dumps(qc, ensure_ascii=False, indent=2))
    (root / "qc.html").write_text("""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>BrainFC · 预处理质控</title><style>body{font:16px/1.7 system-ui;background:#f3f7fb;color:#153a58;
max-width:1200px;margin:30px auto;padding:24px}img{width:100%;background:white;border-radius:12px}
pre{white-space:pre-wrap;background:white;padding:20px}h1{color:#005b9f}</style>
<h1>预处理质控</h1><p>逐项检查：脑提取是否保留完整脑组织；BOLD 与 T1 的脑室、皮层边界是否对齐；
标准空间是否匹配；WM / CSF 是否落在正确组织；头动和 DVARS 是否出现明显突变。
模板传播得到的脑掩膜重叠分数不属于独立精度验证。确认后再进入功能连接提取。</p>
<img src="alignment.png" alt="配准与组织分割叠加"><img src="motion.png" alt="头动与信号变化">
<h2>实际处理与质量记录</h2><pre>""" + text + "</pre></html>", encoding="utf-8")
