# 第一阶段：跑通基线，交中期检查 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10/26 之前，3 个 CA-1M 开发场景端到端跑通（数据 → 输入视频 → 感知 → A1/A0 agent → 导出 → 评测），拿出分档召回表、漏斗前几关和"一次运行花多少额度"。

**Architecture:** 我们的代码是 `src/smallobj/` 下几个小模块（数据、评测、可见性、导出、运行日志），用 pytest 测；重活交给复用的 AHa-3D 运行时（`third_party/aha-3d`，Pi3X、SAM 3、Blender 5.2.1 都已装好）和 Codex CLI。每个模块只读写设计文档 15b 节约定的文件。

**Tech Stack:** Python 3.11（项目自己的 `.runtime/venv`）、numpy、scipy、pytest、Pillow、imageio-ffmpeg、matplotlib；AHa-3D 的三套 venv；Blender 5.2.1；Codex CLI 0.162（`gpt-6.1-sol`，`medium`）。

**Spec:** `docs/design.md`（第 5、8、9 节和 15b 文件约定）；总路线图 `docs/plans/2026-10-22-roadmap.md`。

## Global Constraints

- 新代码、配置、结果都在 `/home/user/6220/Project/ubuntu_final_project/`；`/home/user/6220/Project/Ubuntu_project/` 只当运行时用，不挪、不改名，不改其中的 venv。
- 路径常量集中在 `scripts/env.sh`：`AHA=…/third_party/aha-3d`、`BLENDER=…/third_party/blender-5.2.1/blender`、`PI3X_PY`、`SAM3_PY`、`MESH_PY`（AHa-3D 三套 venv 的 python）、`CODEX=/home/user/.vscode/extensions/openai.chatgpt-26.1007.21434-linux-x64/bin/linux-x86_64/codex`、`PY=.runtime/venv/bin/python`。
- 驱动：`codex exec -m gpt-6.1-sol -c model_reasoning_effort="medium"`；不改 `~/.codex/config.toml`。
- 每天最多 6 次 agent 运行；任何一次运行让订阅用量涨超过 15 个百分点就停下来问 Yifan；fal 付费调用每次先问。
- CA-1M 的位姿、激光深度、真值框**只进评测**，不进 agent 的输入（输入只有 `input.mp4` 和 Pi3X 的感知结果）。
- 阈值（写进 `configs/thresholds.json`，10/20 定死的值，P1 不调）：`iou_strict=0.25`、`dhat_strict=0.5`、`size_ratio=[0.67, 1.5]`、`dhat_loose=1.0`、`iou_loose=0.1`、`visible_min_px=100`、`bin_edges_m=[0.2, 0.5, 1.5]`。
- 划分：22 个视频（design.md 8 节、03 号笔记 1.3 节的 ID），种子 `20261020`，5 开发 / 15 测试 / 2 备用。
- 中期检查用的感知：Betty 还没开通，笔记本上 Pi3X `pixel_limit=150000`，结果里注明"笔记本降分辨率"。
- 提交信息结尾加 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`；每个任务完成后 `git push`。

## Review Focus

1. **CA-1M 位姿约定**：`gt/RT.json` 是相机到世界还是世界到相机、世界坐标的大平移（z≈278 m）都可能让对齐静默失败。期望：对齐后 Pi3X 相机中心和真值相机中心的残差中位数 < 0.15 m。测试放在 Task 4。
2. **帧对应**：Pi3X 只取 32 帧，帧号经 `input.mp4` 映射回 CA-1M 时间戳；CA-1M 帧间隔不是严格 100 ms。期望：用真实时间戳建 `frame_map.json`，不按 fps 推算。测试放在 Task 2。
3. **竖拍视频**：部分 CA-1M 视频是 768×1024。期望：mp4 尺寸取原图尺寸、宽高为偶数，内参不转置。测试放在 Task 2。
4. **导出的非物体**：.blend 里的墙、地面、天花板、空节点会被当成预测物体。期望：按 AHa-3D 的语义路径前缀排除结构类，结构类真值也同样排除。测试放在 Task 5。
5. **agent 卡住或超时**：期望：`timeout` 到点后保留最后保存的 .blend，`run_log.json` 写 `status="timeout"`，照常打分。测试放在 Task 7。

---

### Task 1: 项目环境和骨架

**Files:**
- Create: `scripts/env.sh`、`src/smallobj/__init__.py`、`src/smallobj/boxes.py`（从 `Ubuntu_project/video2sim-align/v2s/boxes.py` 拷贝）、`pyproject.toml`（只写包路径和 pytest 配置）、`tests/test_boxes.py`
- Create: `.runtime/venv`（用 `Ubuntu_project/video2sim-align/.runtime/py311/bin/python3.11 -m venv`）

**Interfaces:**
- Produces: `smallobj.boxes` 原样保留旧接口 `record(object_id, category, center, yaw, size, confidence=1.0, source='gt')`、`corners(rec) -> (8,3)`、`from_obb(...)`、`transform(rec, yaw, translation, scale=1.0, source=None)`、`save(records, path)`、`load(path)`。

- [ ] **Step 1:** 建 venv，装 `numpy scipy pytest pillow imageio imageio-ffmpeg matplotlib`；`scripts/env.sh` 导出 Global Constraints 里的变量。
- [ ] **Step 2: 测试** `tests/test_boxes.py::test_corners_axis_aligned`：中心 (1,2,0.5)、尺寸 (2,1,1)、yaw 0 的框，8 个角的 x ∈ {0,2}、y ∈ {1.5,2.5}、z ∈ {0,1}；`::test_transform_yaw_90`：绕 z 转 90° 后尺寸不变、中心按旋转移动。
- [ ] **Step 3:** 拷贝 boxes.py，跑 `.runtime/venv/bin/pytest -q tests/test_boxes.py`，期望 PASS。
- [ ] **Step 4:** 提交、推送。

### Task 2: CA-1M 读取和输入视频

**Files:**
- Create: `src/smallobj/ca1m.py`、`scripts/prepare_scene.sh`、`tests/test_ca1m.py`

**Interfaces:**
- Consumes: `smallobj.boxes.record`
- Produces:
  - `download(video_id: str, split: str = "val", root: Path) -> Path`：`curl -C -` 断点续传到 `scenes/<id>/raw.tar`，已存在就跳过。URL `https://ml-site.cdn-apple.com/datasets/ca1m/{split}/ca1m-{split}-{id}.tar`。
  - `extract(tar_path: Path, scene_dir: Path) -> list[int]`：只解出每帧的 `wide/image.png`、`wide/image/K.json`、`gt/RT.json`、`gt/depth.png`、`gt/depth/K.json` 和整场景的 `world` 真值文件，返回按时间排序的时间戳（纳秒）。
  - `world_boxes(scene_dir: Path, structural: set[str]) -> list[dict]`：读世界真值框，转成 `boxes.record`（中心、尺寸、yaw；非纯 yaw 的框取重力对齐包围框），类别在 `structural` 里的去掉，写 `scenes/<id>/gt/boxes.json`。
  - `make_video(scene_dir: Path, fps: int = 10) -> Path`：按时间戳顺序写 `scenes/<id>/input.mp4`，同时写 `frame_map.json`（视频帧号 → 时间戳）。
  - `camera_track(scene_dir: Path) -> dict[int, np.ndarray]`：时间戳 → 4×4 相机到世界矩阵（约定按 apple-aiml-research/ml-cubifyanything 的 `dataset.py` 核实后统一）。

