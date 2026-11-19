<!-- 01 查新更新（2026-10-14，研究子 agent）。基线：CIS-6220 仓库 03-final-project/agentic-3d/notes/ 下 2026-10-08 的 fusion-novelty-check.md、grase-reading.md、landscape-agentic-recon.json。本文只写增量，以及与学生新思路 (a)(b)(c) 直接相关的旧材料。 -->

# 查新更新：AHa-3D 现状、10-08 以来的新邻居、「小物体 + 生成式补建」的先例

日期：2026-10-14。arXiv 覆盖到 2026-10-12（周一）这一批公告。10-13 那天 arXiv 没有发布公告（https://arxiv.org/catchup/cs.CV/2026-10-13 显示 "No updates for Tue, 13 Oct 2026"），所以 10-09 之后提交的论文还没有出现在列表里。

标注约定：
- 「原文」：读过 arXiv HTML 全文，数字从原文表格核对过。
- 「摘要」：只读到 arXiv 或 OpenReview 摘要。
- 「旧笔记」：沿用 10-08 的笔记，本次没有重新核对。
- 「未核实」：照字面理解。

---

## 0. 结论先行

1. **AHa-3D 在 10-08 之后没有任何实质变化。** 没有新提交、release、issue 或 arXiv 论文，博客文件也没有改动。唯一的变化是星数从 291 涨到 304。它至今没有任何定量评测，博客里的消融部分作者自己标注为占位。
2. **AHa-3D 处理小物体的方式是降级处理，不是专门处理。**
   - 博客交给 Astra 的任务原话是 "match the walls and major furniture and approximate small objects"。
   - 仓库的「Major objects」精度模式写着 "Small tabletop/cabinet-top decor may vary unless user-flagged"。
   - Codex 审查员把 "Small decor ... approximate by scope" 记为 nonblocking。
   - 小物体靠 RoomKit 小资产库检索，比如花瓶、蜡烛、植物、餐具、挂画，或者由 agent 用脚本从基本体搭出来。
   - **关键发现：** 作者做过一次 SAM 3D Objects 和 TRELLIS.2 的物体生成试点，"completed and then deferred"，生成适配器没有随仓库发布（docs/OBJECT_GENERATION.md）。也就是说，学生想法 (b) 在 AHa-3D 内部已经试过、然后被搁置了，搁置原因没有公开。
3. **10-08 之后出现了两篇和 (a)+(b) 高度重合的新工作，而且都用 GPT-6 Astra。**
   - **GATOR**（NVIDIA，arXiv 2610.11215，10-08）：在 TRELLIS.2 基础上做观测对齐的生成，再交给 GPT-6 Astra 做 edit-render-review 精修。它和「GPT-6 从零用代码建模」做了同预算对比，还画了时间-质量曲线。
   - **LIVIN**（arXiv 2610.12069，10-08）：一个 GPT-6 Astra 加人工审核的家庭数字孪生流水线。agent 给每个实例打两类标签：是否铰接，是家具还是小物体。铰接物体由 agent 写 Blender 代码，非铰接物体走 GPT-Image-2 清理参考图再交给 Rodin 生成。它还专门做了 small clutter 子集的覆盖率、3D 框召回和 F-score 评测（Table 8）。
4. **所以「给 AHa-3D 加一个调用 Hunyuan3D/TRELLIS 的分支」作为方法贡献已经不新。** 这个设计已有 GRASE、LIVIN、LiteReality-Agent、HARMONY、CoDimRecon、GATOR，AHa-3D 自己也试过。
5. **仍然空着的是评测和分析类贡献：**
   - (i) AHa-3D 的首次定量评测，用有 3D 真值的单目视频；
   - (ii) 在 agentic 单目视频到 Blender 这个设定下，按物体尺寸分层报告召回和几何精度。目前只有 LIVIN 对非 agentic 方法、在给定 GT mask 和深度的条件下做过一个小物体子集；
   - (iii) 同一 harness、同等美元预算下比较不同路由策略：全基本体、全生成、按规则、VLM 决定、生成加 agent 精修；
   - (iv) 场景级的「美元-精度」曲线。

   GATOR 只在物体级给出时间曲线，LIVIN 只给了 token 总数。

---

## 1. AHa-3D 现状（10-08 到 10-14）

### 1.1 仓库、博客和论文

| 项目 | 10-08 | 10-14 | 来源 |
|---|---|---|---|
| 最后推送 / HEAD | 2026-09-29，`82f4b11` | 不变，仍是 10 个提交 | `gh api repos/KevinXu02/aha-3d`，https://github.com/KevinXu02/aha-3d/commits/main |
| release / tag / 分支 | 无 / 无 / 仅 main | 不变 | `gh api .../releases`、`.../tags`、`.../branches` |
| issue / PR | 0（垃圾 issue 已删） | 0 | `gh api .../issues?state=all` 返回空 |
| 星 / fork | 291 / 14 | **304 / 14** | `gh api repos/KevinXu02/aha-3d` |
| 有自己改动的 fork | ishaanm612（第 2 级安装修复）、JasperPWang（中文文档） | 不变，没有新的有意义改动 | https://github.com/ishaanm612/aha-3d/commit/684a186 ；https://github.com/JasperPWang/aha-3d/tree/chinese-docs |
| 博客 | 各 section 的 Last-Modified 都是 2026-10-01 23:27 GMT | 不变（10-14 用 curl 查响应头） | https://kevinxu02.github.io/real2sim-indoor-site/sections/*.html |
| arXiv 论文 | 无 | 无 | 网页搜索；arXiv cs.CV/RO/GR 10-06 到 10-12 列表里没有；ICLR 2027 的 OpenReview 检索结果里也没有引用 AHa-3D 的摘要 |

其他：GitHub 上 10-07 之后新建的 real2sim 或 video-to-blender 仓库都是 0 星的个人仓库。`JasperWANG-911/real2sim-agent`（10-12）是空仓库（`gh api repos/JasperWANG-911/real2sim-agent`，size 0）。

