# smallobj-video2blender

CIS 6220 期末项目（3Heads1GPU：Yifan Hu、Mingjian Li、Yujing Li）：**视频转 3D 的 agent 在小物体上丢了多少、丢在哪一步。**
以 AHa-3D 为基线，在 CA-1M 的真实房间扫描上按物体大小分档评测，并比较几种小物体处理方式的成本和精度。

- 文档总目录（每份文档是什么、现行还是快照）：[docs/README.md](docs/README.md)
- 设计（定稿）：[docs/design.md](docs/design.md)
- 路线图、闸门和当前状态：[docs/plans/2026-10-22-roadmap.md](docs/plans/2026-10-22-roadmap.md)
- **当前计划**：[收尾计划（11/20 到 12/7）](docs/plans/2026-11-20-final-push.md)。之前的两份：[第二阶段](docs/plans/2026-10-26-phase2-tools.md)、分支 `scenerig-detection` 的[清单 v2 和 SAM 3D](docs/plans/2026-10-29-scenerig-detection.md)
- 报告：源文件在组员仓库的克隆 `third_party/agent_3d/paper/paper_file/`；收到的初稿和本机试编译的 PDF 在 [docs/report/](docs/report/)
- 课程算力（Betty、LiteLLM）怎么用：[docs/compute/betty-litellm.md](docs/compute/betty-litellm.md)

## 目录

| 目录 | 内容 | 进 git |
|---|---|---|
| `src/smallobj/` | 我们的代码：CA-1M 读取、对齐、评测、可见性、导出、运行日志、汇总出图；高清帧、两种物体清单、生成（`gen3d`）、放置（`place`）、P0、agent 工具（`cli`） | 是 |
| `tests/` | pytest（`.runtime/venv/bin/pytest -q`） | 是 |
| `scripts/` | 一条命令一件事：准备场景、算感知、跑 agent、打分；`scripts/betty/` 是 Betty 上用的 | 是 |
| `configs/` | 划分、阈值、运行上限、生成验收门、清单类别表、各实验组的提示词和请求 | 是 |
| `docs/` | 设计、计划（`plans/`）、调研笔记（`research/`）、算力指南（`compute/`）、会议材料（`meetings/`）、英文提案（`proposal/`）、报告 PDF（`report/`）、组内讲解页（`explainer/`）；目录见 `docs/README.md` | 是 |
| `third_party/` | AHa-3D（提交 82f4b11，含 Pi3X/SAM 3 环境和权重；`scenes/` 是每次运行的工作目录）、Blender 5.2.1、Boxer、Hunyuan3D-2、`agent_3d`（组员仓库的克隆，含报告源文件） | 否 |
| `scenes/<id>/` | CA-1M 场景：逐帧图和位姿、真值框、`input.mp4`、检查图（下载的原始包 `raw.tar` 解完后 11-20 已删，要用时 `prepare_scene.sh` 会重新下载） | 否 |
| `perception/<id>/` | 感知结果（笔记本 10 万像素）、高清帧 `hd/`、清单 `inventory.json`（Boxer）、`inventory_clean.json`（干净对照）和 `inventory_v2.json`（清单 v2）、生成用掩码 `item_masks/`；Betty 的 25.5 万像素结果拉回到 `perception_betty/` | 否 |
| `gen/<id>/<item>/c<k>/` | 生成的网格候选、`placement.json` | 否 |
| `runs/<arm>/<scene>/<seed>/` | 每次 agent 运行：提示词、事件日志、`scene.blend`、`run_log.json`、打分。`<arm>-claude` 是 Opus 主实验，不带后缀的是旧 Codex 对照；`_interrupted/`、`_superseded/` 是被打断和被重跑顶替的运行；`logs/` 是跑完的队列和批处理日志（正在跑的日志在 `runs/` 下，跑完再挪进去） | 否 |
| `results/` | 汇总表和图（中期检查、报告） | 是 |
| `.runtime/` | 项目 Python（`py311`、`venv`）、Boxer 和 Hunyuan 的环境（`boxer/`、`hy3d/`）、tectonic、`bin/`（codex、blender） | 否 |

## 一个场景从头到尾

```bash
source scripts/env.sh
bash scripts/prepare_scene.sh 45261575            # 下载 CA-1M、真值框、10 fps 输入视频、投影检查图
bash scripts/run_reference.sh 45261575            # Pi3X + SAM 3 感知（笔记本显存不够时自动降到 10 万像素）
DRIVER=claude bash scripts/run_agent.sh A1 45261575 0   # 主实验（10-27 起）：headless Claude Code + Opus 5.5 跑 AHa-3D，输出 runs/A1-claude/
bash scripts/run_agent.sh A1 45261575 0           # 不加 DRIVER 是旧的 Codex 对照（gpt-6.1-sol，medium），每天最多 6 次
bash scripts/score_run.sh runs/A1/45261575/0      # 导出 → 对齐 → 分档打分

# 第二阶段：清单、生成、放置
bash scripts/extract_hd.sh 45261575               # 高清帧（Pi3X 那 32 帧的原图 + 放大的内参 + Pi3X 深度）
bash scripts/run_boxer.sh 45261575                # Boxer 清单 → perception/<id>/inventory.json
bash scripts/run_clean_inventory.sh 45261575      # 干净对照清单（SAM 3 + Pi3X 深度）→ inventory_clean.json
bash scripts/build_inventory_v2.sh 45261575       # 清单 v2（开放词表 + 放大窗口 + MoGe-2 深度），只生成不打分 → inventory_v2.json
bash scripts/run_p0.sh 45261575 P0                # 无 agent 流水线（P0c 用干净对照清单）
DRIVER=claude bash scripts/run_agent.sh A3v 45261575 0   # 带清单和生成工具的 agent
bash scripts/queue_runs.sh "A1 42899617 0" ...    # 按额度排队；SCORE=0 只跑不打分
```

## 约定

- CA-1M 的位姿、深度、真值框只进评测，不进 agent 的输入。
- 阈值和划分已经定死（`configs/`），只在开发集上调提示词和生成验收门槛。
- 订阅额度：Claude 驱动的队列把每周额度用完才停（11-20 起，之前是 85%）；旧 Codex 对照单次运行每周额度涨超过 15 个百分点就停；fal 付费调用先问 Yifan。
- 提交信息里不写 Co-Authored-By 之类的署名。