- [ ] **Step 1: 测试** 用 tarfile 在 `tmp_path` 里造一个 3 帧的小 tar（含竖拍 768×1024 一帧场景、帧间隔 90/110 ms）：`::test_extract_sorted`、`::test_frame_map_uses_real_timestamps`（frame_map 的值等于造的时间戳）、`::test_video_shape_even_and_upright`、`::test_structural_filtered`（"wall"、"floor" 被去掉，"cup" 留下）。
- [ ] **Step 2:** 跑测试，期望 FAIL（模块不存在）。
- [ ] **Step 3:** 实现 `ca1m.py`；先下载一个真实场景，打印世界真值文件名和类别清单，把结构类集合写进 `configs/thresholds.json` 的 `structural_categories`。
- [ ] **Step 4:** 测试 PASS；`scripts/prepare_scene.sh <id>` 对真实场景跑通，人工看一张"真值框投影到原图"的检查图，框落在物体上。
- [ ] **Step 5:** 提交、推送。

### Task 3: 划分和阈值配置

**Files:**
- Create: `scripts/make_splits.py`、`configs/splits.json`、`configs/thresholds.json`、`tests/test_configs.py`

**Interfaces:**
- Produces: `configs/splits.json` = `{"seed": 20261020, "dev": [...5], "test": [...15], "spare": [...2]}`；`configs/thresholds.json` 含 Global Constraints 的全部键加 `structural_categories`。