### 1.2 AHa-3D 怎么处理小物体（杯子、书、显示器、植物、杂物）

博客和仓库的原文证据如下，全部在 10-14 抓取核对。

1. **任务说明本身就把小物体降成「近似」。** 博客 Workflow ablation 一节写给两个 Astra agent 的要求是："They should match the walls and major furniture and approximate small objects."（https://kevinxu02.github.io/real2sim-indoor-site/sections/workflow.html）
2. **精度模式里小物体可以随意。** `docs/LAYOUT_INSPECTION.md` 定义了 Approximate / Major objects / Precise / Selective 四档。Major objects 档写的是 "Small tabletop/cabinet-top decor may vary unless user-flagged"。只有 Precise 档才要求最后核对 "smaller objects"（https://github.com/KevinXu02/aha-3d/blob/main/docs/LAYOUT_INSPECTION.md）。同一文件要求逐个审查的主物体是 "at least beds, tables and shelves—plus dominant and user-flagged objects"。
3. **审查环节把小物体列为 nonblocking。** 博客公开的 Codex 结构化审查（media/structured-review.json）的 uncertainties 里有一条："Small decor, leaf shapes and individual cushion contours are approximate by scope"，影响等级 nonblocking。逐项复核记录 review.md 覆盖 21 个语义项：Bed、Bench、Built-in、Cabinet wall、Ceiling、Ceiling fixtures、Chaise、Door header、Door right wall、Floor、Hall far wall、Hall floor、Hall return、Headwall、Wood panel、Lamp、Nightstand、Plant、Rug、Side table、Windows。全部是建筑构件、家具、灯和植物，**没有单独的杯、书或桌面杂物条目**（https://kevinxu02.github.io/real2sim-indoor-site/media/review.md ；https://kevinxu02.github.io/real2sim-indoor-site/media/structured-review.json）。
4. **小物体的来源是检索或程序化脚本，不用生成模型。**
   - RoomKit 博客写的是 "Retrieve furniture, fixtures, plants, and materials by ID"（https://kevinxu02.github.io/real2sim-indoor-site/sections/roomkit.html）。
   - 注册资产索引（`assets/INDEX.md`，registered=108、callable=4）里的小物体类有：
     - decor/candles：六支蜡烛组；
     - plants：绣球花碗、蕨类、阔叶盆栽、白掌；
     - vases：圆瓷瓶、小瓷瓶、高瓷瓶；
     - tableware：银托盘、高脚器皿、餐巾；
     - wall_art：5 种挂画；
     - 另有水龙头和台灯。
   - **没有杯、书、显示器、键盘、遥控器这类常见桌面物体。** 「书」和「电视」只以材质出现：`RK | Book pages and artwork`、`RK | Dark television glass`（https://github.com/KevinXu02/aha-3d/blob/main/assets/INDEX.md）。
   - 植物资产是脚本生成的，原文是 "Both versions are script-built"，白掌由 `tools/build_natural_plant_asset.py` 生成，"No photographic texture or external model is embedded"（https://github.com/KevinXu02/aha-3d/blob/main/docs/ASSET_QUALITY.md）。
   - 博客图集宣称有 "All 251 object assets"，但仓库只注册了 108 项（旧笔记已记录）。
5. **生成模型路线已经试过并搁置。** `docs/OBJECT_GENERATION.md` 第一段："an earlier object-generation pilot (SAM 3D Objects and TRELLIS.2) was completed and then deferred; its generation adapters are not included in this release. Room generation continues through registered asset reuse and Blender." 同一文件说生成网格 "are candidates for complex static furniture and decor"（https://github.com/KevinXu02/aha-3d/blob/main/docs/OBJECT_GENERATION.md）。`docs/omitted_references.json` 里列有未发布的 `tools/object_pilot/trellis2/README.md` 和 `tasks/trellis-pilot-20260909/HANDOFF.md`，说明试点大约在 2026-09-09（https://github.com/KevinXu02/aha-3d/blob/main/docs/omitted_references.json）。**搁置原因没有公开（未核实）。**
6. **SAM3 在 AHa-3D 里不做物体级实例分割。** 首次建参考时只按文字提示分割 person/glass/mirror/floor/wall（旧笔记，semantic.py）。物体级的 SAM3 runner 是可选的，"not invoked automatically by the shared scene workflow"（https://github.com/KevinXu02/aha-3d/blob/main/docs/OBJECT_GENERATION.md ；https://github.com/KevinXu02/aha-3d/blob/main/docs/install/object-tools.md）。所以**流程里没有任何自动的物体清单或召回机制**，物体清单全靠 Astra 看帧来定。

### 1.3 物体数量和类别

- 博客没有给任何物体计数或类别统计。
- 仓库 office48 白模的 README 写的是 "401 objects: walls, beamed ceiling, windows, glazed door, trestle desk, swivel and guest chairs, ladder shelf, side cabinet, chandelier and props"（https://github.com/KevinXu02/aha-3d/blob/main/examples/office48/README.md）。注意 401 是 Blender 对象数，不是语义实例数。
- 卧室例子的逐项复核共 21 个语义项（见 1.2 第 3 条）。

### 1.4 作者自述的失败模式

- 博客 Limitations："very small objects and objects with complex structures remain difficult to reconstruct accurately, and the fine details may be missing or simplified"。另外两条是：依赖昂贵的 GPT-6 Astra、没在其他模型上测过；人和物体的接触不保证物理正确（https://kevinxu02.github.io/real2sim-indoor-site/sections/limitations.html）。
- 博客 Motivation："it can still miss objects or get their shapes, sizes, and positions wrong"（https://kevinxu02.github.io/real2sim-indoor-site/sections/starting-point.html）。
- README："Opus 5.5 can also drive this repository based on initial experiments, but it has not been fully tested"（https://github.com/KevinXu02/aha-3d/blob/main/README.md 第 109 行）。
- 公开的审查样例结论是 rejected，side_table 被建成了镂空支架，逐项复核写着 "final acceptance is pending"（见 1.2 第 3 条的链接）。

