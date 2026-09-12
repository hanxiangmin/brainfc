# 贡献与开发

本目录可作为独立仓库根目录，不依赖父级 Hyper-Brain 源码。普通用户不需要开发工具。

## 环境

```shell
python -m venv .venv
# 激活虚拟环境后：
python -m pip install -e ".[dev]"
cd frontend
npm ci
cd ..
cd network-frontend
npm ci
cd ..
```

## 提交前验证

```shell
python -m ruff check src tests examples scripts
python -m pytest -q
python scripts/generate_reference.py
python scripts/check_release.py
python scripts/generate_reference.py --check
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
```

前端改动在 `frontend` 和 `network-frontend` 分别运行 `npm run check`、`npm run build`；后者还运行 `npm test`。构建后的 JS/CSS 与第三方许可证随包分发，需要一起更新。在 `frontend` 运行 `npm run test:ui` 会启动临时本地服务，用 Playwright 验证提取、自动传递、网络界面和导出；首次需要 `npx playwright install chromium`，也可通过 `FMRI_TEST_CHROMIUM` 指定已有浏览器。

函数 docstring 采用 NumPy 风格；更改函数/默认值后重新生成参考和 OpenAPI。`Config` 是提取参数默认来源，`network.AnalysisConfig` 是网络分析默认来源。版本改 `src/brainfc/_version.py`，并同步两套前端的 package.json、package-lock.json 与 CITATION.cff。算法实现只放在 `brainfc.network`；`hicbrain` 仅保留薄兼容层。

## 数值与数据约定

新增方法要检查 ROI 排序、signed 权重、原始帧索引、空间/单位、混杂处理及输入不覆盖。使用合成数据构造可验证的期望值；真实数据验证写明取得范围、预处理版本和图谱来源。

不提交原始影像、个人数据、下载缓存、许可证文件、账号令牌或结果目录。用于说明的截图必须说明是合成信号还是实际数据。已有发布结果应保留，新的实验输出到新目录。

报告缺陷时提供版本、文件类型、脱敏后的最小示例、期望行为和实际错误。不要在公开 issue 上传受限影像或包含本地个人信息的完整 provenance。