- [ ] **Step 1: 测试** `::test_split_sizes_disjoint`（5/15/2、互不重叠、并集等于 22 个 ID）、`::test_split_deterministic`（同种子两次结果相同）、`::test_thresholds_values`（逐键等于 Global Constraints 的值）。
- [ ] **Step 2:** 实现、生成两个文件；测试 PASS；提交推送。之后这两个文件不再改。

### Task 4: 感知结果和对齐

**Files:**
- Create: `scripts/run_reference.sh`（改自旧版，输出到 `perception/<id>/bundle/`）、`src/smallobj/align.py`、`tests/test_align.py`

**Interfaces:**
- Consumes: `ca1m.camera_track`、`frame_map.json`
- Produces:
  - `align_sim3(src: np.ndarray, dst: np.ndarray, gravity: bool = True, with_scale: bool = True) -> tuple[float, np.ndarray, np.ndarray]`（s, R, t；改自旧 `eval/score.align_gravity`）
  - `pipeline_to_gt(bundle_dir: Path, scene_dir: Path, with_scale: bool) -> dict`：取 AHa-3D 对齐后坐标系里 32 帧的相机中心，按 frame_map 找到 CA-1M 同一时刻的真值相机中心，返回 `{"s","R","t","residual_median_m"}`。

- [ ] **Step 1: 测试** `::test_sim3_recovers_known`（随机点经已知 s=1.3、绕 z 转 40°、平移后，恢复误差 < 1e-6）、`::test_gravity_only_yaw`（gravity=True 时 R 只绕 z）、`::test_no_scale`（with_scale=False 时 s=1）。
- [ ] **Step 2:** 实现，测试 PASS。
- [ ] **Step 3:** 按 splits 下载 3 个开发场景，`run_reference.sh` 跑 Pi3X（`pixel_limit=150000`）和 SAM 3 结构分割，记录耗时和峰值显存到 `perception/<id>/perf.json`。
- [ ] **Step 4:** 对 3 个场景跑 `pipeline_to_gt`，期望 `residual_median_m < 0.15`（Review Focus 1）；不满足就先查位姿约定，再继续。
- [ ] **Step 5:** 提交、推送。

### Task 5: 导出和评测

**Files:**
- Create: `src/smallobj/export_blend.py`、`src/smallobj/evaluate.py`、`scripts/score_run.sh`、`tests/test_evaluate.py`、`tests/test_export.py`

**Interfaces:**
- Consumes: `boxes`、`align.pipeline_to_gt`、`configs/thresholds.json`
- Produces:
  - `export_objects(blend: Path, out_json: Path) -> int`：Blender 无界面跑 AHa-3D 的 `tools/layout_inspection/export_model.py`，按 instance_id 分组，每组算重力对齐有向框（yaw 取 XY 顶点的 PCA 主方向），去掉结构类，写 `export/objects.json`，返回物体数。
  - `iou3d(a: dict, b: dict) -> float`（yaw 框：XY 凸多边形求交 × Z 重叠）、`dhat(pred: dict, gt: dict) -> float`（中心距离 ÷ 真值半对角线）、`size_bin(rec: dict, edges) -> str`（"XS"/"S"/"M"/"L"，按最长边）。
  - `match(preds, gts, th) -> list[tuple[int, int]]`：以 dhat 为代价的匈牙利匹配，只保留过宽松门槛的对。
  - `outcomes(preds, gts, th) -> list[dict]`：每个真值物体 `{"gt_id","bin","I","D"}`，I、D 各取 "correct"/"misplaced"/"missed"。
  - `summarize(rows) -> dict`：每档每判据的召回、misplaced 比例、个数。

- [ ] **Step 1: 测试**（8 cm 立方体真值，沿 x 平移预测）：
  - `::test_gt_vs_gt_all_correct`
  - `::test_iou_flip_at_4_8cm`：平移 4.7 cm 时 I 为 correct，4.9 cm 时为 misplaced（(8−d)/(8+d) = 0.25 ⇒ d = 4.8）
  - `::test_dhat_flip_at_3_46cm`：3.4 cm 时 D 为 correct，3.5 cm 时为 misplaced（半对角线 6.93 cm 的一半）
  - `::test_loose_edge_6_93cm`：6.9 cm 时为 misplaced，7.0 cm 时为 missed
  - `::test_bins_edges`：最长边 0.2 归 S、0.5 归 M、1.5 归 L
  - `::test_structural_excluded`：类别路径以结构前缀开头的导出物体不进预测
- [ ] **Step 2:** 跑测试，期望 FAIL；实现；期望 PASS。
- [ ] **Step 3:** `tests/test_export.py::test_office48_export` 对 `third_party/aha-3d/examples/office48/whitebox.blend` 导出，期望物体数 > 100、每个框尺寸为正。
- [ ] **Step 4:** 提交、推送。

