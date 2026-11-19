# 写作简报：期末项目组内讲解页（Apple 风格重做版）

所有写作 agent 共用这份简报。你只写自己分到的章节片段文件，不碰别人的文件，不改 `assets/` 里的公共文件（review.css、review.js、motion.js、widgets.js）。

## 这一页是什么

CIS 6220 期末项目（组名 3Heads1GPU：Yifan Hu、Mingjian Li、Yujing Li）的组内讲解页。项目一句话：**以 AHa-3D 为基线，第一次定量测出"视频转 3D 的 agent"在小物体上丢了多少、丢在哪一步；再在同一套流程、同样预算下比较几种小物体处理方式，给出成本-精度的权衡。**

用户（Yifan）对上一版的反馈原话："前端再好看一点太丑了，我需要像 apple 一样风格，然后图片和结构图，架构图多一点，这样清晰易懂。然后需要读和相关的 paper 列在最后附上连接。"

所以这一版的硬要求：

1. **用课程仓库里那套 Apple 风格资源和标记写法**（见下面"格式"）。
2. **图要多。** 每一节（h3）至少配一张图：优先用"逐步架构图"（`.arch`，点一步亮一块），其次是普通 `figure` 里的 inline SVG 示意图。机制、数据流、组件关系、前后对比、决策流程，凡是能画的都画。图要画"机制"，不要只画一排写着名字的方框：箭头要标注传的是什么（文件名、数据、动作），对比图要画出两边不同的那一处。
3. **清晰易懂。** 读者有人没有 3D 背景。每个机制按"大白话（生活类比）→ 真实机制 → 具体例子和数字 → 容易搞错的地方"讲。名词第一次出现就解释。

## 读者

三位组员，中文母语，深度学习学过一些，3D 视觉和 agent 可能是零基础。他们要靠这一页弄懂：前置知识、AHa-3D 怎么工作、我们改什么、怎么评、每一步谁做什么。

## 事实来源（唯一可信，按优先级）

1. **设计文档（定稿，决定都以它为准）**：`/home/user/6220/Project/ubuntu_final_project/docs/design.md`
2. 英文提案：`/home/user/6220/Project/ubuntu_final_project/docs/proposal/proposal.tex`
3. 调研笔记：`/home/user/6220/Project/ubuntu_final_project/docs/research/notes/01-landscape-update.md`（新论文、AHa-3D 现状、相关工作对照）、`02-generative-3d-tools.md`（生成模型、摆放、工具接口）、`03-datasets-metrics.md`（数据集、指标）、`04-compute-drivers.md`（Betty、驱动模型、价格）
4. AHa-3D 的深挖笔记（JSON，大）：`/home/user/6220/Project/CIS-6220-Deep-Learning-at-Scale/03-final-project/agentic-3d/notes/deep-aha3d.json`；GRASE 笔记：同目录 `grase-reading.md`
5. 上一版讲解页（内容已核过，可以复用文字和数字，但版式要换）：`/home/user/6220/Project/ubuntu_final_project/docs/explainer/old/v1-index.html`

**审稿已经纠正过的事实，必须照这个写：**
- GATOR（arXiv 2610.11215）给 GPT-6 Astra 每个物体 10 分钟从零写代码建模：ScanNet++ 上 Chamfer 0.033，先生成再精修 0.031，差得不多；**但桌面物体上是 0.016 对 0.009，差了将近一倍**。两组数字都要写，不能只写一组。
- "approximate small objects" 出自 AHa-3D 博客里一次对比实验（workflow ablation）的任务描述，**不一定是发布版的默认提示词**。
- LIVIN（arXiv 2610.12069）按"能不能开合"分流，**所有不能开合的物体（包括大家具）都交给 Rodin 生成**。
- 显示器多数落在 M 档（0.5–1.5 m），不要当小物体的例子。小物体例子用：杯子、瓶子、书、遥控器、鼠标、台灯。
- Boxer 训练时用过 CA-1M 训练集，在 CA-1M 上测属于"同源"，结果偏乐观；所以有干净对照（SAM 3 掩码 + Pi3X 点云拟合框）。
- SAM 3D Objects 官方要 ≥32 GB 显存，本地 12 GB 跑不了；正式实验部署在 Betty（课程额度），fal 自费上限 10 美元只用于核对位姿约定；11/2 前 Betty 装不通就改用本地 Hunyuan3D-2mini 加我们的配准。
- 订阅（ChatGPT、Claude Max）只能驱动 agent，跑不了 3D 生成模型。

**规则：**
- 不编数字。设计文档和笔记里没有的数字不写；自己算的估计值写明"估算"并给算法。
- 区分"事实"（论文、代码、数据集里有的）和"我们的设计决定"（设计文档里定的）和"推断"（写明"按我们的理解"）。
- 不跑模型、不下数据。可以用 `python3 -I` 做小算术验算。可以用 WebFetch/WebSearch 核实链接（D 组必须核）。

## 格式（必须照做）

先读这两样，照着写：
- 标记规范：`/home/user/6220/Project/CIS-6220-Deep-Learning-at-Scale/.claude/skills/building-weekly-review-pages/markup.md`
- 标准样板（看至少两章的写法，尤其 `.arch` 逐步架构图、`.box`、`figure`、`details`、表格）：`/home/user/6220/Project/CIS-6220-Deep-Learning-at-Scale/01-lectures/W12-thu-midterm-2/review/week6.html`（很大，用 grep 或 Read 分段看）
- 样式表（查 class 名）：`/home/user/6220/Project/ubuntu_final_project/docs/explainer/assets/review.css`