### 1.5 对学生计划的含义

- 「AHa-3D 小物体差」这一点有作者原话可以引用，当动机站得住。但要注意：AHa-3D 是**有意**把小物体降级的，任务说明里就写了 "approximate"。所以拿它的默认配置当小物体基线，审稿人会说这不公平。应该同时跑一个「提示里要求认真重建小物体」的 AHa-3D 变体当强基线。
- (b) 的「接生成模型」作者自己试过又搁置了。所以「接入 TRELLIS/Hunyuan」本身不能当贡献，但「**定量回答这条被搁置的路线值不值**」可以当贡献。

---

## 2. 10-08 以来的新邻居

检索方式：
- arXiv：cs.CV、cs.RO、cs.GR 的 pastweek 列表和 10-07/08/09 的 catchup（带摘要）；cs.CV/RO/GR/AI 的 10-12 new 列表。合计 2,064 条带摘要和约 1,800 条标题，用关键词过滤。
- OpenReview：ICLR 2027 api2 `notes/search`，10 个检索词，每词 100 条，去重后 702 篇。
- GitHub：10-07 之后新建的仓库搜索。
- WebSearch 若干次。

下表「首版日期」是 arXiv v1 日期。10-03 到 10-07 首版的几篇不在 10-08 的基线清单里，这次一并补上。

### 2.1 A 类：和 (a)(b) 直接重合，proposal 必须引用

#### GATOR: Generative and Agentic 3D Object Reconstruction From Casual Images（原文）

- arXiv 2610.11215，v1 2026-10-08。作者 Qirui Wu、Stan Birchfield、Hesam Rabeti、Angel X. Chang、Bowen Wen，单位是 NVIDIA 和 SFU。同时是 ICLR 2027 投稿 12nS7mYinw。
- 链接：https://arxiv.org/abs/2610.11215 ；https://arxiv.org/html/2610.11215 ；https://research.nvidia.com/labs/lpr/gator/ ；https://openreview.net/forum?id=12nS7mYinw
- **输入**：一张到十张随意拍的图片，目标物体可能在杂乱桌面或房间里被遮挡。另外给目标 mask，相机和深度可以是估计值：Toys4K 上用 Pi3X，ScanNet++ 上用 VGGT 家族，mask 由 SAM3 推断。
- **几何来源**：在 TRELLIS.2 上微调。结构 denoiser 从 1.3B 的 TRELLIS.2 结构模型初始化，加一个 "local modality mixer"，融合 RGB、pointmap 和目标 mask，再加按阶段的文本条件。训练数据全部合成，约 98 万个物体资产。生成结果交给 GPT-6 Astra，经 Codex CLI 以 xhigh 推理强度在 Blender 里精修，每个物体 10 分钟预算，改坏了可以回退。
- **小物体**：评测对象本身就以小物体为主，包括 LM-O、HB、HANDAL 的桌面物体，以及 ScanNet++ 的 229 个目标（49 个场景，图 4 里有餐具、风扇叶片、推车上的显示器）。但目标是给定的，**不评召回**，也**没有按尺寸分层**。
- **摆放**：生成器保留场景相对朝向，尺度和位置取自观测，再用可微渲染精修，物体组合进同一个场景。
- **主要数字**：距离都按参考物体直径归一化。

  | 设置 | 指标 | GATOR | 对照 |
  |---|---|---|---|
  | Toys4K，525 个物体，4 视角 | CD | 0.009 | Pixal3D-MV 0.011；GPT-6-Astra 从零建 0.013；TRELLIS.2 0.014 |
  | Toys4K | F1 | 0.757 | Pixal3D-MV 0.701 |
  | 桌面（LM-O/HB/HANDAL） | CD | 0.009 | Pixal3D 0.018；MV-SAM3D 0.019；GPT-6 0.016 |
  | 桌面 | ADD-SB@0.1 | 98.47% | — |
  | ScanNet++，229 个目标 | CD | 0.031 | GPT-6 0.033；RecGen 0.041；MV-SAM3D 0.042 |
  | ScanNet++ | F1 | 0.603 | GPT-6 0.581；RecGen 0.540 |

  - 消融（55 个 HANDAL 物体）：agent 精修把 CD 从 0.008 降到 0.007，PSNR 从 18.93 升到 19.60，但 IoU 从 0.739 **降**到 0.717。作者承认精修 "only slightly worsens CD, F1, and IoU on HANDAL"。
  - 时间：只用生成器约 0.5 分钟，已经胜过 GPT-6 用 20 分钟从零建模的结果（Toys4K 抽样的 10 个物体）。GPT-6 从零建模在 1 分钟预算下有效输出 0/10，2 分钟 5/10，5 分钟起才 10/10。
  - 仿真：ScanNet++ 会议室 15 个物体，精修前有 3 把椅子倾倒，精修后都能立住。
- **代码**：项目页写 "Code (Coming Soon)"。
- **对我们的意义**：
  - 它是 (b) 最强的已发表先例，而且给出了一个反直觉的数字：**GPT-6 Astra 每个物体给足 10 分钟、从零写代码建模，几何（CD）不输 TRELLIS.2，在 ScanNet++ 上还好于 MV-SAM3D 和 RecGen。** 所以「LLM 用基本体建不好，就该交给生成模型」不是普遍成立的前提，取决于预算。
  - 它的局限一节把 "open agents" 和 "automatic geometric verification of agent edits" 列为未来方向。
  - 它是**物体级**工作，没有房间级清单和召回，没有单目视频到整间房的设定，也没有按物体做路由决策（所有物体都先生成）。

#### LIVIN: Benchmarking Spatial and Embodied Intelligence in Digital Twins of Lived-In Homes（原文）

