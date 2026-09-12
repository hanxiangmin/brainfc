# GitHub 开源与 pip 包发布

## 当前交付形态

发布根目录是 `brainfc/`，作为独立项目即可运行，不依赖父项目。准备版本为 **0.3.0**，Apache-2.0；有中文 README、英文简介、完整 API 手册、测试、前端源码、内置网页及第三方声明。

独立发布仓库为 [hanxiangmin/brainfc](https://github.com/hanxiangmin/brainfc)。PyPI 首次发布需要维护者完成下文的账号关联；关联本身不会上传文件。现有工作区父项目是另一个项目，本目录使用自己的 Git 仓库与工作流。PyPI `brainfc` 项目查询在 2026-09-12 的准备阶段返回 404；这不代表名称已保留。

## 发布包包含什么

- wheel：Python 库、CLI、已构建网页、离线完整手册、许可证。
- sdist：源码、前端及锁文件、文档、示例、测试、CI 和发布工具。
- standalone source ZIP：与 sdist 同源的独立仓库目录，可解压后作为新仓库根目录。
- 校验清单：各发行文件 SHA-256、大小与版本。

真实影像、下载缓存、`.work/`、输出结果、虚拟环境和 node_modules 不进入发布包。包内示例只在运行时创建合成数据。历史浏览器回归脚本需要原开发环境，独立开源的 `npm run test:ui` 使用全新合成任务。

## 本地构建

```shell
python -m pip install -e ".[dev]"
cd frontend
npm ci
npm run check
npm run build
cd ..
python -m ruff check src tests examples scripts
python -m pytest -q
python scripts/generate_reference.py
python scripts/generate_reference.py --check
python scripts/check_release.py
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
python scripts/check_release.py --dist dist
python scripts/smoke_wheel.py --wheel-dir dist
python scripts/package_release.py --dist dist
```

`smoke_wheel.py` 新建不继承站点包的虚拟环境，直接安装 wheel 及默认依赖，确认包从新环境导入，运行提取/HTML 导出/CLI/文档资产检查。实际依赖解析结果应连同发布验证记录保存。

打包遵循 [PyPA pyproject 指南](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)：标准构建后端、extras、入口点、动态版本和许可证元数据。

## GitHub 独立仓库

从独立仓库取得源码。在检查通过后，为实际发行版本创建对应标签。下列标签必须与 `src/brainfc/_version.py` 一致；已发布标签不应重写。

```shell
git clone https://github.com/hanxiangmin/brainfc.git
cd brainfc
# 完成本文所列检查后：
git tag v0.3.0
git push origin v0.3.0
```

`[project.urls]` 和 `CITATION.cff` 已指向独立仓库。PyPI 使用 `PYPI.md` 作为项目说明，其中的文档链接是完整 GitHub 地址；源码仓库使用包含本地相对链接的中文 README。项目名改变时同时核对打包脚本中的分发名。

`CI` 工作流配置 Windows/Linux × Python 3.11/3.12 测试、前端构建、文档同步、发行物范围、全新安装和合成浏览器操作。它们在 GitHub 上运行成功前，不能声称远程跨平台验证已通过。

## PyPI / TestPyPI

尚无账号时，先在 [PyPI 注册页](https://pypi.org/account/register/) 注册并完成邮箱验证，再按账号提示配置身份验证。账户名可以与包名不同；包名、Python 导入名和命令名均为 `brainfc`。注册本身不会占用包名。无需把密码或令牌写入源码或发送给协作者。

`publish.yml` 是手动触发工作流，默认 TestPyPI，只接受与代码版本一致的 `v0.3.0` 标签。验证成功后使用 PyPI Trusted Publishing；不在仓库保存密码或 token。配置方法以 [PyPI 官方 Trusted Publisher 文档](https://docs.pypi.org/trusted-publishers/using-a-publisher/) 为准。

需要维护者完成一次账号关联：在目标索引配置 owner、独立 repository、工作流 `publish.yml` 和环境 `testpypi` 或 `pypi`；GitHub 创建同名 environment。首次可使用 pending publisher。之后在标签上运行该工作流，选择目标索引。

本项目的正式 PyPI 关联值如下，在 [账号 Publishing 页面](https://pypi.org/manage/account/publishing/) 的 GitHub 表单添加：

| 字段 | 值 |
| --- | --- |
| PyPI Project Name | `brainfc` |
| Owner | `hanxiangmin` |
| Repository name | `brainfc` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

PyPI 用户名用于登录网站，不填写在 GitHub Owner 一栏。TestPyPI 是独立服务，需要单独的账号关联；其 environment 使用 `testpypi`。

先验证 TestPyPI 的发行物与安装，再发布 PyPI。正式 PyPI 同版本文件不能替换，修订后递增版本。成功发布后才能将首选安装方式改成：

```shell
python -m pip install brainfc==0.3.0
```

最后核对远端 tag/commit、下载文件 SHA-256、干净环境安装结果，并把这些证据写进 GitHub Release。手工上传也可用 `twine upload`，但账号授权应通过维护者自己的发布环境完成。

## 发布说明草稿

BrainFC 0.3.0 提供单 run fMRI/ROI 时序到功能连接矩阵的 Python API、CLI 和本地网页，包含来源记录、矩阵/八视图/交互 3D。此版本补齐函数级文档、可试用的 HTTP schema、离线手册和独立发行工具，并修复版本记录不一致。体积/表面格式支持范围和外部 fMRIPrep 未实跑的边界见版本验证文档。
