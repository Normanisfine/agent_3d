# smallobj-video2blender

CIS 6220 期末项目（3Heads1GPU：Yifan Hu、Mingjian Li、Yujing Li）：**视频转 3D 的 agent 在小物体上丢了多少、丢在哪一步。**
以 AHa-3D 为基线，在 CA-1M 的真实房间扫描上按物体大小分档评测，并比较几种小物体处理方式的成本和精度。

- 设计（定稿）：[docs/design.md](docs/design.md)
- 路线图和闸门：[docs/plans/2026-10-22-roadmap.md](docs/plans/2026-10-22-roadmap.md)
- 当前阶段计划：[docs/plans/2026-10-26-phase2-tools.md](docs/plans/2026-10-26-phase2-tools.md)（第一阶段：[2026-10-22-phase1-checkpoint.md](docs/plans/2026-10-22-phase1-checkpoint.md)）
- 课程算力（Betty、LiteLLM）怎么用：[docs/compute/betty-litellm.md](docs/compute/betty-litellm.md)

## 目录

| 目录 | 内容 | 进 git |
|---|---|---|
| `src/smallobj/` | 我们的代码：CA-1M 读取、对齐、评测、可见性、导出、运行日志、汇总出图；高清帧、两种物体清单、生成（`gen3d`）、放置（`place`）、P0、agent 工具（`cli`） | 是 |
| `tests/` | pytest（`.runtime/venv/bin/pytest -q`） | 是 |
| `scripts/` | 一条命令一件事：准备场景、算感知、跑 agent、打分；`scripts/betty/` 是 Betty 上用的 | 是 |
| `configs/` | 划分、阈值、运行上限、生成验收门、清单类别表、各实验组的提示词和请求 | 是 |
| `docs/` | 设计、计划、算力指南、调研笔记（`research/`）、英文提案（`proposal/`）、组内讲解页（`explainer/`） | 是 |
| `legacy/` | 旧项目 video2sim-align 的代码，只作参考和拷贝来源 | 是 |
| `third_party/` | AHa-3D（提交 82f4b11，含 Pi3X/SAM 3 环境和权重）、Blender 5.2.1、Boxer、Hunyuan3D-2 | 否 |
| `scenes/<id>/` | CA-1M 场景：原始包、逐帧图和位姿、真值框、`input.mp4`、检查图 | 否 |
| `perception/<id>/` | 感知结果（笔记本 10 万像素）、高清帧 `hd/`、清单 `inventory.json`（Boxer）和 `inventory_clean.json`（干净对照）、生成用掩码 `item_masks/`；Betty 的 25.5 万像素结果拉回到 `perception_betty/` | 否 |
| `gen/<id>/<item>/c<k>/` | 生成的网格候选、`placement.json` | 否 |
| `runs/<arm>/<scene>/<seed>/` | 每次 agent 运行：提示词、事件日志、`scene.blend`、`run_log.json`、打分 | 否 |
| `results/` | 汇总表和图（中期检查、报告） | 是 |
| `.runtime/` | 项目 Python（`py311`、`venv`）、Boxer 和 Hunyuan 的环境（`boxer/`、`hy3d/`）、tectonic、`bin/`（codex、blender） | 否 |

## 一个场景从头到尾

```bash
source scripts/env.sh
bash scripts/prepare_scene.sh 45261575            # 下载 CA-1M、真值框、10 fps 输入视频、投影检查图
bash scripts/run_reference.sh 45261575            # Pi3X + SAM 3 感知（笔记本显存不够时自动降到 10 万像素）
bash scripts/run_agent.sh A1 45261575 0           # Codex（gpt-6.1-sol，medium）无人值守跑 AHa-3D；每天最多 6 次
bash scripts/score_run.sh runs/A1/45261575/0      # 导出 → 对齐 → 分档打分

# 第二阶段：清单、生成、放置
bash scripts/extract_hd.sh 45261575               # 高清帧（Pi3X 那 32 帧的原图 + 放大的内参 + Pi3X 深度）
bash scripts/run_boxer.sh 45261575                # Boxer 清单 → perception/<id>/inventory.json
bash scripts/run_clean_inventory.sh 45261575      # 干净对照清单（SAM 3 + Pi3X 深度）→ inventory_clean.json
bash scripts/run_p0.sh 45261575 P0                # 无 agent 流水线（P0c 用干净对照清单）
bash scripts/run_agent.sh A3v 45261575 0          # 带清单和生成工具的 agent；DRIVER=claude 换 Claude 驱动
bash scripts/queue_runs.sh "A1 42899617 0" ...    # 按额度排队；SCORE=0 只跑不打分
```

## 约定

- CA-1M 的位姿、深度、真值框只进评测，不进 agent 的输入。
- 阈值和划分已经定死（`configs/`），只在开发集上调提示词和生成验收门槛。
- 订阅额度护栏：单次运行每周额度涨超过 15 个百分点就停；fal 付费调用先问 Yifan。
- 提交信息里不写 Co-Authored-By 之类的署名。