- arXiv 2610.12069，v1 2026-10-08，v2 10-09。16 位作者，单位本次没有核实。
- 链接：https://arxiv.org/abs/2610.12069 ；https://arxiv.org/html/2610.12069
- **输入**：建孪生用的是 floorplan、带位姿的多视角图像和米制扫描，**不是单目视频**。
- **规模**：30 个家、319 个房间、12,808 个物体实例，其中 1,559 个是铰接物体。平均每房间 40.15 个物体，密度 3.70 个/m²，两项都是表内各数据集里最高的（Table 1）。
- **几何来源，也就是路由**：GPT-6 Astra 作重建 agent，每个阶段后都有人工审核。agent 在实例识别阶段给每个实例打两组标签："articulated or non-articulated, and as large furniture or a small object"（App. B.2）。
  - 铰接物体由 agent 直接写 Blender 代码，"in-context construction"。
  - 非铰接物体先用 GPT-Image-2 把参考视图清理成 "product-style" 图，再交给 Rodin 生成网格，agent 估尺度和位姿后摆放。
  - 人工审核时，有问题的非铰接物体直接用 Rodin 重生成（Sec. 4.3、4.4，Table 7）。
- **小物体**：
  - 「家具还是小物体」这个标签只用来决定摆放顺序。
  - 实例识别阶段 agent 会 "revisiting densely populated regions" 去找被遮挡的物体（Sec. 4.1）。
  - **评测上有 small clutter 子集（App. D，Table 8）**：先按 GT 名称筛出杂物类，再按物理尺寸和投影尺寸筛小目标，去掉几乎看不见的实例，共 306 条「物体-视图」记录。结果（覆盖率 / 3D 框召回 / surface F-score）：

    | 方法 | 覆盖率 | 3D 框召回 | F-score |
    |---|---|---|---|
    | Gen3DSR | 43.14% | 34.97% | 0.2586 |
    | RecGen | 100% | 42.48% | 0.3558 |
    | SAM3D | 100% | 53.59% | 0.3686 |
    | Fire3D | 95.42% | 72.55% | 0.5774 |
    | ShapeR | 100% | 85.95% | 0.7510 |

    注意：所有方法都拿到了 GT 实例 mask、深度和标定，Fire3D 和 ShapeR 还额外拿到 GT 有向框（Sec. 5.2）。所以这是「给定 GT 输入」下的小物体重建，不是端到端召回。
- **检测召回**：在 268 个房间上，类别无关、IoU 0.25 时的召回：Boxer 0.417，SpatialLM 0.111，SceneScript 0.083（Table 2）。作者结论："object recovery remains a major challenge in LIVIN's object-dense household scenes"。
- **构建消融**：只有定性图（Fig. 9），加上 token 数。Single-Round 和 Iterative Refinement 都超过 1 亿 token，作者自己的流程略多于 7,000 万（App. B.5）。**没有路由策略的定量比较。**
- **发布**：正文里没找到数据或代码链接，网页搜索也没找到项目页（**未核实**）。
- **对我们的意义**：
  - 「agent 判断大小和类型，然后分别走代码或生成」已经是 LIVIN 的标准做法。
  - 它的 Table 8 是目前唯一**单独评小物体**的场景级先例，但评的是非 agentic 方法，而且给了 GT 输入。
  - 如果 LIVIN 数据公开，它会是很好的小物体评测源：可以渲染成视频，有逐物体网格。

#### AffordCraft: Scalable Construction of Task-Ready Simulation Assets from Single Images（原文）

- arXiv 2610.06643，v1 2026-10-05。
- 链接：https://arxiv.org/abs/2610.06643 ；https://arxiv.org/html/2610.06643 ；代码 https://github.com/AffordCraft/AffordCraft （论文写已公开）
- **输入**：单张 RGB 图加任务指令。
- **几何来源**：从铰接资产库**检索**，再拟合到图像上，不做生成。
- **主要数字**（Table 1，按物理闸门判定通过；native 是原样交付即通过，adapted 是经过统一物理适配后通过；表格是用 MathML alttext 重新解析的）：

  | 方法 | 样本数 | native | adapted | 中位耗时 |
  |---|---|---|---|---|
  | AffordCraft | 2,000 张照片、31 类 | 85.15% | — | 40.0 s |
  | PhysX-Anything | 2,000 | 44.55% | 30.10% | — |
  | TRELLIS.2 | 2,000 | — | 23.60% | — |
  | Articulate-Anything | 200 张子集 | — | 35.00% | — |
  | **GPT-6 Astra agent** | 200 张子集 | **34.50%** | **22.00%** | 1423.0 s |
- **杂乱图像**：50 张 COCO 图、237 个标注物体，检到 172 个，通过 162 个。作者结论是 "Detection is the limiting step"（Sec. 4.3）。
- **对我们的意义**：这是「检索、生成、agent 从零建」三条路线在同一闸门、同一成本口径下的定量对比，但只到单物体和单图，没有路由策略，也不是场景重建。可以直接作为「路由值得比较」的动机引用。

#### CoDimRecon 的小物体补全环节（基线清单里已有，本次新读到的细节，原文）

- 链接：https://arxiv.org/html/2609.36024 ，Sec. 3.1 和 App. B.3。
- 每个 3D 轨迹都用 SAM3D 生成参考网格，agent 再参照它用 Blender 基本体重建。
- **App. B.3「Small Object Completion」**："Scene-level segmentation can omit small objects inside containers." agent 先找出已重建的容器，查看对应图像区域、取可见内容的 mask，再由 REST3D（arXiv 2605.30338，据 CoDimRecon 引用，本次未单独核实）用 SAM3D 生成缺失物体、放回容器。
- 原文明确写了 "**not a separately evaluated component**"。
- **意义**：agentic 的小物体补漏已经有人做了，但**没有评测**，这正是 (a) 能填的空。

#### GRASE（基线清单里已有，本节只为 (a)(b) 重提，旧笔记）