### Task 6: 可见性（漏斗第 ① 关）

**Files:**
- Create: `src/smallobj/visibility.py`、`tests/test_visibility.py`

**Interfaces:**
- Consumes: `ca1m.camera_track`、CA-1M `gt/depth.png` 和 `gt/depth/K.json`、bundle 里 32 帧的帧号和处理后的分辨率
- Produces: `visible_pixels(box: dict, c2w, K, wh: tuple[int, int], depth=None, depth_K=None) -> int`（投影框表面采样点，深度比激光深度远 5 cm 以上算被挡），`visible_flags(gts, scene_dir, bundle_dir, wh) -> dict[str, bool]`（任一帧 ≥ `visible_min_px` 即可见）。A0/A1 用流程分辨率，A2 起用 1024×768（P2 才用到）。

- [ ] **Step 1: 测试** `::test_cube_pixels_match_pinhole`（10 cm 立方体正对相机 2 m，f=497：像素数在 25² 的 ±15% 内）、`::test_behind_wall_is_hidden`（深度图在 1 m 处有墙，2 m 处的框可见像素为 0）、`::test_behind_camera_zero`。
- [ ] **Step 2:** FAIL → 实现 → PASS；提交推送。

### Task 7: agent 运行器和额度测量

**Files:**
- Create: `scripts/run_agent.sh`、`configs/prompts/A0.md`（作者博客和 AHa-3D intake 的原任务描述）、`configs/prompts/A1.md`（加"逐个建出所有看得见的小物体，只用代码和方块，不能省略"）、`src/smallobj/runlog.py`、`tests/test_runlog.py`、`tests/fixtures/codex_events.jsonl`（取自第一次真实运行，截短）

**Interfaces:**
- Produces:
  - `scripts/run_agent.sh <arm> <scene_id> <seed>`：把 `input.mp4` 放进 AHa-3D 的 `scenes/<scene>/references/`，填好提示词，`timeout $CAP codex exec -m gpt-6.1-sol -c model_reasoning_effort="medium" --json --skip-git-repo-check -C "$AHA" "<prompt>" > events.jsonl`；结束后把最新的 .blend 拷到 `runs/<arm>/<scene>/<seed>/scene.blend`，写 `run_log.json`。
  - `parse_codex_events(path: Path) -> dict`：`{"input_tokens","cached_input_tokens","output_tokens","turns","used_percent_start","used_percent_end"}`（字段名以第一次真实运行的事件为准）。
  - `write_run_log(run_dir: Path, status: str, wall_s: float, usage: dict) -> None`，`status ∈ {"ok","timeout","crashed"}`。

- [ ] **Step 1:** 先在 office48（复用旧的参考结果）上用 A0 提示词跑一次，`CAP=3600`，拿到真实事件日志；记下这次额度用量。超过 15 个百分点就停下来问 Yifan。
- [ ] **Step 2: 测试** 用截短的真实日志：`::test_parse_tokens`（数值等于日志里最后一次累计值）、`::test_timeout_status`（模拟 timeout 退出码 124 时 `status="timeout"`，并保留 .blend）。
- [ ] **Step 3:** FAIL → 实现 → PASS；提交推送。

### Task 8: 开发场景上的基线和中期检查材料

**Files:**
- Create: `scripts/report_checkpoint.py`、`results/checkpoint/summary.md`、`results/checkpoint/recall_by_bin.png`、`results/checkpoint/funnel.png`

**Interfaces:**
- Consumes: Task 4–7 的全部接口

- [ ] **Step 1:** 3 个开发场景各跑一次 A1（每天 ≤6 次的护栏内）；额度允许再各跑一次 A0。
- [ ] **Step 2:** 每次运行：`export_objects` → `outcomes`（Sim(3) 和不修尺度两版）→ `visible_flags`。
- [ ] **Step 3:** `report_checkpoint.py` 出两张图：每档召回（I、D 两判据）；漏斗（看得见 → 建出来（宽松门槛内）→ 建对了）。另出一张表：每次运行的 token、墙钟、额度百分比。
- [ ] **Step 4:** 写 `summary.md`（中文一页，给组内；附英文三段，给助教）：做了什么、第一批数字、每次运行花多少额度、按设计文档第 5 节削减顺序给出的建议规模、下一阶段计划。注明"感知用笔记本降分辨率"。
- [ ] **Step 5:** 按 summary 里的额度结果写 `configs/run_caps.json`（墙钟上限 = A1 中位耗时的 2 倍），提交、推送，更新路线图状态。
