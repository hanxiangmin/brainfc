# 输入格式与本地工作区

## 数组与列

- FC：R×R，对称；明确 correlation、fisher_z 或 covariance。相关系数范围为 [-1,1]。
- ROI 时序：T×R；非有限值、恒定 ROI、错误列数会被拒绝。
- CSV/TSV/TXT/1D 支持有表头和无表头。ADHD 的 File、Sub-brick 辅助列按名称移除。
- MAT/NPZ 支持选择数值变量；多变量时必须选择。MATLAB v7.3 仅接受数值型二维数据，不解析可执行对象。
- ROI 列选择采用从 0 开始、结束不包含的范围，如 `0:116`。这只是列选择，不等于已证明 AAL 图谱。
- 导入最大 1000 ROI、100000 时间点、5000000 数值单元。网页每文件最大 128 MiB、每次请求最大 512 MiB（包含分块上传）；Python 读取器最大 256 MiB。超出限制须显式分区/降尺度后分析。

## 预设

ABIDE1/2、ADHD、MDD、ADNI 预设处理常用字段名称和辅助列。MDD 的多图谱 ROISignals 必须选择对应 ROI 范围并保留实际来源说明。矩阵维度和文件夹名称不能替代图谱字典、表型或受试者身份。

`ROICorrelation_FisherZ` 与 `ROICorrelation` 应使用不同的矩阵类型。Fisher-z 转回相关系数时对角线显式设为 1；网络分析不计自连接。

Fisher-z 文件对角线中未定义的 NaN/Inf 自连接在读取副本中置零并记录处理数量；非对角 NaN/Inf 会拒绝。坐标表、已识别的脑区中心与标签变量不作为功能数据。

## ROI 与解剖

元数据可提供 `roi_ids`、`labels`、R×3 `coordinates`，以及 `metadata.coordinate_space`、atlas、atlas_version、TR、滤波/GSR/删帧等。缺少 TR 不阻止静态 FC，但会在报告中标记。缺少脑区坐标时只显示抽象结构。

只有明确 MNI 坐标才启用模板脑定位。坐标必须逐行匹配 ROI。不要将不同图谱或重复受试者静默合并。

## 存储

默认工作区位于操作系统的用户数据目录。也可通过 `hicbrain serve --workspace PATH` 指定。目录包括 uploads、results、exports、templates 和 state.sqlite。上传是复制，原始数据不被覆盖。删除工作区是用户手动操作；软件不会自动清理结果。

安装时可以联网取得软件依赖；分析任务与网页资源不需要外部网络。真实数据不打包入 wheel/sdist，不用于公开演示站点。