- ICLR 2027 投稿 NjJOSWydaG（https://openreview.net/forum?id=NjJOSWydaG ）。
- 设定：单目视频，GPT-6 VLM 列物体清单并区分大件和小件。大件由 VLM 经 Blender MCP 用基本体搭建；VLM 判断形状太差的大件，以及**所有小件**，用 TRELLIS.2 生成：先用图像编辑补全遮挡，每个物体生成 3 个候选，由 VLM 挑。
- 评测在 8 个 Replica 和 15 个 Imaginarium 场景上，指标有 CD、NC、F@5cm、实例 mIoU 和图像指标。
- 据 10-08 通读 PDF 的笔记：**没有按尺寸分层，没有路由消融，没有成本数据**；唯一的消融是几何 critic（来源：基线笔记 grase-reading.md）。
- 这是 (a)+(b) 设计上**最直接的撞车**，学生的方案必须正面区分。

### 2.2 B 类：相关的工具或旁证，可以选择性引用

| 工作 | ID / 日期 | 输入 → 输出 | 和我们的关系 | 读到的程度 |
|---|---|---|---|---|
| **GenIA**: Generative Reconstruction with Test-Time Input Alignment（Esposito、…、Kontschieder、Geiger、Luiten） | arXiv 2610.12388，10-08 | 单目、稀疏或动态观测 → SAM3D 生成的物体，在测试时对齐观测 | 不重训 SAM3D，平移和尺度从几何取，旋转沿用先验，外观靠可微渲染引导。可以作为 (b) 里「生成后对齐」的现成候选工具 | 摘要 https://arxiv.org/abs/2610.12388 |
| **RGBD-to-3D Object Mesh Refinement via Depth Matching and Symmetry Propagation**（ACCV 2026） | arXiv 2610.11187，10-08 | 任意 RGB 到 3D 的结果加深度 → 修正后的网格 | 全闭式、即插即用，单目伪深度也能用，比测试时优化快几个数量级。可以当生成物体的廉价对齐和修形工具 | 摘要 https://arxiv.org/abs/2610.11187 |
| **Why VLMs Miss Small Objects, and When Zooming In Is Safe** | arXiv 2610.09313，10-07 | 理论分析加约 177,000 次请求、797 张图 | VLM 漏检小物体是因为每个物体分到的视觉 token 太少，把图像加倍 token 只能让最大可达 S 提高 41%。切块放大在 "no view zooms out ... and views overlap by one object" 的条件下不会降低召回；在施工图纸上召回最多提高 0.28。**可以直接支撑 (a) 里「切块和放大做清单」的设计** | 摘要 https://arxiv.org/abs/2610.09313 |
| **ArticuTable** | arXiv 2610.05249，10-04；ICLR uZ5ENC7AfQ | 单图 → 带部件级铰接的桌面场景 | 桌面小物体先用 TRELLIS.2 出整体代理网格，再由 MLLM（GPT-5）拟合关节；推出 ArticuTable-100。代码 github.com/bryceyin13/articutable-code | 摘要加部分原文 https://arxiv.org/html/2610.05249 |
| **USDCraft** | arXiv 2610.11322，10-08 | 局部网格 → LLM 写程序生成铰接 USD 资产 | 「LLM 用程序建模、以局部几何为依据」这一端的代表，把已观测和未知空间分开描述 | 摘要 https://arxiv.org/abs/2610.11322 |
| **Artisan**（Towards Physically Grounded Articulated 3D Assets，Vedaldi、Shangzhe Wu 等） | arXiv 2610.13947，10-09 | 在 Articraft 基础上做多 agent 加物理仿真反馈 → 铰接资产 | 物体级，与路由无关，引用时可以作为程序化分支的代表 | 摘要 https://arxiv.org/abs/2610.13947 |
| **Tetris3D** | arXiv 2610.10539，10-07 | 单图 → 物体之间相互咬合的场景生成 | 非 agentic，生成每个物体时以邻居几何为条件；构建了 120 万场景的 ComOb 数据集 | 摘要 https://arxiv.org/abs/2610.10539 |
| **DistScene** | arXiv 2610.06960，10-03 | 单图 → 环境加物体的组合式场景 | 非 agentic | 摘要 https://arxiv.org/abs/2610.06960 |
| **Building Rome from a Single Image** | arXiv 2610.08790，10-06 | 单图 → 室内外场景网格 | 把 TRELLIS 2 改造为按距离分块的场景生成；在 ScanNet++ 上评测 | 摘要 https://arxiv.org/abs/2610.08790 |
| **Hi3D 3.0 (Twinkle3D)** | arXiv 2610.11685，10-08 | 单图 → 2048³ 水密网格 | 新的 image-to-3D 骨干，可替换 Hunyuan3D/TRELLIS；铭文字符召回 82.1% | 摘要 https://arxiv.org/abs/2610.11685 |
| **SceneEvolve**（Learning to Code the World: Harness Evolution for Compositional 3D Reconstruction） | ICLR wsMs7sVFKY | 单图 → 由基本体程序组成的场景 | 用强 teacher 改进 harness，模型本身不训练。Qwen3.8-27B 比 GPT-5.6-Sol 重建质量高 32.3%，部署成本低 59.8%。是 (c)「换小模型驱动」的直接先例 | 摘要 https://openreview.net/forum?id=wsMs7sVFKY |
| **WorldSculpt** | ICLR OU5l8NvsOq | grounded video → 数百个互相遮挡的物体网格 | 稠密杂乱场景的组合式生成，自建了带逐物体标注的稠密杂乱基准，可能是小物体评测源 | 摘要 https://openreview.net/forum?id=OU5l8NvsOq |
| **ReconAgent** | ICLR fVzLs20zdl | 5 视角 → 室内表面重建 | agent 决定在哪里补视角、接受哪些生成证据 | 摘要 https://openreview.net/forum?id=fVzLs20zdl |
| **FuncRoom-Agent** | ICLR 0d7DLdcNit | 文本 → 功能性房间，含 "dense support-surface and nested small objects" | 生成任务，不是重建；把构建轨迹蒸馏成单遍执行的专家，再用过程奖励做 RL | 摘要 https://openreview.net/forum?id=0d7DLdcNit |
| **Splat2Act** | arXiv 2610.13945，10-09 | 手机扫描 → 3DGS 数字孪生 → 个性化 VLA | real2sim2real，不重建 Blender 物体，相关度低 | 摘要 https://arxiv.org/abs/2610.13945 |
| hku-sail/Real2Sim_GPT6_ASTRA | GitHub，2026-09-07 到 09-10，86 星 | 三视角机器人 RGB → Blender 重放 | 不在基线清单里，AffordCraft 引用了它。提交记录里有 "Add three-stage ASTRA model cascade"，与降成本相关 | README https://github.com/hku-sail/Real2Sim_GPT6_ASTRA |

