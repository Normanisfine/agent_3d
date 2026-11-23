# 小物体部分交接说明（Yifan → Mingjian，2026-11-24）

这份说明讲三件事：论文里哪些内容是小物体部分的、这个分支上放了什么、还需要你处理什么。
`evan/README.md` 是整个小物体项目的总说明（目录、怎么从头跑一个场景）；这里只讲和论文有关的。

## 一句话结论

以 AHa-3D 为基线，叠加三个改动（All objects → Inventory → Checklist）。六个测试房间、543 个 50 cm 以下的目标里，
摆对的从 6 个涨到 71、101、142（Checklist 第二遍 155）。三个改动在每个房间都高于基线（p = 0.031）；
三者之间的差距在六个房间上不显著。清单自己的框不经过 agent 能过 194 个，所以下一步该改的是摆放。

## 论文里属于小物体的部分

都在 `paper/paper_file/`，基于你合并后的版本（`df04b9a`）改的，你的句子没有动。

| 位置 | 文件 | 内容 |
|---|---|---|
| 摘要前半（到 "placement is the clear next step" 为止） | `main.tex` | 小物体的问题、三个改动、结果 |
| 引言第 2 段，第 3 段前两句 | `main.tex` | 三个改动的定义；基线漏了多少 |
| 相关工作 "Finding small objects" 一段 | `main.tex` | 新加的 |
| 3.1 节，图 1 | `small-object-method.tex`、`visual-evidence.tex` | 方法、评测判据 |
| 4.1 节第一段 | `main.tex` | 房间怎么选、用的模型 |
| 4.2 节，图 4、图 5 | `reconstruction.tex` | 结果 |
| 4.4 节 | `cost-results.tex` | 六个房间的时间和成本 |
| 讨论前三段、结论第一段 | `main.tex` | |
| 附录 A | `appendix-small-objects.tex` | 表 2–6、图 8 |

每个数字的出处都记在 `paper/paper_file/evidence.md` 最后两节（11 月 22 日和 24 日）。

## LaTeX 文件一览

整篇论文的 LaTeX 都在 `paper/paper_file/`，入口是 `main.tex`，其余文件由它按下面的顺序读入。编译：`make pdf`（pdflatex），或 `tectonic main.tex`。

| 顺序 | 文件 | 论文里的位置 | 谁的 |
|---|---|---|---|
| 1 | `main.tex` | 标题、摘要、1 引言、2 相关工作、3.3 时间和成本的算法、4.1 实验设置、图 3、5 讨论、6 结论 | 共用（小物体的句子见上表） |
| 2 | `small-object-method.tex` | 3.1 小物体的重建和评测 | Yifan |
| 3 | `visual-evidence.tex`（由上一个文件读入） | 图 1 系统总览 | Yifan |
| 4 | `architecture.tex` | 3.2 规划和控制，图 2 | Mingjian |
| 5 | `completion.tex` | 3.4 物理属性 | Yujing |
| 6 | `reconstruction.tex` | 4.2 小物体结果，图 4、图 5 | Yifan |
| 7 | `systems-results.tex` | 4.3 并行构建和整间房重建，表 1、图 6 | Mingjian |
| 8 | `cost-results.tex` | 4.4 时间和推理成本 | Yifan |
| 9 | `physics-results.tex` | 4.5 茶几上的物理测试，图 7 | Yujing |
| 10 | `appendix-small-objects.tex` | 附录 A，表 2–6、图 8 | Yifan |

其他文件：`references.bib`（参考文献，共用）、`neurips_2025.sty`（会议模板，不要改）、`Makefile`、`evidence.md`（每个数字的出处）、`main.pdf`（编译结果）、`build/`（编译的中间文件）。

图在 `paper/paper_file/figures/`：

| 文件 | 哪张图 | 谁的 |
|---|---|---|
| `system-pipeline.pdf` | 图 1 | Yifan |
| `parallelism.pdf` | 图 2 | Mingjian |
| `ai2thor-source.png`、`ai2thor-reconstruction.png` | 图 3 | Mingjian |
| `small-object-results.pdf` | 图 4 | Yifan |
| `panels/*.jpg` | 图 5、图 8 的小图 | Yifan |
| `experimental-settings.pdf` | 图 6 | Mingjian |
| `ca1m-coffee-physics.pdf`（由 `coffee-rest.png`、`tissue-density.png` 拼成） | 图 7 | Yujing |

