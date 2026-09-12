# 输入格式、ROI 映射与空间

## 支持的输入契约

| 格式 | 信号维度 | 图谱/附加信息 |
|---|---|---|
| NIfTI `.nii/.nii.gz` | X×Y×Z×T | 同空间 3D 整数标签图谱；可选 mask、混杂、参考 |
| Analyze `.hdr/.img`、MGH/MGZ、AFNI HEAD/BRIK | 必须读成 4D | NiBabel 兼容读取；实际格式验证范围见版本验证记录 |
| CIFTI `.dtseries.nii` | SeriesAxis×BrainModelAxis | 完全一致灰坐标轴的单标签 `.dlabel.nii` |
| CIFTI `.ptseries.nii` | SeriesAxis×ParcelsAxis | 自带 ROI 名称顺序；不需要 atlas |
| GIFTI `.func.gii` | 一个顶点×时间数组，或逐帧顶点数组 | TIME_SERIES intent；同顶点对应的 `.label.gii` |
| CSV/TSV/TXT/1D | 默认 T×R | 只包含 ROI 信号，不含时间/索引/受试者列 |
| NPY | 2D 实数数组 | 不允许 pickle |
| NPZ/MAT | 指定的 2D 数值变量 | 无歧义时可推断；MAT v7.3/HDF5 不支持 |
| DICOM、原始 BIDS | 多文件序列/目录 | 先外部预处理，再传入已处理 run |

体积与表面影像均要求 `preprocessed=True` 和可确认的 `data_space`。表格时序不强制该声明。概率图谱、静态指标图、T1 单图、CIFTI dconn/pconn 不能作为 fMRI 时序。对称表格疑似 FC 时，GUI/preflight 拒绝；低层数值读取函数不会推断科学来源。

图像可能由多个配对文件组成：例如 Analyze 需要 hdr 与 img 都在本地。`provenance.inputs.source` 当前只哈希传给 source 的路径，不能代表所有配对文件的完整指纹；研究归档时另外保存这些配对文件。

## 文本规则

CSV 用逗号，TSV 用制表符，TXT/1D 用空白分隔；`#` 为注释。Python API 默认有表头；GUI 根据首个有效行是否全为数字推测表头。全数字 ROI ID 的表头有歧义，应显式设置 `table_header=True`。

不自动删除数值时间列、行号或表型列。无表头文件用 `table_header=False`；ROI×时间用 `transpose=True`，转置后不继续使用旧表头作为 ROI 名称。

## ROI 表

体积/标签表面图谱示例（实际保存为制表符分隔）：

```text
label_value  roi_id  name        x    y    z
3            ROI_A   Region A   -32  -20   40
17           ROI_B   Region B    32  -20   40
```

`roi_id` 唯一且非空；影像图谱需要 `label_value` 与真实标签完全对应。`name` 可省略，会使用图谱名或 `ROI {value}`；不要把 ROI 表行号当作体素标签。自定义 `x,y,z` 覆盖图谱质心，需一起提供有限值。

已分区时序表使用 `roi_id` 匹配真实列 ID/ParcelsAxis 名称，不需要 `label_value`。可选字段：`name, abbreviation, hemisphere, network, x, y, z`。映射必须没有多余或缺失 ROI；ROI 表的行顺序不会改变输入列或图谱提取顺序。

## 空间与单位

`MNI152NLin6Asym`、`MNIColin27` 是不同模板，不能简写为同一个 MNI 后混用。空间名称按字符串严格匹配。体积影像的 affine 决定坐标，要求有限、可逆；编码的 qform/sform 冲突会报错。米/微米单位拒绝，unknown 空间单位暂按 mm 并在体积提取结果中提醒。

坐标约定 RAS+、mm：x 正向为右、y 正向为前、z 正向为上。参考脑/mask/自定义 ROI 坐标的空间由调用者保证；库没有自动配准验证器。GIFTI 相同顶点数不等于实际一一对应，需同模板、半球和顶点顺序。

## TR 与 JSON

`t_r` 以秒计。NIfTI 已知秒/毫秒/微秒单位会换算；未知时间单位不能直接当作秒。CIFTI 主提取要求 SeriesAxis 单位 SECOND。JSON `RepetitionTime`、影像头与手动 TR 如有冲突，主处理拒绝。

`sidecar_path` 对 `.nii[.gz]` / `.dtseries.nii` / `.ptseries.nii` 替换末尾为 `.json`，其他格式追加 `.json`，如 `signals.tsv.json`。本库只读取相邻 JSON，没有完整 BIDS 继承实现。原始 BIDS 的继承由上游 fMRIPrep 处理；单文件提取应带最终生效的 TR 或显式 `Config(t_r=...)`。

## 首次真实数据最小集合

- 已预处理体积：一个 run 的 BOLD、实际空间、匹配标签图谱；推荐同 run 混杂和 mask/参考，TR 未知时补 JSON。
- ROI 时序：信号文件、列含义/图谱顺序；3D 需要全部 ROI 坐标，滤波需要 TR。
- 原始数据：一个受试者的完整 BOLD、T1、采集 JSON/序列信息，必要的场图/相位编码资料；先整理为 BIDS。

公开数据集的下载层级不同，见 [下载说明](datasets.md)；数据集名字不会自动证明某份文件已经完成去噪。