另外两篇在旧笔记 aha3d-paper-maps.json 里只记过名字，这次读了摘要：
- **BlenderWorld**（ICLR Nim9ZlB2Tu）：223 个任务，GPT-6-Astra 综合分 79.9。
- **Unravel**（ICLR moKm6yjmhc）：单图，逐层剥离加图像编辑，再按移除的逆序重建；把观测点云当作物体尺寸下界；"recovers more objects"。

检查过、判定不相关的：IRSTD-Agent（红外小目标）、Lifelong small-object navigation、M3SunAgent、NeRFifyMesh、Code2Games、VETR（BlenderGym 编辑），以及若干 4D、驾驶、医疗方向的论文。

---

## 3. 针对 (b)+(a)：谁做过「VLM 决定生成、基本体还是检索」，谁单独评过小物体

### 3.1 按物体路由的先例（最强 6 个）

| 工作 | 谁决定、按什么决定 | 各分支用什么 | 测了什么 | 没测什么 |
|---|---|---|---|---|
| **GRASE**（ICLR NjJOSWydaG，旧笔记） | VLM：小件一律生成；大件默认用基本体，VLM 判断「形状太差」时改为生成 | 基本体走 Blender MCP；生成用 TRELLIS.2，3 个候选由 VLM 挑 | Replica 8 个、Imaginarium 15 个场景的 CD、NC、F@5cm、实例 mIoU、PSNR 等；外壳单独评 | 路由消融、按尺寸分层、成本（据 grase-reading.md） |
| **LIVIN**（2610.12069，原文） | agent 打「铰接与否」和「家具/小物体」两组标签，**按是否铰接路由** | 铰接物体由 agent 写 Blender 代码；非铰接物体走 GPT-Image-2 加 Rodin；外加人工审核 | 数据集统计、用户研究；构建消融只有定性图和 token 数；小物体子集只评了其他方法 | 路由策略的定量比较；自家流程的小物体召回 |
| **LiteReality-Agent**（2610.01863，原文） | 按物体类型：结构化或铰接走程序化，"visually complex, predominantly static" 走 TRELLIS.2。原文是 "are routed"，没写由谁判断 | 程序化分支学 Articraft 写 object.py；生成分支用 TRELLIS.2，有坏网格检查和重试。小物体在第二阶段的第三个模块 "placing small objects" 中由 agent 添加 | RGB-D 输入，在采集视角上评测（旧笔记） | 路由消融、小物体指标（https://arxiv.org/html/2610.01863 Sec. 3.2–3.3） |
| **GATOR**（2610.11215，原文） | 不路由：所有物体都先生成，再由 agent 精修 | TRELLIS.2 微调版加 GPT-6 Astra，每物体 10 分钟 | 对照「生成+agent」「只生成」「GPT-6 从零建」，同为每物体 10 分钟，另有时间-质量曲线；多套物体级指标 | 场景级清单和召回、尺寸分层、按物体选择分支 |
| **AffordCraft**（2610.06643，原文） | 不路由：只做检索 | 检索加拟合，对照 5 个生成方法和 2 个 API 路线 | 2,000 张照片（API 路线是 200 张子集）的 native/adapted 物理通过率、中位耗时、每次通过的 GPU 分钟、API 成本；杂乱 COCO 图的检出和通过数 | 场景级、视频输入、尺寸分层 |
| **CoDimRecon**（2609.36024，原文） | 不路由：每个物体都先用 SAM3D 做参考，再由 agent 用基本体重建；容器里的小物体另走一遍补全 | SAM3D 参考网格加基本体；REST3D/SAM3D 做小物体补全 | 多视角 RGB，在 ScanNet++/Replica 上评 CD、F1、NC（旧笔记） | 小物体补全 "not a separately evaluated component" |

旁证（不在前 6）：
- HARMONY：所有物体都用 Hunyuan3D-2 生成，装饰物最后放、由 VLM 判断由哪件家具支撑。动机一节写了 "small objects such as decorations can be difficult to resolve in monocular images"。没有小物体指标（https://arxiv.org/html/2609.26793 ）。
- VIGA：`get_better_assets` 工具可以调 SAM-3D，由 agent 决定是否调用（旧笔记）。
- SceneSmith：静态物体用文生 3D，铰接物体检索，最后单独一层放小物件；是文生场景，不是重建（旧笔记）。
- SceneWeaver：LLM planner 从工具库里选生成工具（旧笔记）。
- AHa-3D 自己：试过 SAM 3D Objects 和 TRELLIS.2，后来搁置（第 1.2 节）。

### 3.2 单独评过小物体或召回的先例

