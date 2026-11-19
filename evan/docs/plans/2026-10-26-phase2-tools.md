# 第二阶段（P2，10/27–11/02）逐任务计划：清单、生成、放置、P0 和 A2/A3 的工具

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 到 11/02（G2）为止，P0、A2、A3r、A3v 要用的东西全部在开发集上跑通：两种物体清单、`gen3d_request`、`place_mesh`、校准过的验收门、P0 流水线、A2/A3 的提示词和 agent 工具。同时冻结评测协议，用本周额度先跑测试集的 A0/A1。

**Architecture:**
- 所有新工具只读 `perception/<id>/`（感知结果、高清帧、清单），只写 `gen/` 和 `runs/`。`scenes/<id>/` 只给评测用。
- 几何计算在项目自己的 venv 里做。三个 GPU 模型各用自己的 venv，通过子进程调用，靠文件交换数据：
  - SAM 3 用 AHa-3D 现成的 `sam3-segmentation` venv；
  - Boxer 用 `.runtime/boxer`；
  - Hunyuan 用 `.runtime/hy3d`。
- 生成和放置拆成两步，结果按 (帧, 掩码, 后端, 种子) 缓存。agent 和 P0 调的是同一套函数。

**Tech Stack:**
- Python 3.11、numpy/scipy，新增 trimesh 和 fast-simplification 两个包；
- SAM 3：AHa-3D 的 `tools/object_pilot/segmentation`；
- Boxer：facebookresearch/boxer，权重在 HF 的 facebook/boxer；
- Hunyuan3D-2mini：只生成形状，用 hy3dgen；
- Blender 5.2.1 无界面运行；bash 驱动脚本。

**Spec:** `docs/design.md`（§5 实验组、§6 工具、§8 高清帧、§9.5 漏斗、§15b 文件约定），`docs/research/notes/02-generative-3d-tools.md` §7.2–7.4（工具接口、失败处理），`docs/plans/2026-10-22-roadmap.md`（P2、G2）。

## Global Constraints

- AHa-3D 固定在提交 82f4b11，Blender 5.2.1，驱动 Codex CLI `gpt-6.1-sol`、推理强度 `medium`。不改全局 `~/.codex/config.toml`。
- 每次运行的上限按 `configs/run_caps.json`：墙钟 3862 s，工具调用 184 次。每天最多 6 次 agent 运行；单次运行让每周额度涨超过 15 个百分点就停下来问。
- fal 的付费调用每次都要先问，自掏腰包总共不超过 10 美元。
- 真值传感器数据（CA-1M 的位姿、激光深度、注册位姿、真值框）一律不进入流程，只给评测用。工具只能读 `perception/<id>/`、`gen/`、`configs/`，不能读 `scenes/<id>/`。
- **高清帧**：Pi3X 那 32 帧（`alignment/cameras.json` 的 `frames[].source_frame`），从 `scenes/<id>/input.mp4` 解码成原尺寸。位姿用 Pi3X 的，深度用 Pi3X 的点图上采样（设计 §8）。
- 评测协议在 Task 1 冻结之前，测试集一律不打分；冻结之后不再改。提示词和生成验收门槛只在开发集上调。
- 生成：
  - 最好那一帧的掩码小于 200 像素时，返回 `too_small`；
  - 裁剪四周留 15% 的边；
  - 网格清理后不超过 2 万个面，Z 朝上，原点在底面中心；
  - 每个场景最多生成 30 次。
- 验收门的初值（设计 §6，Task 10 校准）：
  - 多帧平均剪影 IoU ≥ max(0.6, 方块版 IoU + 0.03)；
  - 观测点到网格的 Chamfer ≤ max(1.5 cm, 0.1 × 最长边)；
  - 尺寸在框的 0.75–1.25 倍之间；
  - 穿进支撑面不超过 1 cm。
- A3r 的规则：清单里估计最长边小于 0.5 m 的物体走生成。
- 提交信息里不写 Co-Authored-By 之类的署名。文档和注释用中文。

## Review Focus

1. **GLB 的坐标轴约定。** Hunyuan 和 SAM 3D 导出的 glTF 是 Y 朝上，网格没转成 Z 朝上就放进场景，高瘦的物体会躺倒。期望：`clean_mesh` 统一转成 Z 朝上。测试在 Task 8，`test_clean_mesh_y_up_to_z_up`。
2. **清单物体在 32 帧里看不到或太小。** 期望：`gen3d` 返回 `too_small`（或 `no_view`），P0 和 agent 照常退回方块，不报错。测试在 Task 8 `test_too_small_and_no_view` 和 Task 11 `test_p0_falls_back_to_box`。
3. **agent 运行中生成器显存不够。** Blender 渲染和 Hunyuan 同时占 12 GB 显卡。期望：后端遇到 CUDA OOM 时返回 `backend_error`，agent 的运行不被拖崩。测试在 Task 8 `test_backend_oom_is_backend_error`。
4. **工具不碰真值。** 期望：agent 调工具时的命令行里只出现 `perception/`、`gen/` 下的路径，审计（`runlog.audit_gt_access`）不报。测试在 Task 12 `test_agent_tool_paths_pass_gt_audit`。
5. **竖拍场景和"拉伸"的内参。** Pi3X 的流程帧是把原图直接拉伸到 364×266 的，不是裁剪，所以高清内参在两个方向上的缩放不同；竖拍视频宽高互换。期望：高清内参 = diag(W/w, H/h, 1)·K。测试在 Task 4 `test_hd_intrinsics_anisotropic` 和 `test_hd_portrait`。