具体要求：
- 片段文件只含正文：从 `<h2 …>` 开始，不写 `<html>`、`<head>`、`<body>`、`<nav>`、`.content` 外壳。
- 章标题：`<h2 id="<章id>"><span class="num"><章号></span>标题</h2>`；节标题：`<h3 id="<前缀>-<名字>">N.M 标题</h3>`。id 用下面表里的章 id 和你的前缀，全页唯一。
- 框只用 markup.md 列的 class：`grandma`（大白话）、`detail`、`calc`（算例，每个数要验算）、`trap`（易错点）、`key`（必记结论）、`extra`、`plain`。每个 `.box` 里先放 `<span class="box-label">…</span>`。
- 逐步架构图：`.arch` > `.arch-title` + `.svg-wrap > svg` + `ol.arch-steps`。svg 用 `viewBox`，宽 ≤ 780，给 `width` 属性；`role="img"` 和 `aria-label`。第 k 个 `<li>` 对应 `data-s` 含 k 的元素；一般 3–7 步。
- SVG 配色只用 class：填色 `f0`–`f6`，描边 `stroke`（配 `fill` class 使用，如 `class="f1 stroke"`），箭头 `arrow` / `arrow-blue` / `arrow-red` / `arrow-green`，等宽字 `shape`，强调字 `lbl-accent`。**不写死任何十六进制颜色**（深浅色都要看清）。文字 12–13 号；`<text>` 不用设 fill（CSS 已设）。
- marker 的 id 加你的前缀（如 `c-m1`），marker 的 path 不设 fill 也行（样板里是继承）；参照样板写法。
- 普通示意图：`<figure><div class="svg-wrap"><svg …></svg></div><figcaption>这张图说明什么</figcaption></figure>`。
- **不要用 KaTeX 和 `$…$`**（这一页不加载公式库）。公式写成 `<code>` 或 `<pre><code>`，用 Unicode 符号（Σ、‖·‖、≤、×、θ）。
- **不要外部图片、不要 `<img>`**。所有图都是 inline SVG。
- 表格包在 `<div class="table-wrap">` 里。折叠用 `<details><summary>…</summary><div class="inner">…</div></details>`。
- 交互组件（只有 C 组有）：写在 `/home/user/6220/Project/ubuntu_final_project/docs/explainer/assets/widgets-proj.js`，用 widgets.js 的 `RW._u` 工具（`U.frame / U.slider / U.select / U.bind / U.get / U.setv / U.f`），组件名加前缀 `p-`；正文放 `<div class="widget" data-widget="p-xxx"></div>`（看样板里 widget 的外层写法）。颜色只用 CSS 变量。

## 写法（用户反馈过的硬要求）

- 一段只讲一件事，先说要点再给例子。段落尽量 ≤ 80 汉字，超过 120 字就拆。三项以上并列用清单。
- 不用破折号（——），不写"不是……而是……"翻案句，少用引出下文的冒号。
- 英文原句放句尾当出处：先用中文说完意思，再"原文是 <q>…</q>"。
- 大白话要具体（比如把 agent 比作装修队包工头：会看图纸、会叫师傅、自己也会动手；把漏斗比作安检通道的几道关）。

## 整页结构和锚点

| 章号 | 章 id | 标题（可微调） | 负责 | 节 id 前缀 |
|---|---|---|---|---|
| 0 | `ov` | 一页看懂这个项目 | A | `a-` |
| 1 | `pre` | 前置知识 | A | `a-` |
| 2 | `aha` | AHa-3D 是怎么工作的 | B | `b-` |
| 3 | `sys` | 我们的系统架构 | B | `b-` |
| 4 | `arms` | 七个实验组 | C | `c-` |
| 5 | `funnel` | 漏斗：小物体丢在哪一关 | C | `c-` |
| 6 | `gen` | 生成与摆放工具 | B | `b-` |
| 7 | `data` | 数据 | C | `c-` |
| 8 | `eval` | 评测 | C | `c-` |
| 9 | `cost` | 算力、驱动和花费 | B | `b-` |
| 10 | `steps` | 一步一步做 | D | `d-` |
| 11 | `team` | 分工与交接 | D | `d-` |
| 12 | `timeline` | 时间线和闸门 | D | `d-` |
| 13 | `risks` | 风险与退路 | D | `d-` |
| 14 | `train` | 训练加分项 | D | `d-` |
| 15 | `related` | 相关工作 | D | `d-` |
| 16 | `reading` | 必读论文与阅读清单 | D | `d-` |
| 17 | `gloss` | 术语表 | D | `d-` |

跨章链接只用上表的章 id（`<a href="#eval">第 8 章</a>`），不要链别人的节 id。

## 输出文件

每章一个文件：`/home/user/6220/Project/ubuntu_final_project/docs/explainer/parts/<两位章号>-<章id>.html`，例如 `parts/04-arms.html`。

## 交付前自查

1. 跑 `python3 /home/user/6220/Project/CIS-6220-Deep-Learning-at-Scale/.claude/skills/building-weekly-review-pages/scripts/check_page.py <你的片段>`（片段阶段跨章断链可以忽略；它报破折号、"不是…而是"、标签不闭合、id 重复）。
2. 每个 SVG：文字不和框线、箭头重叠（按坐标算一遍）；`data-s` 步数和 `<li>` 数一致；没有十六进制颜色。
3. 回报：写了哪些文件、每章的 h3 列表、画了哪些图（每张一句话）、不确定的事实。