| 工作 | 怎么评 | 数字 | 局限 |
|---|---|---|---|
| **LIVIN Table 8**（原文） | 先按 GT 名称筛杂物类，再按物理尺寸和投影尺寸筛小目标，共 306 条「物体-视图」记录；报覆盖率、3D 框召回、surface F-score | 召回从 Gen3DSR 的 34.97% 到 ShapeR 的 85.95%；SAM3D 53.59% | 给了 GT mask、深度、标定，部分方法还有 GT 框；只评非 agentic 方法；只有一个尺寸档，没有分层曲线 |
| **LIVIN Table 2**（原文） | 268 个房间，类别无关 3D 检测，Hungarian 匹配 | 召回@0.25：Boxer 0.417，SpatialLM 0.111，SceneScript 0.083 | 是检测，不是重建 |
| **AffordCraft Sec. 4.3**（原文） | 50 张 COCO 杂乱图、237 个物体：检出数和通过数 | 172/237 检出，162 通过 | 单图，不按尺寸 |
| **GATOR**（原文） | 对小桌面物体做物体级几何和位姿评测；ScanNet++ 上 229 个目标 | 见第 2.1 节 | 目标给定，**不评召回**；不分尺寸 |
| **Scenix**（原文，反例） | 召回和 F1 时 "a fixed class-pattern filter **excludes small decorative objects** such as lights, tableware, books, wall ornaments, and hardware" | — | 说明现有场景程序类工作在评测时**主动排除**小物体（https://arxiv.org/html/2608.07012 ） |
| **Why VLMs Miss Small Objects**（摘要） | 2D VLM 的召回和每物体 token 数的关系，以及切块规则 | 施工图纸上召回最多提高 0.28 | 只到 2D 识别，不涉及 3D |
| Lucida/GizmoAct（旧笔记） | CA-1M 上 mAP_all 0.180、mAP_filter 0.390 | — | 不按尺寸，而且没有召回数字 |

**结论：** 在「agentic、单目视频、整间房到 Blender」这个设定下，没有任何工作按物体尺寸分层报告召回和几何精度。场景级唯一单独评小物体的是 LIVIN，但它给的是 GT 输入、评的是非 agentic 方法。

### 3.3 课程项目里仍然算新的部分（按把握从高到低）

1. **AHa-3D 的首次定量评测。** 博客、仓库、arXiv、OpenReview 里都没有任何数字，作者自己把消融标成 placeholders（旧笔记）。在有真值的单目视频上报 CD、F-score，以及逐物体的召回、尺寸误差和位姿误差。数据选择见第 5 节。
2. **按尺寸分层的评测。** 建议分 4 档：小于 15 cm、15–40 cm、40–100 cm、大于 1 m，阈值要在 proposal 里定死。把每个 GT 物体的结局拆成三类：漏检、检到但建坏、检到且建好。LIVIN 只有一档、而且给了 GT 输入；GRASE、CoDimRecon、HARMONY 都没有。
3. **同一 harness、同等美元下比较路由策略：**
   - (R0) AHa-3D 默认：基本体加检索，小物体近似；
   - (R1) 全生成，HARMONY/GRASE 小件那种；
   - (R2) 按规则：按尺寸或类别分，LIVIN/LiteReality 那种；
   - (R3) VLM 逐物体决定，GRASE 那种；
   - (R4) 生成后再由 agent 精修，GATOR 那种。

   目前没有人在场景级做过这个比较。GATOR 和 AffordCraft 只在物体级、单图上比过分支。
4. **场景级「美元-分层精度」曲线。** GATOR 只有物体级时间曲线，LIVIN 只报 token 总量，AffordCraft 只到单物体。
5. **小物体清单环节的改进加评测**，比如帧切块放大配合 SAM 3 文本提示，依据是 2610.09313。用分尺寸召回来评，同时检验 CoDimRecon 那种容器内补全有多少收益，它自己没评。
6. **(c) 换模型**：AHa-3D 只在 GPT-6 Astra 上跑过，Opus 5.5 只有初步实验（README）。和 SceneEvolve 不同，我们是视频和整间房的设定。不过 Agentic Real2Sim、SceneEvolve、Agentic RSR 已经报过「换模型或便宜模型」的结论（旧笔记），所以这一条只适合作为次要轴。

---

## 4. 红旗和绿灯

### 已经明显撞车，不要作为主贡献

- 「给 agentic 重建加 Hunyuan3D/TRELLIS 处理难建模物体或小物体」：GRASE、LIVIN、LiteReality-Agent、HARMONY、CoDimRecon、GATOR 都做了，AHa-3D 自己也试过后搁置。
- 「agent 对生成网格做 edit-render-review 精修」：GATOR 已经做了，而且有消融和时间曲线。
- 「agent 补漏小物体」：CoDimRecon 有容器内补全，ImScene 有检测 agent，LIVIN 会回看稠密区域，Scenix 和 HARMONY 有相关机制。
- 「按是否铰接或物体类型路由」：LIVIN、LiteReality-Agent。
- 「VLM 判断形状太差就改用生成」：GRASE。

### 风险提示

- GATOR 的数字说明，GPT-6 Astra 每个物体给 10 分钟从零建模，几何上并不差（ScanNet++ 上 CD 0.033，MV-SAM3D 是 0.042）。所以「生成一定更好」可能被我们自己的实验推翻，proposal 要写成一个**开放问题**，不要写成前提。
- AHa-3D 作者已经试过生成路线并搁置，说明工程上有坑：尺度、朝向、遮挡补全和摆放都可能出问题。
- GATOR 代码 "Coming Soon"，GRASE 在审，LIVIN 的发布情况不明。两个月内很可能出现「GRASE 或 GATOR 加评测」的后续工作。

### 仍然开放（截至 10-14 的检索范围）

- AHa-3D 的任何定量评测。
- agentic 单目视频到 Blender 场景的**分尺寸召回和精度**。
- **场景级、同等美元**的路由策略对比，以及成本-精度曲线。
- AHa-3D「生成路线为什么被搁置」的可检验版本：同一 harness 里开关生成分支，看分尺寸指标怎么变。

---

## 5. 对 10-19 一页 proposal 的具体建议（供参考）