---

### Task 1: 按 G1 的决定冻结评测协议（等 10/26 当面的答复）

**Files:**
- Modify: `src/smallobj/evaluate.py`（`match`、`_strict_D`）、`src/smallobj/configs.py`、`configs/thresholds.json`、`docs/design.md` §9.4
- Test: `tests/test_evaluate.py`

**Interfaces:**
- Produces（thresholds 新键，后面所有打分都读这些）：
  - `match_mode`：`"hungarian"` 或 `"greedy"`；
  - `strict_floor_m`：判据 D 的距离下限，单位米，0 表示不设；
  - `loose_abs_m`：从敏感性分析升为正式口径时设 0.30，否则不设这个键。

- [ ] **Step 1:** 把 G1 的答复写进 `docs/design.md` §9.4，删掉"待 G1 确认"那一段。要写清五件事：
  - 事后改协议是否认可；
  - 配对方式；
  - "建出来"是否加 30 cm 门槛；
  - "建对了"是否加 10 cm 下限；
  - A0 用哪个保真度。
- [ ] **Step 2: 测试**
  - `test_greedy_keeps_correct_pair`：p1 正好在 g1 上，同时也在 g2 的宽松门槛内；p2 只在 g1 的宽松门槛内。
    - `match_mode="greedy"` 时，配对结果是 `[(0, 0)]`，g1 判 correct，g2 判 missed；
    - `"hungarian"` 时，两个都判 misplaced。
  - `test_strict_floor`：真值是 8 cm 的杯子，预测偏 6 cm。
    - `strict_floor_m=0.10` 时判 correct；
    - 等于 0 时判 misplaced。
- [ ] **Step 3:** 实现。
  - `match` 按 `th.get("match_mode", "hungarian")` 分支：贪心就是按代价从小到大取，两边都没用过的才配。
  - `_strict_D` 的距离条件改成"d̂ ≤ 0.5"或"中心距离 ≤ `strict_floor_m`"，两者满足其一即可，尺寸比的条件不变。
- [ ] **Step 4:** `.runtime/venv/bin/pytest -q` 全过。然后用新的 thresholds 重打开发集的 6 次运行，并重跑 `scripts/report_checkpoint.py`。
- [ ] **Step 5:** 提交（信息里写"协议冻结"），打标签 `protocol-frozen`，推送。从这一刻起才允许给测试集打分。

### Task 2: 无人值守运行的补强（测试集开跑之前做完）

**Files:**
- Modify: `src/smallobj/runlog.py`、`scripts/run_agent.sh`、`scripts/queue_runs.sh`、`scripts/report_checkpoint.py`
- Test: `tests/test_runlog.py`、`tests/test_report.py`

**Interfaces:**
- Produces:
  - `runlog.aha_acceptance(run_dir) -> {"accepted": bool | None, "source": str}`：按顺序读 `FINAL_STATUS.json`、`stopped_state.json`、`SUMMARY.md` 的第一行（含 "not accepted"、"unaccepted" 记 False，含 "accepted" 记 True）；
  - `run_log.json` 新增 `aha_accepted` 键；
  - `report.missed_rows(gts, th) -> list[dict]`：所有真值都记 missed。

- [ ] **Step 1: 测试**
  - `test_aha_acceptance_from_files`：三种文件各一个样例，外加一个都没有的（返回 None）。
  - `test_missing_blend_counts_all_missed`：一次没有 `.blend` 的运行，照样出现在漏斗里，n 不变，built 和 correct 都是 0。
- [ ] **Step 2:** 实现。
  - `write_run_log` 写入 `aha_accepted`。
  - `report_checkpoint.py` 遇到没有 `score_sim3.json` 的运行，用 `missed_rows` 补上，`runs.md` 里状态照写。
  - 可见性缓存的文件名带上流程分辨率和像素上限：`scenes/<id>/gt/visibility_<W>x<H>_<pixel_limit>.json`。
- [ ] **Step 3:** bash 部分：
  - `queue_runs.sh` 加环境变量 `SCORE`（默认 1）；为 0 时跑完不打分；
  - `timeout` 加上 `-k 60`；
  - `queue_runs.sh` 开头用 `flock -n "$PROJ/runs/.queue.lock"` 加锁，拿不到锁就退出码 4；
  - 每个 job 开跑前查一次每周额度，`weekly + 10 > 95` 就退出码 3。
- [ ] **Step 4:** 用假 codex 跑端到端检查（做法和 10-23 一样，脚本放 scratchpad）：
  - 两个队列同时起，第二个退出码 4；
  - 每周额度 90% 时不开跑。
- [ ] **Step 5:** pytest 全过，提交。

### Task 3: 测试集的 A0/A1 运行（等 G1 定下规模、感知分辨率、A0 的保真度）

**Files:**
- Create: `runs/queue-<日期>.log`（不进 git）
- Modify: `docs/plans/2026-10-22-roadmap.md` 的状态部分

