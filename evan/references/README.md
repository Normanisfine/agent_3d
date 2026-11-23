# 小物体部分引用的论文：核对记录（2026-11-24）

每篇都从 arXiv 下载了 PDF（本目录），并把 arXiv 接口返回的标题、作者和 PDF 第一页对过；会议和页码用 Crossref 查。PDF 不进 git（见 `.gitignore`）。

| bib 键 | 论文 | 出处 | 核对到的事实 | 本地文件 | 论文里哪里用 |
|---|---|---|---|---|---|
| `ca1m` | Cubify Anything: Scaling Indoor 3D Object Detection（Lazarow 等 5 人） | CVPR 2025，第 22225–22233 页；arXiv:2412.04458 | arXiv 标题、作者一致；Crossref DOI 10.1109/cvpr52734.2025.02070 | `ca1m_2412.04458.pdf` | 数据集和标注框 |
| `boxer` | Boxer: Robust Lifting of Open-World 2D Bounding Boxes to 3D（DeTone 等 7 人） | arXiv:2604.05212（2026-04-06） | 标题、作者一致 | `boxer_2604.05212.pdf` | Inventory 的清单 |
| `scenerig` | SceneRig: An Agentic System for Simulation-Ready 3D Scene Reconstruction from Single Images（Luo 等 7 人） | arXiv:2610.28585（2026-10-20）；arXiv 备注：CoRL 2026 Agentic Robotics Workshop | 标题、作者一致 | `scenerig_2610.28585.pdf` | 修订版清单借用的检测做法 |
| `sam3` | SAM 3: Segment Anything with Concepts（Carion 等 38 人） | arXiv:2511.16719 | 标题、作者一致 | `sam3_2511.16719.pdf` | AHa-3D 的结构掩码；修订版清单的分割 |
| `moge2` | MoGe-2: Accurate Monocular Geometry with Metric Scale and Sharp Details（Wang 等 9 人） | arXiv:2507.02546 | 标题、作者一致 | `moge2_2507.02546.pdf` | 修订版清单的深度 |
| `sahi` | Slicing Aided Hyper Inference and Fine-Tuning for Small Object Detection（Akyon、Altinuc、Temizel） | ICIP 2022，第 966–970 页；arXiv:2202.06934 | Crossref DOI 10.1109/ICIP46576.2022.9897990；arXiv 备注 "Presented at ICIP 2022" | `sahi_2202.06934.pdf` | 相关工作：切窗口检测小物体 |
| `pi3` | π³: Permutation-Equivariant Visual Geometry Learning（Wang 等 10 人） | ICLR 2026（PDF 首页写明）；arXiv:2507.13347 | 标题、作者一致。Pi3X 没有单独的论文：官方仓库 github.com/yyfz/Pi3 的 README 把它写成同一工作的升级版（2025-12-28 发布），权重在 huggingface.co/yyfz233/Pi3X | `pi3_2507.13347.pdf` | AHa-3D 的相机和点云（图 1 图注、相关工作） |
| `hunyuan3d2` | Hunyuan3D 2.0: Scaling Diffusion Models for High Resolution Textured 3D Assets Generation（Zhao 等 74 人，bib 里列前 6 人加 others） | arXiv:2501.12202 | 标题、作者一致；我们用的 2mini 权重在 huggingface.co/tencent/Hunyuan3D-2mini（页面存在） | `hunyuan3d2_2501.12202.pdf` | 两个生成变体 |
| `aha3d` | AHa-3D（软件） | github.com/KevinXu02/aha-3d | 仓库存在（GitHub 接口，2026-09-23 创建）；本地用的版本 82f4b11 | — | 基线 |

另外用 arXiv 接口核对过（只对标题和作者，没下载）：`legoanything` 2609.36380、`sceneconductor` 2606.08402、`literealityagent` 2610.01863、`viga` 2601.11109、`litereality` 2507.02861、`ai2thor` 1712.05474，都存在，和 bib 里的标题、作者一致。
没有核对的（队友的条目，没有 arXiv 号）：`vomp`、`scan2cad`、`scenesmith`、`fastsam3d`、`llmcompiler`、`frugalgpt`。