1. **题目定位**改成评测和分析类：「AHa-3D 的首个定量评测，以及按尺寸分层的路由研究：同等成本下，什么时候该基本体、检索、生成，还是生成后精修？」方法上可以带一个轻量路由器和清单增强，但不要宣称它是新方法。
2. **必引用并逐一区分**：GRASE、LIVIN、GATOR、LiteReality-Agent、CoDimRecon、AffordCraft、HARMONY，再加上 AHa-3D 自己的 OBJECT_GENERATION.md。
3. **评测数据**的关键约束是要有小物体真值：
   - 旧笔记记录 ARKitScenes 3DOD 只标了 17 类，基本是家具，**测不了小物体**。要用 ARKitScenes 视频，就得配 CA-1M。CA-1M 的说法是 "exhaustively labels over 400K 3D objects on over 1K ... laser-scanned scenes"，许可是 CC BY-NC-ND（据旧笔记，未重新核对）（https://arxiv.org/abs/2412.04458 ）。
   - 或者用 ScanNet++：有 iPhone 视频、激光扫描真值、开放词汇语义标注，共 460 个场景（https://arxiv.org/abs/2308.11417 ）。GATOR 已经在 ScanNet++ 上扩出 229 个目标、49 个场景的物体协议，可以复用它的思路，但它的目标清单还没发布。
   - LIVIN 如果公开，可以作为第三个来源（渲染出视频）。
4. **小物体基线要公平**：R0 要有两个版本，一个用 AHa-3D 原始提示（"approximate small objects"），一个改成要求认真建小物体。
5. **预算**：旧笔记估算 AHa-3D 一个场景在 GPT-6 Astra 上约 12–22 美元（短上下文）。GATOR 精修每个物体 10 分钟，按每房间几十个物体算，生成后精修这一臂会很贵，所以要设物体级预算上限，并把成本作为一个评测轴。

---

## 6. 未核实和检索盲区

- **arXiv**：只覆盖到 10-12 公告，10-09 之后提交的论文还没上列表；10-13 没有公告。cs.CV pastweek 列表只有标题，10-07/08/09 用 catchup 补了摘要。cs.AI 只看了 10-12 一天。arXiv API 返回 429，没有用。
- **OpenReview**：ICLR 2027 共 10 个检索词，每词前 100 条；单篇 notes 接口触发了 Cloudflare challenge（403），PDF 没读。SceneEvolve、WorldSculpt、ReconAgent、FuncRoom-Agent、BlenderWorld、Unravel 都只读到摘要。
- **GRASE**：「没有按尺寸分层、没有路由消融」来自 10-08 主会话通读 PDF 的笔记（grase-reading.md），本次无法重读原文。
- **LIVIN**：数据和代码是否发布、作者单位、Table 2 里 F-Score-S 的阈值数值（HTML 渲染丢了公式）都没有核实。
- **AHa-3D 生成试点被搁置的原因**：仓库没有给出，HANDOFF 文件被列在 omitted_references 里没有发布。
- **REST3D**（2605.30338）只在 CoDimRecon 的引用里看到，没有单独核对。
- 网页搜索结果里说 Code-as-Room 项目页写了 "code-only geometry can be insufficient for fine-grained small objects"，这句我没有在原文里核到，**未核实**，正文没有使用。
- **没有覆盖的渠道**：X/Twitter、知乎/小红书、CVPR 2027 投稿（尚未公开）、Google Scholar 的引用追踪。

---

## 7. 本次用到的主要链接

- AHa-3D：https://github.com/KevinXu02/aha-3d ；https://kevinxu02.github.io/real2sim-indoor-site/ ；docs/OBJECT_GENERATION.md、docs/LAYOUT_INSPECTION.md、docs/ASSET_QUALITY.md、assets/INDEX.md、examples/office48/README.md、docs/omitted_references.json（都在 https://github.com/KevinXu02/aha-3d/blob/main/ 下）；博客 sections/workflow.html、limitations.html、roomkit.html、starting-point.html；media/review.md、media/structured-review.json
- 新邻居：
  - GATOR https://arxiv.org/html/2610.11215 ，https://research.nvidia.com/labs/lpr/gator/
  - LIVIN https://arxiv.org/html/2610.12069
  - AffordCraft https://arxiv.org/html/2610.06643
  - GenIA https://arxiv.org/abs/2610.12388
  - RGBD-to-3D refinement https://arxiv.org/abs/2610.11187
  - Why VLMs Miss Small Objects https://arxiv.org/abs/2610.09313
  - ArticuTable https://arxiv.org/html/2610.05249
  - USDCraft https://arxiv.org/abs/2610.11322
  - Artisan https://arxiv.org/abs/2610.13947
  - Tetris3D https://arxiv.org/abs/2610.10539
  - DistScene https://arxiv.org/abs/2610.06960
  - Building Rome https://arxiv.org/abs/2610.08790
  - Hi3D 3.0 https://arxiv.org/abs/2610.11685
  - Splat2Act https://arxiv.org/abs/2610.13945
- ICLR 2027（只读摘要）：GRASE https://openreview.net/forum?id=NjJOSWydaG ；SceneEvolve https://openreview.net/forum?id=wsMs7sVFKY ；WorldSculpt https://openreview.net/forum?id=OU5l8NvsOq ；ReconAgent https://openreview.net/forum?id=fVzLs20zdl ；FuncRoom-Agent https://openreview.net/forum?id=0d7DLdcNit ；BlenderWorld https://openreview.net/forum?id=Nim9ZlB2Tu ；Unravel https://openreview.net/forum?id=moKm6yjmhc
- 已知邻居中本次核对过原文细节的：LiteReality-Agent https://arxiv.org/html/2610.01863 ；CoDimRecon https://arxiv.org/html/2609.36024 ；HARMONY https://arxiv.org/html/2609.26793 ；Scenix https://arxiv.org/html/2608.07012
- 数据集：CA-1M https://arxiv.org/abs/2412.04458 ；ScanNet++ https://arxiv.org/abs/2308.11417