- [ ] **Step 1:** 按 G1 的规模定名单：
  - A1 跑测试列表的前 N 个；
  - A0 跑前 5 个。

  N 由 G1 定，建议 10，顺序照 `configs/splits.json` 的 test 列表。感知用 G1 定的那一份；如果用 Betty 的结果，要先跑 Task 2 的可见性缓存。
- [ ] **Step 2:** 依次运行 `bash scripts/queue_runs.sh "A1 <id> 0" … "A0 <id> 0"`（后台）。A1 排前面。
  - 本周额度 10/30 13:57 重置，重置前能跑多少跑多少；
  - 每天的 6 次上限由脚本自己管。
- [ ] **Step 3:** Task 1 冻结之前只跑不打分：用 `SCORE=0` 排队（Task 2 加的开关），冻结后再逐个跑 `scripts/score_run.sh` 补打分。
- [ ] **Step 4:** 每天在路线图的状态部分记一行：跑了几次、用了多少额度、有没有 infra 或 tool_cap。

### Task 4: 高清帧

**Files:**
- Create: `src/smallobj/hd.py`、`scripts/extract_hd.sh`
- Test: `tests/test_hd.py`

**Interfaces:**
- Consumes: `alignment/cameras.json`（`frames[].source_frame`、`c2w`、`intrinsics`、`processed_size_wh`），`pi3x/predictions.npz`（`local_points`、`conf`，按 `pi3x/inputs.npz` 的 `frame_indices` 对应帧）
- Produces:
  - `hd.extract_hd(video: Path, bundle_dir: Path, out_dir: Path) -> dict`。写出：
    - `out_dir/frames/<source_frame:06d>.png`（视频原尺寸）；
    - `out_dir/depth/<source_frame:06d>.npy`（float32，H×W，置信度低或在边缘的像素为 NaN）；
    - `out_dir/cameras.json`：`{"size_wh": [W, H], "frames": [{"source_frame", "c2w", "K"}]}`。

    返回 `cameras.json` 的内容。
  - `hd.load(out_dir) -> dict`，后面所有工具都用它读高清帧。
  - 默认输出到 `perception/<id>/hd/`。

- [ ] **Step 1: 测试**（用合成的 64×48 视频和假 bundle，流程尺寸 16×12）
  - `test_hd_frames_match_source_frames`：输出的帧号集合等于 `cameras.json` 里的 `source_frame` 集合，每张图都是 64×48。
  - `test_hd_intrinsics_anisotropic`：流程 K 的 fx=10、fy=10，`processed_size_wh=(16,12)`，原尺寸 (64,48)；高清 K 的 fx=40、fy=40，cx、cy 也按比例放大。另外用流程尺寸 (16,16)，确认 x、y 两个方向的缩放各算各的。
  - `test_hd_portrait`：48×64 的竖拍视频，`size_wh == [48, 64]`。
  - `test_hd_depth_upsampled`：`local_points` 的 z 处处等于 2.0，输出深度是 48×64 且处处等于 2.0；`conf` 为 0 的像素输出 NaN。
- [ ] **Step 2:** 实现。
  - 用 imageio 按帧号解码视频。
  - 深度用双线性上采样 `local_points[..., 2]`；`conf` 低于 bundle 里 `reference_build.json` 给的置信度门槛（没有就用 0.1），或 `non_edge` 为假的像素，设成 NaN。
- [ ] **Step 3: 在真实数据上核对**（写进提交信息）：对 45261575，用高清深度和 c2w 反投影，得到的点要和 `predictions.npz` 的 `points` 经过 `world_transform` 变换后的结果一致，中位误差 < 1 cm。如果对不上，说明 `world_transform` 里带了尺度，深度也要乘上这个尺度。
- [ ] **Step 4:** 给 20 个场景都跑一遍 `scripts/extract_hd.sh <id>`，pytest 全过，提交。

### Task 5: Boxer 清单

**Files:**
- Create: `src/smallobj/inventory.py`、`scripts/run_boxer.sh`、`configs/inventory_labels.json`、`.runtime/boxer/`（venv，不进 git）、`third_party/boxer/`（不进 git）
- Test: `tests/test_inventory.py`

**Interfaces:**
- Consumes: `hd.load`
- Produces:
  - `inventory.fuse(per_frame: list[dict], iou_min: float = 0.25) -> list[dict]`：先按置信度从高到低排；同一类别、3D IoU ≥ iou_min 的框合成一个。合并后的中心和尺寸按置信度加权平均，yaw 取置信度最高的那个；记下 `n_frames` 和 `best_frame`。
  - `inventory.from_boxer(raw_dir: Path) -> list[dict]`：把 Boxer 每帧的输出转成 `boxes.record`（`source="boxer"`），再加上 `frame`、`bbox2d_xyxy`、`score` 三个键。
  - `inventory.save(items, path)` 和 `inventory.load(path)`。每条记录除了 `boxes.record` 的字段，还有 `item_id`、`best_frame`、`bbox2d_xyxy`（最好那一帧，高清像素）、`n_frames`。
  - 输出 `perception/<id>/inventory.json`。
