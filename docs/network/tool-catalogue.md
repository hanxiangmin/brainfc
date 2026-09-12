# 脑网络工具目录

检索日期：2026-09-10。按官方页面和作者仓库整理；此表不代表所有工具均已安装验证。许可字段以锁定版本的实际 LICENSE 为准，附带组件、图谱、数据分别核查。仅 phase 标为核心的组件进入首版依赖。

## 分析界面

| 项目 | 用途 | 许可核查 | 接入安排 |
|---|---|---|---|
| [CONN](https://web.conn-toolbox.org/) | fMRI连接完整流程 | MIT | 参考 |
| [DPABI / DPARSF / DPABISurf](https://github.com/Chaogan-Yan/DPABI) | 体积与表面处理、统计 | LGPL-2.1; bundled modules separately | 格式兼容 |
| [GRETNA](https://www.nitrc.org/projects/gretna/) | 脑图构建及指标 | GPL; version verify | 参考 |
| [GraphVar](https://www.nitrc.org/projects/graphvar/) | 图统计与机器学习GUI | GPL; version verify | 参考 |
| [BRAPH 2](https://github.com/braph-software/BRAPH-2) | 图、多层网络、学习GUI | Custom; redistribution/integration restricted | 仅功能参考 |
| [BrainNetClass](https://github.com/zzstefan/BrainNetClass) | 脑网络构建分类 | Not confirmed | 研究目录 |
| [GIFT](https://github.com/trendscenter/gift) | ICA与动态功能连接 | Distribution license requires verification | 后续 |
| [BrainVoyager](https://brainvoyager.com/bv/doc/UsersGuide/GeneralInfo/Overview.html) | 商业影像分析GUI | Proprietary | 仅功能参考 |

## 可视化与平台

| 项目 | 用途 | 许可核查 | 接入安排 |
|---|---|---|---|
| [BrainNet Viewer](https://github.com/mingruixia/BrainNet-Viewer) | 脑表面节点和连接 | GPL-3.0 | 导出兼容 |
| [Surf Ice](https://www.nitrc.org/projects/surfice/) | 脑表面绘图 | BSD style | 后续 |
| [brainGL](https://github.com/rschurade/braingl) | 桌面脑图形 | MIT | 参考 |
| [Workbench](https://ccf.humanconnectome.org/software/connectome-workbench) | CIfTI/GIfTI表面与体积 | GPL-2.0 | 后续 |
| [FSLeyes](https://github.com/pauldmccarthy/fsleyes) | MRI本地查看 | Apache-2.0 | 后续 |
| [3D Slicer](https://www.slicer.org/) | 医学影像桌面 | Slicer BSD style | 后续 |
| [MRtrix3](https://github.com/MRtrix3/mrtrix3) | 扩散和结构连接 | MPL-2.0 | 后续 |
| [NiiVue](https://github.com/niivue/niivue) | 网页解剖查看 | BSD-2-Clause | 核心网页 |
| [BrainBrowser](https://github.com/aces/brainbrowser) | 网页脑影像 | AGPL-3.0 | 备选 |
| [Papaya](https://github.com/rii-mango/Papaya) | 网页切片查看 | BSD style; nonclinical notice | 备选 |
| [vtk.js](https://github.com/Kitware/vtk-js) | 通用三维浏览器渲染 | BSD-3-Clause | 备选 |
| [Cytoscape.js](https://github.com/cytoscape/cytoscape.js) | 普通图交互与布局 | MIT | 备选 |
| [Plotly.js](https://github.com/plotly/plotly.js) | FC热图与统计图 | MIT | 核心网页 |
| [brainlife](https://brainlife.io/docs/user/started/) | 网页上传、计算、溯源 | Warehouse MIT; Apps separate | 架构参考 |
| [CBRAIN](https://github.com/aces/cbrain) | 机构HPC网页平台 | GPL-3.0 | 后续 |
| [Neurodesk](https://github.com/NeuroDesk/neurodesktop) | 容器神经影像桌面 | MIT; tools separate | 部署参考 |
| [NeuroVault](https://github.com/NeuroVault/NeuroVault) | 统计图分享 | MIT; datasets separate | 后续 |

## 图与超图

| 项目 | 用途 | 许可核查 | 接入安排 |
|---|---|---|---|
| [Nilearn](https://github.com/nilearn/nilearn) | 时序/连接/脑图 | BSD-3-Clause | 核心 |
| [NiBabel](https://github.com/nipy/nibabel) | 影像格式 | MIT | 核心依赖 |
| [NetworkX](https://github.com/networkx/networkx) | 普通图 | BSD-3-Clause | 核心 |
| [python-igraph](https://github.com/igraph/python-igraph) | 高性能图计算 | GPL-2.0 | 备选 |
| [bctpy](https://github.com/aestrivex/bctpy) | BCT脑图指标 | GPL-3.0+ | 参考/可选 |
| [brainconn](https://github.com/fiuneuro/brainconn) | 脑图指标 | GPL-3.0+; no longer actively maintained | 历史参考 |
| [netneurotools](https://github.com/netneurolab/netneurotools) | 脑网络统计和零模型 | BSD-3-Clause | 后续 |
| [NBS](https://www.nitrc.org/projects/nbs/) | 队列连接成分置换检验 | GPL; version verify | 后续 |
| [BrainSpace](https://github.com/MICA-MNI/BrainSpace) | 连接梯度 | BSD-3-Clause | 后续 |
| [BrainStat](https://github.com/MICA-MNI/BrainStat) | 脑空间统计 | BSD-3-Clause; bundled terms separate | 后续 |
| [neuromaps](https://github.com/netneurolab/neuromaps) | 空间映射与注释 | CC-BY-NC-SA-4.0 | 许可受限可选 |
| [XGI](https://github.com/xgi-org/xgi) | 原生超图结构/统计 | BSD-3-Clause | 核心 |
| [HyperNetX](https://github.com/pnnl/HyperNetX) | 属性超图与HIF | BSD-3-Clause | 后续 |
| [Hypergraphx](https://github.com/HGX-Team/hypergraphx) | 高阶模体/时间多层超图 | BSD-3-Clause | 后续 |
| [TopoNetX](https://github.com/pyt-team/TopoNetX) | 单纯/胞腔/组合复形 | MIT | 后续 |
| [TopoEmbedX](https://github.com/pyt-team/TopoEmbedX) | 高阶结构嵌入 | MIT | 后续 |
| [GUDHI](https://github.com/GUDHI/gudhi-devel) | 持久同调 | Current master MIT; pin release/submodules | 后续 |
| [ripser.py](https://github.com/scikit-tda/ripser.py) | 持久同调 | MIT | 后续 |
| [giotto-tda](https://github.com/giotto-ai/giotto-tda) | 拓扑学习流程 | AGPL-3.0 | 可选 |
| [hoi](https://github.com/brainets/hoi) | 高阶信息估计 | BSD-3-Clause | 后续 |
| [THOI](https://github.com/Laouen/THOI) | Gaussian-copula高阶信息 | MIT | 后续 |
| [IDTxl](https://github.com/pwollstadt/IDTxl) | 信息流网络估计 | GPL-3.0 | 可选 |
| [JIDT](https://github.com/jlizier/jidt) | 信息动力学 | GPL-3.0 | 可选 |
| [HOI-Lenses](https://github.com/nplresearch/HOI_lenses_analysis) | 多框架高阶脑功能比较作者代码 | Not confirmed | 研究目录 |

## 后续学习模型

| 项目 | 用途 | 许可核查 | 接入安排 |
|---|---|---|---|
| [PyG](https://github.com/pyg-team/pytorch_geometric) | 图与HypergraphConv | MIT | 后续优先 |
| [DGL](https://github.com/dmlc/dgl) | 图学习框架 | Apache-2.0 | 备选 |
| [DeepHypergraph](https://github.com/iMoonLab/DeepHypergraph) | HGNN/HGNN+/HyperGCN/UniGNN | Apache-2.0 | 后续 |
| [TopoModelX](https://github.com/pyt-team/TopoModelX) | 拓扑神经网络 | MIT | 后续 |
| [BrainGB](https://github.com/HennyJie/BrainGB) | 脑网络学习基准；BrainNN是内部模块 | MIT | 后续 |
| [NeuroGraph](https://github.com/Anwar-Said/NeuroGraph) | 静态/动态图基准 | MIT | 后续 |
| [NeuroSTORM](https://github.com/CUHK-AIM-Group/NeuroSTORM) | 多类脑影像学习输入 | Apache-2.0 LICENSE; README discrepancy | 后续 |
| [BrainGNN](https://github.com/xxlya/BrainGNN_Pytorch) | ROI-aware图模型 | Not confirmed | 研究目录 |
| [Brain Network Transformer](https://github.com/Wayfear/BrainNetworkTransformer) | 脑网络Transformer | MIT | 后续 |
| [FBNetGen](https://github.com/Wayfear/FBNetGen) | 时序可学习构图 | Not confirmed | 研究目录 |
| [BrainNetCNN](https://github.com/jeremykawahara/ann4brains) | 矩阵卷积 | CC-BY-NC-SA-4.0 | 许可受限可选 |
| [RethinkingBCA](https://github.com/LearningKeqi/RethinkingBCA) | 传统及图模型比较 | Not confirmed | 研究目录 |
| [HGST](https://github.com/iMoonLab/HGST) | ROI超图；ADHD/MDD | Research/education only | 许可受限可选 |
| [HUNet](https://github.com/basiralab/HUNet) | 受试者群体超图 | MIT | 后续 |
| [HCAE](https://github.com/basiralab/HCAE) | 形态ROI多视图超图 | MIT per README | 研究目录 |
| [junifer](https://github.com/juaml/junifer) | 预处理影像特征提取 | Verify pinned release | 后续 |
| [julearn](https://github.com/juaml/julearn) | 规范机器学习 | Verify pinned release | 后续 |
| [PHOTONAI](https://github.com/wwu-mmll/photonai) | 机器学习流程 | Verify pinned release | 后续 |
| [CPM](https://github.com/YaleMRRC/CPM) | 连接组预测 | Not confirmed | 研究目录 |

## 原始影像处理

| 项目 | 用途 | 许可核查 | 接入安排 |
|---|---|---|---|
| [BIDS Validator](https://github.com/bids-standard/bids-validator) | 数据规范校验 | MIT | 后续 |
| [PyBIDS](https://github.com/bids-standard/pybids) | BIDS索引 | MIT | 后续 |
| [dcm2niix](https://github.com/rordenlab/dcm2niix) | DICOM转NIfTI | BSD/MIT/public-domain components | 后续 |
| [Clinica](https://github.com/aramis-lab/clinica) | ADNI/OASIS转换 | MIT | 后续 |
| [MRIQC](https://github.com/nipreps/mriqc) | 影像质量控制 | Apache-2.0 | 后续 |
| [fMRIPrep](https://github.com/nipreps/fmriprep) | BIDS预处理 | Apache-2.0; dependencies separate | 后续 |
| [XCP-D](https://github.com/PennLINC/xcp_d) | 去噪和ROI/FC衍生物 | BSD-3-Clause | 后续 |
| [C-PAC](https://github.com/FCP-INDI/C-PAC) | 连接组处理 | LGPL-3.0-or-later | 后续 |
| [AFNI](https://github.com/afni/afni) | EPI处理及QC | Mixed public-domain/CC-BY/third-party | 后续 |
| [FSL](https://fsl.fmrib.ox.ac.uk/fsl/docs/license.html) | 影像分析组件 | Noncommercial/custom; components differ | 许可分别处理 |
| [FreeSurfer](https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSoftwareLicense) | 皮层重建 | Custom | 后续 |
| [ANTs](https://github.com/ANTsX/ANTs) | 配准 | Apache-2.0 | 后续 |
| [Nipype](https://github.com/nipy/nipype) | 工作流接口 | Apache-2.0 | 后续 |
| [Pydra](https://github.com/nipype/pydra) | 工作流执行 | Apache-2.0 | 后续 |
| [ADNI_fMRI_protocol](https://github.com/STATMINDlab/ADNI_fMRI_protocol) | ADNI GO/2/3处理流程 | GPL-3.0 | 研究目录 |

## 四病数据来源

- ASD：[ABIDE I](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html)、[ABIDE II](https://fcon_1000.projects.nitrc.org/indi/abide/abide_II.html)。
- ADHD：[ADHD-200](https://fcon_1000.projects.nitrc.org/indi/adhd200/index.html)。
- MDD：[REST-meta-MDD](https://rfmri.org/REST-meta-MDD-V1)、[SRPBS](https://www.synapse.org/Synapse%3Asyn22317076/metadata/)。
- AD/认知障碍：[ADNI](https://adni.loni.usc.edu/)、[OASIS-3](https://sites.wustl.edu/oasisbrains/)。

ADNI 是队列名称。个体级数据和衍生物依各自协议使用，不随工具再分发。ROI超图、受试者群体超图、形态网络与fMRI网络须分别记录；超图表征不自动证明不可约高阶关系。
