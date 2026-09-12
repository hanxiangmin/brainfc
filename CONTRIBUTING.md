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

前端改动运行 `npm run check`、`npm run build`；构建后的 JS/CSS 与第三方许可证随包分发，需要一起更新。`npm run test:ui` 会启动临时本地服务并使用 Playwright，首次需要 `npx playwright install chromium`，也可通过 `FMRI_TEST_CHROMIUM` 指定已有浏览器。

函数 docstring 采用 NumPy 风格；更改函数/默认值后重新生成参考和 OpenAPI。`Config` 是科学参数的唯一默认来源。版本改 `src/brainfc/_version.py`，并同步 frontend/package.json 与 package-lock.json；Vite 从该文件读显示版本。

## 数值与数据约定

新增方法要检查 ROI 排序、signed 权重、原始帧索引、空间/单位、混杂处理及输入不覆盖。使用合成数据构造可验证的期望值；真实数据验证写明取得范围、预处理版本和图谱来源。

不提交原始影像、个人数据、下载缓存、许可证文件、账号令牌或结果目录。用于说明的截图必须说明是合成信号还是实际数据。已有发布结果应保留，新的实验输出到新目录。

报告缺陷时提供版本、文件类型、脱敏后的最小示例、期望行为和实际错误。不要在公开 issue 上传受限影像或包含本地个人信息的完整 provenance。