- `configs/inventory_labels.json`：固定的类别表，现在定下，不从真值类别里抄。内容：
  - ARKitScenes 的 17 类：cabinet、refrigerator、shelf、stove、bed、sink、washer、toilet、bathtub、oven、dishwasher、fireplace、stool、chair、table、tv_monitor、sofa；
  - 再加这些小物体：cup、mug、bottle、bowl、plate、book、laptop、keyboard、mouse、monitor、lamp、plant、vase、pillow、box、bag、basket、shoe、remote control、phone、clock、picture frame、speaker、towel、trash can、toy、candle、jar、tissue box、soap dispenser、cutting board、pot、kettle、microwave、toaster、fan、mirror、rug。

- [ ] **Step 1: 装 Boxer。** 克隆到 `third_party/boxer`，用 `.runtime/py311` 建 `.runtime/boxer/venv`，装 torch 2.7.1+cu128 和仓库的依赖，从 HF 下载 facebook/boxer 的权重。按 README 跑一次自带的示例。
  - 记下三件事：每帧输出的格式、是否已经做了多帧融合、世界系 z 朝上的断言写在哪。
- [ ] **Step 2:** 查重合：Boxer 论文用的 CA-1M 测试集是"val 前 10 段"，核对它和我们 22 个场景有没有重合，结果写进 `docs/design.md` §13 的 Boxer 那一行。
- [ ] **Step 3: 测试**
  - `test_fuse_merges_same_object_across_frames`：同一个杯子在三帧里各有一个框，位置抖动 1 cm，合并成 1 个，`n_frames == 3`。
  - `test_fuse_keeps_different_labels_apart`：位置重叠的 book 和 laptop 保持两个。
  - `test_from_boxer_fixture`：用 Step 1 得到的真实输出截一小段做 fixture，放在 `tests/fixtures/boxer_raw/`，转换后中心、尺寸、yaw 和原始值一致。
- [ ] **Step 4:** 实现 `fuse`、`from_boxer`、`save`、`load`。`scripts/run_boxer.sh <id>` 的流程：
  - 在 boxer venv 里运行 Boxer，输入高清帧、K、c2w，深度走 `sdp_from_depth`，类别用 `--labels`；
  - 原始输出写到 `perception/<id>/boxer_raw/`；
  - 再用项目 venv 调 `from_boxer`、`fuse`、`save`。

  如果 Boxer 自己已经做了多帧融合，就跳过 `fuse`，在提交信息里说明。
- [ ] **Step 5: 开发集合理性检查**（设计 §9.4 允许）：5 个开发场景各跑一次，用 Task 7 的"检测到"统计各档召回，写进 `results/inventory_dev.md`，不拿它调任何阈值。pytest 全过，提交。

### Task 6: 干净对照清单（SAM 3 掩码加 Pi3X 点）

**Files:**
- Create: `src/smallobj/clean_inventory.py`、`scripts/run_clean_inventory.sh`
- Modify: `src/smallobj/boxes.py`（把 `export_blend.fit_groups` 里最小面积矩形拟框的部分抽成 `boxes.fit_obb(points: np.ndarray) -> dict`，`export_blend` 改为调用它）
- Test: `tests/test_clean_inventory.py`、`tests/test_boxes.py`

**Interfaces:**
- Consumes: `hd.load`、`inventory.fuse`、`inventory.save`、AHa-3D 的 `tools/object_pilot/segmentation/run.sh`（文本提示，在 sam3 venv 里跑）
- Produces:
  - `clean_inventory.points_from_mask(mask: np.ndarray, depth: np.ndarray, K, c2w) -> np.ndarray`：返回世界坐标点，NaN 深度的像素丢掉，再丢掉离中位数最远的 10%。
  - `clean_inventory.build(hd_dir, masks_dir) -> list[dict]`：每帧每个掩码先拟一个框，然后 `fuse`。
  - 输出 `perception/<id>/inventory_clean.json`（格式同 Task 5），`source="clean"`。

- [ ] **Step 1: 测试**
  - `test_points_from_mask_backprojects`：常数深度 2 m、已知 K、c2w 是单位阵，一个 3×3 像素的掩码，反投影得到的点 z 都等于 2，x、y 和像素位置对应。
  - `test_fit_obb_recovers_rotated_box`：从 `export_blend` 原有的测试里搬过来（100 个随机框都能还原）。
  - `test_build_two_frames_one_object`：同一个物体在两帧里各有一个掩码，合成 1 个框，尺寸误差 < 5%。
- [ ] **Step 2:** 实现。用 `inventory_labels.json` 里的类别逐个做文本提示，得分 ≥ 0.5 的实例才保留。SAM 3 的输出写到 `perception/<id>/sam3_objects/`。
- [ ] **Step 3:** 5 个开发场景各跑一次，"检测到"召回和 Boxer 的并排写进 `results/inventory_dev.md`。pytest 全过，提交。

### Task 7: 漏斗加上"检测到"，以及高清分辨率下的"看得见"

**Files:**
- Modify: `src/smallobj/report.py`、`src/smallobj/score.py`、`scripts/report_checkpoint.py`
- Test: `tests/test_report.py`、`tests/test_score.py`

