# video2sim-align（本机试跑区）

期末项目「AHa-3D + Lucida/GizmoAct 融合」在 Ubuntu 上的工作目录。方案和分工见课程仓库的
`03-final-project/agentic-3d/RUNBOOK.md`（只读），这里先跑通手册第 1 周里 Yifan 负责的部分：
**装好 AHa-3D → 在 office48 上跑通 → 写 ICP 对齐器**。

## 文件夹

```
video2sim-align/
  README.md            本文件
  scripts/             分步脚本，按编号运行；每个新终端先 source scripts/env.sh
  third_party/aha-3d/  AHa-3D 源码（KevinXu02/aha-3d@82f4b11，和调研时核对的是同一版）
  data/office48/       office48 源视频（脚本 04 自动下载）
  runs/                每次运行一个新目录，不覆盖旧结果
  .runtime/            Python 3.11 底座、Blender 5.2.1（脚本自动建）
```

AHa-3D 自己的三个环境和权重在 `third_party/aha-3d/.runtime/` 里。所有东西都在这个文件夹内，
不改 conda base 和 env_isaaclab，删掉整个文件夹就能完全撤销。

## A. 免费部分：环境 + 参考几何（不调用大模型 API）

```bash
cd /home/user/6220/Project/Ubuntu_project/video2sim-align
bash scripts/01_install_static.sh      # 约 20–30 分钟，下载约 10 GB pip 包
bash scripts/02_blender.sh             # Blender 5.2.1，约 384 MB
third_party/aha-3d/.runtime/pi3x-inference/venv/bin/hf auth login   # 登录 HF，只需一次
bash scripts/03_weights.sh             # Pi3X 约 5.4 GB + SAM 3 约 3.5 GB
bash scripts/04_office48_reference.sh  # 在 10 秒视频上跑 Pi3X + SAM 3 + 定地板墙面
```

| 步骤 | 做完怎么算对 |
|---|---|
| 01 | 最后一行打印 `2.7.1+cu128 True NVIDIA GeForce RTX 5070 Ti ... (12, 0)` |
| 02 | 打印 `BLENDER_API_OK`；能打开作者的成品 `third_party/aha-3d/examples/office48/whitebox.blend` |
| 03 | 两个权重文件都在，`ls -lh` 能看到大小 |
| 04 | `runs/office48-reference-*/` 里有 `pi3x/`、`masks/`、`alignment/`、`mesh/`、`source_views/` 和 `reference_build.json`；打开 `source_views/` 的叠图，看点云和地板、墙是否贴住原画面 |

注意：
- HF 登录如果 `hf` 命令不存在，用 `"$PI3X_PY" -c "from huggingface_hub import login; login()"`。
  `facebook/sam3` 需要审批，你 HW2 时已经批过，用同一个 HF 账号即可。
- 作者只在 96 GB 显卡上验证过，24 GB 是他们的目标。本机 12 GB，脚本 04 默认 32 帧；爆显存就
  `bash scripts/04_office48_reference.sh 150000`（降低每帧像素），并在结果里记下这个改动。
- 脚本 04 会先看剩余显存，不到 9 GB 就退出。有别的 GPU 任务时等它结束，不要杀进程。
- 源视频取自项目主页，是网页压缩版（约 2 MB），作者原片没有公开，冒烟测试够用。

### 2026-10-09 实跑记录（A 段）

- **01**：SAM 3 环境最后的 `pip check` 报 `decord 0.6.0 is not supported on this platform` 后脚本退出。
  这是误报：decord 官方 wheel 标签写成了 `cp36-cp36m`，新版 pip 26 会把它判成不兼容，实际在
  Python 3.11 里能正常导入。没改 AHa-3D 的脚本，把 `tools/setup_reference.sh` 剩下的命令（SAM 3
  导入检查、建 Open3D 环境）照原样手动跑完，日志 `runs/logs/01b_manual_finish.log`。三个环境的导入检查都通过。
