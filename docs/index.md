# BrainFC 文档

Python 库、命令行和本地网页，共用处理核心。从原始 BOLD + T1、已处理影像或 ROI 时序生成有符号功能连接矩阵，并进行网络与超图分析。

| 你要做什么 | 阅读入口 |
|---|---|
| 安装、打开界面、运行演示 | [安装与上手](quickstart.md) |
| 用 Python 处理自己的数据 | [Python 使用指南](python-api.md) |
| 从原始 BOLD / DICOM 开始 | [Python 原始 fMRI 全流程](python-preprocessing.md) |
| 查每个函数的准确参数和返回值 | [全部函数与参数](api-reference.md) |
| 了解计算顺序、头动剔除、偏相关 | [处理流程与方法](processing.md) |
| 确认需要哪些文件和空间信息 | [输入格式与空间](formats.md) |
| 读取导出数组、ROI 顺序和质控结果 | [输出文件与数据契约](outputs.md) |
| 在另一个程序中调用本地服务 | [HTTP 使用指南](http-api.md) · [完整接口定义](http-reference.md) |
| 使用命令行和批处理 | [命令行完整参数](cli-reference.md) |
| 使用公开数据集方案 | [官方预设与自动填写](presets-and-workflow.md) · [数据下载入口](datasets.md) |
| 开发、准备 GitHub 与 PyPI 发布 | [发布手册](release.md) |
| 确认测试了哪些能力 | [0.5.0 验证范围](validation-v0.5.0.md) |

函数参考、CLI 帮助和 OpenAPI 直接从源码生成；文档检查会发现新增接口或默认值更改后没有更新参考的情况。安装包内包含离线 HTML 手册，运行本地服务后访问 `/reference/`。

## 范围

连接矩阵是一次扫描内 ROI 信号的相关性描述。库保留原始 ROI 顺序、有符号数值、原始帧索引及处理来源；显示筛选不修改矩阵。

原始影像通过 Python 完成转换和预处理，检查配准与头动报告后进入连接提取。场图畸变校正、疾病诊断和任务 GLM 未实现。网络、超图及组间统计另见网络分析指南；单例结果不等于疾病诊断。

## 网络与超图

[网络分析指南](network-analysis.md) · [Hyper-Brain 迁移](hyper-brain-migration.md) · [网络 HTTP 参考](network-http-reference.md)
