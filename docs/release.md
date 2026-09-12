# 发布维护指南

本页供维护者使用。普通用户运行 `pip install -U brainfc` 和 `brainfc serve` 即可。

## 发行物

- wheel：Python API、命令行、两套本地界面、离线手册和许可证。
- sdist：源码、前端锁文件、文档、示例、测试和发布工具。
- rest01：经核查的 ROI 时序、混杂变量、参数和二值脑组织掩膜。

原始 DICOM、个体 T1/BOLD、私人输出与缓存不打包。`scripts/check_release.py` 检查发行范围，并校验 rest01 的文件清单和 SHA-256。详见[隐私核查](privacy-review.md)。

## 本地检查

```shell
python -m pip install -e ".[dev]"
npm --prefix frontend ci
npm --prefix frontend run check
npm --prefix frontend run build
npm --prefix network-frontend ci
npm --prefix network-frontend run check
npm --prefix network-frontend test
npm --prefix network-frontend run build
python -m ruff check src tests examples scripts
python -m pytest -q
python scripts/generate_reference.py --check
python scripts/check_release.py
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
python scripts/check_release.py --dist dist
python scripts/smoke_wheel.py --wheel-dir dist
```

修改 API 或文档后，先运行 `python scripts/generate_reference.py` 更新离线手册，再进行 `--check`。

## 发布步骤

1. 更新版本、变更记录和文档，提交检查通过的源码。
2. 创建与 `src/brainfc/_version.py` 一致的 `vVERSION` 标签，例如 `v0.4.0`；已有标签不重写。
3. 在该标签上运行 **Publish Python distributions**，选择 `pypi`。
4. 工作流重新验证 Windows/Linux、两套前端、文档、安装包和真实样例浏览器流程，再上传同一批发行物。
5. 核对 PyPI 版本、下载文件 SHA-256 和干净环境安装结果，补充 GitHub Release。

PyPI 已使用 [Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)，仓库不保存发布密码或令牌。

| 配置 | 值 |
| --- | --- |
| 项目 | `brainfc` |
| GitHub 仓库 | `hanxiangmin/brainfc` |
| 工作流 | `publish.yml` |
| 环境 | `pypi` |

TestPyPI 是独立索引，需要单独配置 `testpypi` 环境与发布者。正式 PyPI 的同版本文件不能替换；需要修订时递增版本。