**Interfaces:**
- Consumes: `inventory.load`
- Produces:
  - `score.score_inventory(items, gts, transform, th) -> list[dict]`：对齐后跑 `evaluate.outcomes`，不做结构件过滤。
  - `report.funnel_counts(rows, visible, key="D", detected: dict | None = None)`：多一个 `"detected"` 计数，`detected` 是 gt_id 到 bool 的映射；为 None 时不出这一项。
  - 实验组和清单、分辨率的对应关系（`ARM_INVENTORY`）：
    - P0、A2、A3r、A3v、A4 用 `inventory.json`；
    - P0c 用 `inventory_clean.json`；
    - A0、A1 没有清单。

    用清单的组按高清分辨率算"看得见"，A0、A1 按流程分辨率算。

- [ ] **Step 1: 测试**
  - `test_funnel_detected_stage`：传入 `detected` 时，每档多一个 `detected` 计数，等于映射里为真的个数；传 None 时没有这个键。
  - `test_score_inventory_aligns`：用和 `test_score_predictions_after_alignment_all_correct` 一样的变换，清单框全部"检测到"。
- [ ] **Step 2:** 实现。漏斗图里，有清单的组画四根柱，没有的画三根。另外加一条"流程分辨率下看得见"的参考线（设计 §9.5）。
- [ ] **Step 3:** pytest 全过，提交。

### Task 8: `gen3d`：挑帧、掩码、裁剪、Hunyuan3D-2mini 后端、网格清理、缓存

**Files:**
- Create: `src/smallobj/gen3d.py`、`scripts/gen_backends/hy3d_shape.py`（在 hy3d venv 里运行）、`scripts/masks_for_items.sh`、`.runtime/hy3d/`（不进 git）
- Test: `tests/test_gen3d.py`

**Interfaces:**
- Consumes: `hd.load`、`inventory.load`、AHa-3D 的 `tools/object_pilot/segmentation/run.sh`（框提示）和 `tools/object_pilot/prepare_inputs.py`（`crop_rgba`）
- Produces:
  - `gen3d.project_box(item, cam, size_wh) -> (xyxy, truncation: float)`
  - `gen3d.pick_frames(item, hd: dict, sharpness: dict[int, float], k=3) -> list[int]`：按"投影框面积 × (1 − 截断比例) × 清晰度"排序。清晰度是框内拉普拉斯的方差，用 `scipy.ndimage.laplace` 算。框完全在画面外的帧不算。
  - `gen3d.crop_rgba(image, mask, margin=0.15) -> np.ndarray`
  - `gen3d.clean_mesh(mesh: trimesh.Trimesh, up="y") -> trimesh.Trimesh`：只留最大连通分量，减面到 ≤ 20000，转成 Z 朝上，最长边缩放成 1，原点放在底面中心。
  - `gen3d.cache_key(frame: int, mask: np.ndarray, backend: str, seed: int) -> str`：sha1 取前 12 位。
  - `gen3d.request(scene_id: str, item_ids: list[str], backend="hy3d_shape", n_candidates=2, seed=0) -> list[dict]`，每个候选一条：

    ```
    {"item_id", "candidate_id", "status", "frame", "mask_px", "mesh_glb", "seconds", "cost_usd"}
    ```

    - `status` 取 `"ok"`、`"too_small"`、`"no_view"`、`"backend_error"`、`"budget"`；
    - 文件写在 `gen/<scene>/<item>/c<k>/{mesh.glb, rgba.png, mask.png, gen.json}`；
    - 后端调用统一走 `gen3d.run_backend(name, rgba_png, out_glb, seed, timeout_s=300) -> dict`，用子进程，返回 `status` 和 `seconds`。
  - 每个场景的生成计数记在 `gen/<scene>/budget.json`，到 30 次以后返回 `budget`。

- [ ] **Step 1: 装 Hunyuan3D-2。** 克隆 Tencent-Hunyuan/Hunyuan3D-2 到 `third_party/`，建 `.runtime/hy3d/venv`（torch 2.7.1+cu128），只装形状部分，不装纹理需要的 CUDA 扩展，权重用 `tencent/Hunyuan3D-2mini`。然后用一张杯子的 RGBA 跑一次 `scripts/gen_backends/hy3d_shape.py`，记下耗时和峰值显存。
- [ ] **Step 2: 测试**
  - `test_pick_frames_prefers_big_unclipped_sharp`：在三帧里，同样大小、截断一半的那帧排在没被截断的后面；只有面积不同时，大的排前面。
  - `test_too_small_and_no_view`：最好那一帧的掩码只有 150 像素时，返回 `too_small`；投影框在所有帧都在画面外时，返回 `no_view`。两种情况都不调后端，fake 后端被调用 0 次。
  - `test_crop_margin`：掩码外接框 100×50，裁出来是 130×65。
  - `test_clean_mesh_y_up_to_z_up`：一个沿 Y 方向 3 倍高的长方体，清理后 Z 方向最长，底面 z=0，最长边等于 1。
  - `test_clean_mesh_keeps_largest_component`：主体加一个远处的小碎片，碎片被去掉。
  - `test_cache_hit_skips_backend`：同一个 key 第二次请求不调后端。
  - `test_backend_oom_is_backend_error`：fake 后端以 OOM 的错误退出，结果是 `backend_error`，不抛异常。
  - `test_budget_cap`：第 31 次请求返回 `budget`。