## 这个分支上新放的东西

| 路径 | 内容 |
|---|---|
| `evan/runs/<组>-claude/<房间>/<第几遍>/` | 36 次正式运行各自的最终场景 `scene.blend`、提示词、运行日志（时间、token、成本）、导出的实例框 `export/objects.json`、打分 `score_sim3.json`（相机拟合尺度）和 `score_noscale.json`；Checklist 另有逐条决定 `inventory_decisions.json` |
| `evan/runs/showcase/<房间>_A5_materials/scene.blend` | 六个房间的材质版场景（图 5、图 8 最后一列） |
| `evan/inventories/<房间>/` | 三份清单：`inventory.json`（Boxer）、`inventory_v2.json`（修订版，去重前）、`inventory_v2_list.json`（Checklist 实际拿到的） |
| `evan/results/test_opus_6rooms/` | 六个房间的主表、配对检验、第二遍、对照检查 |
| `evan/configs/prompts/A5.md`、`configs/checklist.json` | Checklist 的提示词和去重阈值 |
| `evan/scripts/paper/` | 出图脚本 |
| `evan/paper_figures/` | 图 1 的 TikZ 源文件 `pipeline/system.tex` 和它用的小图、结果图的数据 `figures/data.json`、怎么重出每张图 |
| `evan/references/README.md` | 小物体部分每条引用的核对记录 |
| `evan/src`、`scripts`、`configs`、`tests`、`results` | 同步到 11 月 24 日的状态 |

组名对照：A0 基线、A1 All objects、A2 Inventory、A5 Checklist、A3r 和 A3v 是两个生成网格的变体（只有前三个房间）。
房间编号：1 = 42897538，2 = 42898849，3 = 42899617，4 = 42899712，5 = 42899729，6 = 44358442。
用 Blender 5.2 打开 `scene.blend`；每个实例是一组带同一个 `instance_id` 的网格。

## 需要你处理的

1. **摘要最后三句是你的**，现在写的还是"整间房的速度和成本尚未测量"，和你 4.3 节的 FloorPlan209 对比表对不上。摘要里小物体占了大半，比例你看着调。
2. **正文现在约 10 页**，上限 8 页。小物体这边可以压的：图 5 可以减到两行；4.2 节的 "Generation" 和 "Instances without a target" 两段可以挪进附录。
3. **`main.pdf` 是我用 tectonic 编的**（这台机器没有 pdflatex），`build/` 下的 aux、log 还是你上次的。请用 `make pdf` 重编一次。
4. **图 1 下排第 2、3 块**（Parallel builds、Physical properties）是我按你们各节的描述画的，请你和 Yujing 看看画得对不对。改 `evan/paper_figures/pipeline/system.tex`，用 tectonic 或 pdflatex 单独编译后拷到 `paper/paper_file/figures/system-pipeline.pdf`。
5. **4.4 节加了一句**：小物体的运行用 Claude Opus 5.5，和你控制器对比用的模型不同，所以两处基线成本（14.13 美元和 27.27 美元）不能直接比。
6. `paper/paper_file/README.md` 里"正文七页"和用 `plot_ca1m.py` 重出召回图的说法已经过时，我没有改。

## 已知的问题，没有做

- 只有 Checklist 跑了两遍，其余各组一遍；局限里写了。
- Checklist 同时换了清单和处理规则，没有做把两者分开的消融；局限里写了。
- 图 4 和图 5 的颜色含义不同（图 4 的蓝是 Checklist，图 5 的蓝是"摆对"），在相邻两页，容易看混。
- 更严的 box overlap 判据下，六个房间是 6、40、47、53（附录表 4 的一列），Checklist 对 Inventory 的领先只剩 6 个。正文只写了"顺序不变"。
- Checklist 没配上标注的实例里，除了明信片和圣诞树挂件，其余约 175 个没有人工核对。

## 没有上传的

这个仓库是公开的，所以 CA-1M 的原始数据（视频、帧、标注框）没有放，人工核对用的画面截图也没有放。
另外没有放的：每次运行的完整对话记录（每个十几到二十几 MB）、AHa-3D 的工作目录（每个房间几个 GB）、引用论文的 PDF。
这些都在 Yifan 的笔记本上，需要哪个可以单独要。
