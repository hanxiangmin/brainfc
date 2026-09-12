# Hyper-Brain 合并到 BrainFC

## 合并理由与边界

原来的两个库都读取 ROI 时序、计算相关性、管理图谱并显示三维脑网络；主要区别是所处处理阶段。BrainFC 擅长影像输入、ROI 提取、时间域清理、矩阵和八视图；Hyper-Brain 擅长已有矩阵的普通图/原生超图、结构指标和独立被试组间统计。合并后保留两个明确模块，共享安装包、本地服务和结果传递。

| 原入口 | 新入口 | 兼容性 |
|---|---|---|
| `brainfc.extract_connectome` | 不变 | 提取参数和数值契约保持。 |
| `hicbrain.BrainDataset` / `AnalysisConfig` / `analyze` | `brainfc.network` 的同名对象 | `hicbrain` 是薄兼容模块，不含第二份算法。 |
| `hicbrain.graph` / `hypergraph` / `statistics` / `atlas` 等 | `brainfc.network` 下同名模块 | 同一实现；保留旧导入路径。 |
| `Connectome.to_hicbrain()` | `to_network()`；可直接 `analyze_network()` | 旧方法保留，无需另装 Hyper-Brain。 |
| `hicbrain serve` | `brainfc serve` | 旧命令保留 8765 端口并启动统一界面；新命令默认 8766。 |
| `hicbrain analyze` | `brainfc network` | 旧参数保留；新命令还能直接读取 BrainFC 保存目录。 |
| 独立 Hyper-Brain HTTP `/api/v1` | 统一服务 `/networks/api/v1` | HTTP 客户端需要更改基础路径；旧 `hicbrain.web.app.create_app()` 仍可独立提供旧路由。 |

### 安装当前合并版

当前合并源码版本为 **0.4.0**，正式 PyPI 发布以版本标签和发布记录为准。要立即使用本次合并：

```bash
pip install "brainfc @ git+https://github.com/hanxiangmin/brainfc.git"
brainfc serve
```

如果同一个环境以前安装过 `hic-brain`，先执行 `pip uninstall hic-brain`，再安装/重装 BrainFC。两个 distribution 曾使用相同的 `hicbrain` 命名空间，不能依靠安装先后来管理重叠文件。旧环境和工作目录无需删除；可在新虚拟环境试用。

## 数据与旧工作区

原 Hyper-Brain 仓库及其历史输出保留。本次没有自动移动、删除或覆盖它们。统一服务把网络数据放在所选工作区的 `networks` 子目录；已有 Hyper-Brain 工作区可继续通过 `hicbrain.web.app.create_app(old_workspace)` 读取，或把原始矩阵和显式 ROI 映射导入新界面。数据迁移不根据脑区数量猜图谱。

提取结果通过完整矩阵传递，因此不会再次滤波/回归，偏相关或 Spearman 也不会误被重新计算为 Pearson。已有低层 Fisher-z 函数保留其历史截断规则：`Connectome.fisher_z` 使用 1e-7，而网络模块的独立 `fisher_z()` 使用机器精度并发出完美相关裁剪提示；二者没有被悄悄替换。最终研究方法仍应明确声明。

## 实现与许可

网络计算和服务位于 `src/brainfc/network`；旧导入兼容层位于 `src/hicbrain`。`network-frontend` 编译进同一个 wheel，用户不需要 Node.js 或第二个服务器。图谱分区切片等较大显示依赖在需要时加载。

上游来自 [Hyper-Brain](https://github.com/hanxiangmin/Hyper-Brain)，准确提交和迁入文件列表见 [来源记录](network/upstream.json)。Apache-2.0 许可和第三方声明均保留。图像/真实样例的公开范围仍受原有[隐私核查记录](privacy-review.md)约束；合并不增加私人数据发布范围。
