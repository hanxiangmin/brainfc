# UIH 样例的转换参数核验

本样例来自经数据提供者确认的静息态扫描。使用 dcm2niix v1.0.20260724 转换时，发现了两类元数据问题。

| 参数 | 原始证据 | 初始转换结果 | 样例采用值 |
| --- | --- | --- | --- |
| BOLD 回波时间 TE | 所有 150 个 DICOM 的 `(0018,0081)` 均为 23 ms | 0.000315 s | **0.023 s** |
| BOLD 有效回波间隔 | `1 / (28.86002886 × 110)` s | 0.000315 s | **保留 0.000315 s** |
| BOLD 总读出时间 | `0.000315 × (110−1)` s | 0.034335 s | **保留 0.034335 s** |
| T1 / 场图的总读出时间 | 转换器缺少 EPI 带宽时采用 AcquisitionDuration 的回退路径 | 271.785 / 103.55 s | **移除，不能当成 EPI 读出参数** |

设备文件中另一个标签 `(0018,9082) EffectiveEchoTime` 被写成约 0.315 ms，恰好对应回波间隔。该转换器版本在读取此标签后无条件覆盖已读取的 TE，随后除以 1000 写入 JSON。因此，这是输入标签冲突与转换器覆盖规则共同造成的错误，不是 BrainFC 计算相关矩阵时修改了 TE。[转换器对应代码](https://github.com/rordenlab/dcm2niix/blob/v1.0.20260724/console/nii_dicom.cpp#L7467)

已进行独立对照：在本地临时副本中只移除 `(0018,9082)`，确认 PixelData 的 SHA-256 不变，再用相同版本转换器执行，结果恢复为 **0.023 s**。该临时 DICOM 不包含在样例包中。总读出时间的异常则对应另一个明确的 UIH 回退分支。[对应代码](https://github.com/rordenlab/dcm2niix/blob/v1.0.20260724/console/nii_dicom_batch.cpp#L3472)

`examples/reconcile_uih_sidecar.py` 提供可复用的严格核验脚本：检查整个单一序列，只有匹配已确认的错误特征时才写入**新的** JSON。它拒绝多序列、非 UIH、增强型 DICOM、TE 不一致或未知冲突，不修改原始文件。需额外安装 `pydicom`。

```console
python examples/reconcile_uih_sidecar.py path/to/one_series converted.json reviewed.json
```

该脚本不做影像脱敏。场图的物理单位和缩放仍无充分证据，样例没有猜测 Hz/rad/s，也没有使用这些场图进行畸变校正。私有实验标记在同一体积的不同切片间出现 rest/active 混合，因此任务类别依据数据提供者确认，而非这些标记推断。

样例的具体处理步骤、脱敏范围和未执行的步骤见 [真实静息态样例](real-example.md)。