- [ ] **Step 3:** 实现。
  - 掩码：`scripts/masks_for_items.sh <id> <items.json>` 把每个物体在最好几帧的投影框当框提示，交给 AHa-3D 的 SAM 3 分割工具，输出写到 `perception/<id>/item_masks/<item>/<frame>.png`。
  - `request` 只读这些掩码，不在进程里加载 SAM 3。
- [ ] **Step 4:** 在 45261575 上对 3 个 XS 清单物体跑一遍，看一下生成的网格（用 Blender 渲染一张图），pytest 全过，提交。

### Task 9: `place_mesh`：初始化、ICP、剪影坐标搜索、验收

**Files:**
- Create: `src/smallobj/place.py`、`src/smallobj/silhouette.py`、`configs/gen_gate.json`（先写设计 §6 的初值）
- Test: `tests/test_place.py`、`tests/test_silhouette.py`

**Interfaces:**
- Consumes: `hd.load`、`gen3d` 的候选目录、`clean_inventory.points_from_mask`、`perception/<id>/item_masks/`
- Produces:
  - `silhouette.render_mask(points_world, K, c2w, size_wh, dilate_px=2) -> np.ndarray`（bool）：把网格表面采的 2 万个点投到图上，再膨胀。不用 nvdiffrast。
  - `silhouette.iou(a, b) -> float`
  - `place.place_mesh(scene_id, item_id, candidate_id, init="obb", dof=7, support_z: float | None = None) -> dict`，返回 PlacementResult，键照 02 号笔记 §7.2：
    - `object_id`、`status`、`backend`、`candidate_id`、`frame`、`seed`、`mesh_glb`；
    - `matrix_world`（4×4）、`scale_xyz`；
    - `fit`：`sil_iou_mean`、`sil_iou_min`、`n_views`、`chamfer_obs2mesh_cm`、`primitive_sil_iou`、`inlier_ratio`；
    - `input`：`mask_px`；
    - `seconds`、`blender_snippet`。

    `status` 取 `accepted`、`rejected_fit`、`too_small`、`backend_error`。结果写到 `gen/<scene>/<item>/c<k>/placement.json`。
  - `place.gate(fit: dict, size_ratio: list[float], penetration_m: float, longest_m: float, gate: dict) -> bool`
- 算法：
  1. **起点。** 尺度取清单框的尺寸（dof 7 用各向同性尺度，等于框的最长边；dof 9 三个轴各自取框尺寸）。yaw 每 10° 一个起点；朝上轴除了 +Z，再试 4 个横躺的方向（绕 X、Y 转 ±90°）。
  2. **ICP。** 观测点到网格采样点的单向最近邻（`scipy.spatial.cKDTree`），每次迭代解相似变换。尺度限制在框尺寸的 [0.75, 1.25] 倍。给了支撑面时，底面贴住 `support_z`。
  3. **剪影搜索。** 取得分最好的 3 个起点，对 (x, y, z, yaw, s) 做有界坐标搜索，步长减半 4 次，在 K = min(5, 可用帧数) 帧上算。目标函数 = (1 − 平均 IoU) + 0.35 × (1 − 最差 IoU) + 0.12 × 归一化 Chamfer。（GRASE 表 3 的权重抽取时有错位，要对照原文确认；如果原文不同，改成原文的值，并记一条 ruling。）
  4. **方块版 IoU。** 把清单框当成网格，用同样的帧和渲染方式算一遍。
  5. **验收。** 用 `configs/gen_gate.json`。

- [ ] **Step 1: 测试**（合成场景：3 台已知相机，网格是一个不对称的 L 形，按已知位姿摆放；掩码用同样的点投影渲染，观测点从可见表面采样，加 3 mm 噪声）
  - `test_render_mask_matches_projection`：单位立方体在正前方 2 m 处，掩码的外接框和 8 个角点投影的外接框差不超过 3 像素。
  - `test_place_recovers_pose`：初始化用一个加了扰动的框（平移 5 cm、yaw 20°、尺度 1.1）。结果要满足：平移误差 < 2 cm，yaw 误差 < 5°，尺度误差 < 3%，`status == "accepted"`。
  - `test_wrong_shape_rejected`：用球去配 L 形的观测，结果是 `rejected_fit`，因为剪影 IoU 不比方块版高 0.03。
  - `test_gate_size_and_penetration`：`gate` 函数在尺寸比 1.3 时返回 False，穿进支撑面 2 cm 时返回 False，其余都合格时返回 True。
- [ ] **Step 2:** 实现。`blender_snippet` 是一段能直接粘进 bpy 的代码：导入 GLB，再设 `matrix_world`。
- [ ] **Step 3:** 对 Task 8 生成的 3 个物体跑一遍 `place_mesh`，把叠图（掩码和剪影）存到 `gen/<scene>/<item>/c<k>/overlay_<frame>.png`，人工看一眼。pytest 全过，提交。

### Task 10: 验收门在 10 个开发物体上校准

**Files:**
- Create: `scripts/calibrate_gate.py`、`results/gate_calibration.md`
- Modify: `configs/gen_gate.json`

**Interfaces:**
- Consumes: `gen3d.request`、`place.place_mesh`、开发集的真值框（只给校准用，设计 §8 允许在开发集上调生成验收门槛）

