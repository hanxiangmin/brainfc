# 验证记录 · 0.3.0

发布准备日期：2026-09-12，Windows / Python 3.12.14。GitHub CI 与 PyPI 上传未执行。

## 更名与安装范围

此版本将原 `fmri-connect` 分发及 `fmri_connect` 导入改名为 `brainfc` / `brainfc`。默认安装包含 GUI 依赖。旧目录中的发行物和运行结果未改写。

## 本地验证范围

- Python：**56 项通过**，包含原有 44 项及新 HTTP schema/错误请求、版本一致性、文件下载、MGZ 预检查、空间推断和文档代码运行测试。Ruff 通过。
- 文档：48 个类/函数/方法条目，18 条 HTTP 路径，13 个主手册页面；实际签名、Config 默认值、CLI 帮助和 OpenAPI 与生成文件一致。Markdown 文件链接检查通过。
- 前端：TypeScript 与 Vite 构建通过；版本取自 Python 版本文件。
- 示例：合成体积 12 ROI/157 保留帧、表格 3 ROI 示例均完成矩阵、静态图和 HTML 导出；表格结果与独立 NumPy 参考一致。
- 浏览器：`frontend/test-release.cjs` 在独立临时服务和新工作目录通过。覆盖演示提取、矩阵选择、3D/八视图逐边同步、SVG、离线 HTML、无表头表格上传的三步引导、随包手册跳转和 390 px 手册布局。无页面脚本错误；截图已查看。
- 发行物：wheel/sdist 构建及 twine 检查通过；归档清单排除真实影像、下载缓存、虚拟环境和输出目录。全新、不继承站点包的 venv 安装 wheel 及依赖后，`pip check`、提取、HTML、CLI 和随包文档检查通过。

第三方库仍有弃用提醒，未使本次测试失败。上述本地测试不等于所有声明兼容平台均已实测。发行文件的大小和 SHA-256 由 `dist/build-manifest-v0.3.0.json` 记录。

## 与以前记录的关系

历史显示改进和 100 ROI 测试见 [0.2.0 验证](validation-v0.2.0.md)，实际 ADHD 文件读取与早期格式覆盖见 [0.1.0 验证](validation.md)。本次不新增真实患者样本，也不更改那些已保存的原始结果。

## 尚未完成的外部验证

完整 DICOM→BIDS→fMRIPrep 全链路未实跑；没有新的跨站点科学验证。新增 Windows/Linux CI 是待远端执行的配置，不作为已通过证据。PyPI/独立 GitHub 仓库尚未发布。