- **03**：Pi3X 权重是直接按固定版本下载的，SHA256 和 Hugging Face 上一致；SAM 3 checkpoint 3.3 GB。
- **04**：默认 255000 像素在 Pi3X 上爆显存（峰值约 11.3 GB，日志 `runs/logs/04_reference.log`，
  失败目录 `runs/office48-reference-20261009-115909` 保留不删）。改用 **150000 像素** 加
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` 后跑通：`runs/office48-reference-20261009-115943`，
  状态 `built; visual review required`。叠图看过，横梁、吊灯、窗户、书架和原画面对得上；
  SAM 3 在第 49–234 帧检测到一个人。显存峰值仍接近 11.7 GB，非常紧。

## B. 让 agent 搭出可编辑的房间（Claude Code + Haiku 5.5）

参考几何做完以后，「看视频、列物体清单、在 Blender 里搭房间、自查修改」这一段由 AI 编程 agent
按 `third_party/aha-3d/AGENTS.md` 和 `.agents/skills/` 里的技能文档去做。这里用 VSCode 插件里
最新的 Claude Code（`claude-haiku-5-5`），走你自己账号的额度。

```bash
bash scripts/05_agent_office48.sh runs/office48-reference-20261009-115943
```

- 请求文件 `configs/office48_whitebox_request.json` 已预填（白模、只要主要物体、输出静态图），
  AHa-3D 自己的 intake 校验结果是 `ready_for_authoring`，开头不会停下来问人。
- 给 agent 的任务说明是 `configs/agent_office48_prompt.md`，脚本把路径填进去后存到每次运行的 `prompt.md`。
- AHa-3D 的视觉审查写死调用 `codex exec`。`tools/codex-shim/codex` 是同名转接脚本，把审查请求转给
  Haiku 5.5：只开放 Read 工具让它真的打开每张图，按同一个 JSON Schema 回答。AHa-3D 本身没改。
  注意 AHa-3D 记录里的 `image_delivery.method` 仍会写成 `codex_exec_images`，实际审查员是 Claude。
- 每次运行的输出在 `runs/agent-office48-*/`：`session.jsonl`（完整会话）、`SUMMARY.md`（agent 写的总结）。
  agent 的中间文件按 AHa-3D 的规矩放在 `third_party/aha-3d/runs/` 和 `scenes/office48_v2s/` 下。
- `runs/agent-office48-20261009-120125` 是作废的一次：脚本把参考几何的相对路径传给了在另一个目录工作的
  agent，一分钟后手动停掉，脚本已修好。

## C. 写对齐器（手册 7.1，代码以后放 `aligners/`）

ICP 对齐器：Open3D point-to-plane ICP，只改位置和绕竖直轴的朝向，不改尺寸。它是最弱的对照，
1–2 天。输入输出格式要先和组员定好（手册 3.4 的「物体记录」JSON）。

### 2026-10-09 实跑记录（B 段）

`runs/agent-office48-20261009-120206`：Haiku 5.5，67 轮，5.7 分钟，按 API 价格折算约 0.56 美元
（输出 66k token，缓存读取 7.8M token）。agent 的总结是 `SUMMARY.md`；成品在
`third_party/aha-3d/runs/office48_v2s/whitebox-20261009-120206/room_v2/room.blend`，
源帧对白模的对比图是同目录下的 `renders/clay_v2/compare_sources.png`。

- 做到的：读懂了流程；复用了参考几何；自己查清了平面方程的正负号；用拟合平面定出三面墙
  （约 3.9 × 4.95 m，高 2.9 m）；用 RoomKit 资产搭了书桌、两把椅子、吊灯，书架和电视用方块代替；
  跑了两次摆放检查，修了一轮（书架插墙 6 cm 的错误已消除）；没有伪造任何验收记录。
- 没做到的：平顶（实际是带横梁的拱顶）；窗户和门在渲染里看不出是洞口；书桌放在房间中央
  （实际靠窗）；少了一把转椅和侧柜；159 个物体，作者的成品是 401 个。验收停在第一道关
  （没有登记候选版本），布局审查和逐物体审查都没跑。
- 它没有调用 `codex` 转接脚本做结构化审查，理由是「只是替身」并且没有候选版本。下次要在任务说明里
  写明可以用，并要求至少修三轮。

## D. ARKitScenes 单场景：数据 → 感知 → 打分 → ICP（2026-10-09）

一条命令跑一个场景（BVB 150 个 ARKitScenes 场景之一，下载约 1.2 GB，GPU 部分约 3 分钟）：

```bash
bash scripts/06_arkit_scene.sh 41125700      # 第二个参数是 Pi3X 像素上限，默认 100000
```

代码（按手册 3.3 的目录）：

| 文件 | 做什么 |
|---|---|
| `v2s/boxes.py` | 手册 3.4 的「物体记录」格式：中心、yaw、长宽高（米，z 朝上） |
| `v2s/arkit.py` | 读轨迹、内参、标注；**按位姿判断画面朝向**并转正；10 fps 视频 + 每帧真实位姿；真值框投影检查图；融合 LiDAR 点云 |
| `perception/sam3_furniture.py` | SAM 3 按 17 个类名逐帧分割，每个实例单独保存（AHa-3D 自带的会把同类合并） |
| `perception/lift.py` | 掩码 + Pi3X 点 → 对齐后世界里的物体点云；跨帧在 3D 合并；PCA 拟合初始框（手册里的「干净对照」） |
| `eval/score.py` | 手册 6.1 的打分：相机中心做重力约束的刚体/带比例对齐、匈牙利配对、F1@0.5/1 m、尺寸对数比、召回拆分、朝向误差（考虑对称） |
| `aligners/icp.py` | 手册 7.1 的 ICP：只动位置和 yaw，不改尺寸；残差是点到框表面的有符号距离，Huber 鲁棒高斯-牛顿 |
| `experiments/run_scene.py` | 打分 SAM3+PCA 和 +ICP，写 `scores.csv`、`summary.json` 和叠图 |
| `experiments/offline_align.py` | 手册 7.4 的离线测试缩小版：真值框推歪 10 次，看 ICP 修回几成，LiDAR 和 Pi3X 两种观测 |
| `tests/` | `test_score.py`（手册 6.2 的 4 个 + 相机对齐 1 个）、`test_icp.py`（3 个），8 个全过 |

运行测试：`source scripts/env.sh && "$PI3X_MESH_PY" -m unittest discover -s tests -v`

### 场景 41125700 的结果（17 个真值框：5 柜子、烤箱、灶台、2 沙发、3 桌子、4 椅子、水槽）

- **数据**：真值框投影回画面对得上（`data/arkitscenes/scenes/41125700/gt_projection_check.jpg`）。
  **坑**：`metadata.csv` 写的拍摄朝向是 `Up`，但位姿显示 1034/1064 帧是 `Left`，画面也确实是横的。
  照 ARKitScenes 官方 `rectify_im.py` 改为按位姿投票决定朝向。手册里「按 sky_direction 转正」要改成按位姿。
- **Pi3X 比例误差**（T1）：带比例对齐的比例 1.05，Pi3X 把房间估小约 5%（|log s| = 0.049）；
  相机高度 1.442 m 对真值 1.44 m；刚体对齐后相机位置 RMSE 0.17 m。
- **显存**：这段竖拍视频在 150000 像素也爆显存，用 **100000 像素**跑通。桌面程序占约 2 GB，Pi3X 的 F32 权重 5.4 GB。
- **SAM3+PCA 和 ICP**（`runs/arkit-41125700-perception/eval-01/`，刚体对齐、不看类别）：

  | | F1@0.5m | F1@1m | 召回@0.5m | 中心误差中位数 | 尺寸对数比中位数 | 朝向误差中位数 | 没检到/没对齐 |
  |---|---|---|---|---|---|---|---|
  | SAM3+PCA | 0.718 | 0.821 | 0.824 | 0.245 m | −0.45 | 35° | 1 / 2 |
  | +ICP | 0.667 | 0.821 | 0.765 | 0.232 m | −0.48 | 30° | 1 / 3 |

  框普遍偏小约 36%（只看到朝外的面），朝向偏差大；ICP 用的是拟合框的同一批点，又不改尺寸，所以没帮上忙。
  没检到的是客厅的茶几。
- **离线对齐测试**（`runs/arkit-41125700-perception/offline-align-01/table.json`，170 次）：ICP 修回率
  LiDAR 62.4%、Pi3X 46.5%；小扰动（<20 cm 且 <30°）LiDAR 9/9 全对。观测点按真值框位置裁出，数字偏乐观。

### 提案修订

`report/proposal/proposal-v2.pdf`（一页），加了上面这些初步结果。改动和出处见 `report/proposal/CHANGES.md`。
本机 LaTeX 用的是装在 `.runtime/tex` 里的 tectonic：`.runtime/tex/bin/tectonic -X compile proposal-v2.tex`。