- [ ] **Step 1:** 选物体。用固定种子 20261020，从 5 个开发场景 Boxer 清单里"检测到"了的物体中，抽 10 个 XS 和 S 档的。
- [ ] **Step 2:** 每个物体生成 2 个候选，各跑一遍 `place_mesh`，记录：
  - 每个候选的 `fit` 各项；
  - 放好后的框按判据 D 对真值的结局；
  - 方块版（清单框）的结局。
- [ ] **Step 3:** 写 `results/gate_calibration.md`。先列一张表；再定门槛，使"通过门槛的候选"按判据 D 的结局不比方块版差，同时尽量多放行。把定下的数值写进 `configs/gen_gate.json`，在 `docs/design.md` §6 的验收条件后面注明"10-xx 在 10 个开发物体上校准"。之后冻结，不再改。
- [ ] **Step 4:** 提交。

### Task 11: P0 流水线（不用大模型）

**Files:**
- Create: `src/smallobj/p0.py`、`scripts/run_p0.sh`、`scripts/blender_assemble.py`（在 Blender 里运行）
- Test: `tests/test_p0.py`

**Interfaces:**
- Consumes: `inventory.load`、`gen3d.request`、`place.place_mesh`、`score.score_run`（`export/objects.json` 已经存在时，`score_run` 跳过导出）
- Produces:
  - `p0.assemble(items: list[dict], placements: dict[str, dict | None]) -> list[dict]`：
    - 每个物体有 `accepted` 的放置结果时，用 `boxes.fit_obb` 对变换后的网格顶点拟框，`source="gen"`；
    - 否则用清单框，`source="box"`。
  - `p0.run_p0(scene_id, inventory: Path, run_dir: Path, backend="hy3d_shape") -> dict`：写出：
    - `run_dir/export/objects.json`；
    - `run_dir/placements.json`；
    - `run_dir/run_log.json`：状态、墙钟、生成次数、被接受的个数，`usage` 为空；
    - `run_dir/scene.blend`：用 Blender 导入接受的 GLB，加上作为方块的长方体。
  - 实验组名：`P0` 用 Boxer 清单，`P0c` 用干净对照清单。

- [ ] **Step 1: 测试**
  - `test_p0_falls_back_to_box`：3 个物体，放置结果分别是 accepted、rejected_fit、None（too_small）。输出 3 条，`source` 依次为 gen、box、box，后两条的中心和尺寸等于清单框。
  - `test_p0_objects_json_is_scoreable`：输出能被 `boxes.load` 读，`score.score_predictions` 不报错。
- [ ] **Step 2:** 实现，然后在 3 个开发场景上跑 P0 和 P0c，打分，重跑 `report_checkpoint.py`（漏斗图里会多出 P0 和 P0c 两组）。
- [ ] **Step 3:** pytest 全过，提交。

### Task 12: A2、A3r、A3v 的提示词和 agent 工具

**Files:**
- Create:
  - `configs/prompts/A2.md`、`A3r.md`、`A3v.md`；
  - `configs/requests/A2.json`、`A3r.json`、`A3v.json`，保真度都是 precise，和 A1 一样；
  - `scripts/agent_tools/gen3d_request`、`gen3d_status`、`place_mesh`（bash，调用 `$PY -m smallobj.cli ...`）；
  - `src/smallobj/cli.py`。
- Modify: `scripts/run_agent.sh`（实验组白名单和模板变量）、`src/smallobj/inventory.py`（`export_crops`、`route_rule`）
- Test: `tests/test_cli.py`、`tests/test_prompts.py`

**Interfaces:**
- Consumes: `gen3d.request`、`place.place_mesh`、`gen3d.pick_frames`
- Produces:
  - `inventory.export_crops(scene_id) -> Path`：在每个物体最好那一帧裁一张图，写到 `perception/<id>/inventory_crops/<item>.jpg`。
  - `inventory.route_rule(items, max_longest_m=0.5) -> list[str]`：A3r 走生成的物体 ID。
  - `smallobj.cli` 的子命令：
    - `gen3d-request --scene S --items a,b [--backend B]`：在后台起一个 worker，立即打印 `job_id`，任务文件写到 `gen/<S>/jobs/<job_id>.json`，里面有 `status` 和每个候选的结果；
    - `gen3d-status JOB`；
    - `place-mesh --scene S --item I --candidate K [--dof 7|9] [--support-z Z]`：打印 PlacementResult。
  - `run_agent.sh` 新增的模板变量：`{{INVENTORY}}`、`{{CROPS}}`、`{{TOOLS}}`、`{{SCENE_ID}}`。实验组白名单是 A0、A1、A2、A3r、A3v。
- 提示词要点：
  - **A2** = A1 加清单。清单里每一项都要处理：建出来，或者写明为什么跳过。处理结果写到 `$OUT/inventory_decisions.json`，格式是 `{item_id: {"action": "built" | "skipped", "object_id"?, "reason"?}}`。
  - **A3r** = A2 加生成工具。`route_rule` 列出的物体必须先调 `gen3d_request`，再调 `place_mesh`；accepted 的用 `blender_snippet` 导入，其余用方块。别的物体照旧用代码搭。不许改生成网格的材质。
  - **A3v** = 工具和 A3r 一样，由 agent 逐个决定生成还是用代码搭，决定和理由记进 `inventory_decisions.json`。

- [ ] **Step 1: 测试**
  - `test_prompt_templates_fully_rendered`：每个实验组的模板渲染后，不再含 `{{`。
  - `test_route_rule`：最长边分别为 0.3 m、0.49 m、0.5 m、1.2 m 的四个物体，只有前两个走生成。
  - `test_cli_job_file_schema`：用 fake 后端，`gen3d-request` 立即返回一个 `job_id`；任务文件最终的 `status` 是 done，里面的候选数等于 `n_candidates`。
  - `test_agent_tool_paths_pass_gt_audit`：把三个工具实际执行的命令行拼进一个假的 `events.jsonl`，`runlog.audit_gt_access` 返回空。
- [ ] **Step 2:** 实现。工具脚本的路径和参数写进提示词的 `{{TOOLS}}` 段，样例命令用 `perception/` 下的绝对路径。
- [ ] **Step 3: 开发集试跑**（驱动按 G1 的决定，Codex 或 Task 13 的 Claude），在 45261575 上 A2 和 A3v 各跑一次。看三件事：
  - `inventory_decisions.json` 是不是每一项都覆盖到了；
  - 生成的物体有没有被导入；
  - 审计报不报。

  有问题就改提示词，改动只在开发集上做。
- [ ] **Step 4:** pytest 全过，提交。

### Task 13: Claude 驱动（等 G1 决定 Claude 的分工）

**Files:**
- Modify: `scripts/run_agent.sh`（`DRIVER=codex|claude`）、`src/smallobj/runlog.py`
- Test: `tests/test_runlog.py`、`tests/fixtures/claude_stream.jsonl`

**Interfaces:**
- Produces:
  - `runlog.parse_claude_stream(path) -> dict`：键和 `parse_codex_events` 一样。`tool_calls` 数 `tool_use` 块；token 从最后的 `result` 事件的 `usage` 里取；另外多一个 `cost_usd_equiv` 键，取 `total_cost_usd`。
  - `run_agent.sh` 在 `DRIVER=claude` 时运行：

    ```
    claude -p "<prompt>" --output-format stream-json --verbose --model claude-opus-5-5 --dangerously-skip-permissions
    ```

    在 `$AHA` 目录下跑，输出写到 `events.jsonl`；看门狗改数 `tool_use`。AHa-3D 内部的审查步骤仍然调 `codex exec`，这会用掉少量 Codex 额度，要在报告里注明。

- [ ] **Step 1: 测试** `test_parse_claude_stream`：fixture 里有 3 个 `tool_use` 和一个 `result` 事件，解析出 `tool_calls == 3`，token 数和 `cost_usd_equiv` 也对。
- [ ] **Step 2:** 实现，然后在 office48 上用 Claude 跑一次 A0，记下 token、墙钟和美元等价成本，补进 `results/checkpoint/summary.md` 第 4 节。
- [ ] **Step 3:** pytest 全过，提交。

### Task 14: SAM 3D 后端（等 HF 审批通过，Betty 那边由 Mingjian 部署）

**Files:**
- Create: `scripts/betty/sam3d.sbatch`、`scripts/gen_backends/sam3d_job.py`
- Modify: `src/smallobj/gen3d.py`（后端 `sam3d_betty`）、`src/smallobj/place.py`（`init="backend_pose"`）
- Test: `tests/test_gen3d.py`、`tests/test_place.py`

**Interfaces:**
- Produces:
  - 批处理任务的目录格式：`gen/<scene>/sam3d_jobs/<job>/`，里面有：
    - `inputs.json`：每条是 `{item_id, frame, rgba, mask, pointmap}`；
    - `<item>_rgba.png`、`<item>_mask.png`；
    - `<item>_pointmap.npy`：这一帧的高清点图，在相机坐标系下。

    Betty 跑完写回 `<item>/mesh.glb` 和 `<item>/pose.json`。`pose.json` 是相机坐标系下的 `{"R", "t", "s"}`。
  - `place.backend_pose_to_world(pose: dict, c2w) -> np.ndarray`（4×4）。

- [ ] **Step 1: 测试** `test_backend_pose_to_world`：相机坐标系下的已知位姿，加上已知的 c2w，变换后的物体中心等于 c2w 作用在 t 上的结果，尺度保持不变。
- [ ] **Step 2:** 实现，把 `sam3d.sbatch` 交给 Mingjian 在 Betty 上试。
  - G2（11/02）时还没跑通，就按路线图改用 Hunyuan 加我们的配准，这一任务关掉。
  - 用 fal 核对位姿约定要先问 Yifan，并控制在 10 美元以内。
- [ ] **Step 3:** pytest 全过，提交。

---

## 执行顺序和闸门

- **10/27 先做：** Task 2，然后 Task 4。
- **Task 1、3：** 收到 G1 的答复后立刻做。Task 3 要在 10/30 13:57 每周额度重置之前尽量多跑。
- **Task 5–11：** 按顺序做，这是 G2 前的主线。
- **Task 12：** 依赖 Task 8、9。
- **Task 13：** 依赖 G1。
- **Task 14：** 依赖 SAM 3D 的 HF 审批和 Betty。
- **G2（11/02）要回答两个问题：**
  - SAM 3D 能在 Betty 上跑吗？
  - 验收门校准好了吗？P0 在开发集上跑通了吗？
