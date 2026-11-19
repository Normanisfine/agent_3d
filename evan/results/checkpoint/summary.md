# 中期检查（10/26）一页总结

2026-10-24 · 3Heads1GPU · 数据：3 个开发场景各跑 1 次 A1 和 1 次 A0（A0 见 §6）。图表在本目录：`recall_by_bin.png`、`funnel.png`、`funnel_abs30.png`、`runs.md`、`sensitivity.md`。

## 1. 做了什么

- 整条流水线已经端到端跑通：CA-1M 下载 → 10 fps 输入视频 → Pi3X 感知 → AHa-3D agent（Codex CLI + gpt-6.1-sol medium）→ 从 .blend 导出物体框 → 和真值对齐 → 按尺寸分档评测 → 漏斗图。代码在 `src/smallobj/`，有 65 个测试。
- 每次运行都自动记录耗时、token 和订阅额度，并按"每天最多 6 次、单次每周额度涨超过 15 个百分点就停"的护栏无人值守排队。
- **注意：感知用的是笔记本的 10 万像素**（15 万像素显存不够），不是作者默认的 25.5 万像素。正式实验的分辨率在 G1 定（见 §5）。

## 2. 第一批数字（A1，3 个场景，292 个真值物体，判据 D，Sim(3) 对齐）

| 档（最长边） | 真值数 | 看得见 | 建出来（正式口径） | 建出来（30 cm 口径） | 建对了 | 判据 I 召回 | 不修尺度时建对了 |
|---|---|---|---|---|---|---|---|
| XS（<0.2 m） | 84 | 100% | 26% | **80%** | **6%** | 2% | 0% |
| S（0.2–0.5 m） | 82 | 94% | 49% | 59% | 22% | 5% | 6% |
| M（0.5–1.5 m） | 89 | 97% | 61% | 61% | 30% | 20% | 27% |
| L（≥1.5 m） | 37 | 100% | 41% | 41% | 24% | 19% | 24% |

## 3. 关键发现

1. **小物体大多建出来了，但没摆准。** XS 档有 80% 在 30 cm 以内建出来（把预测随机挪开 0.5–1.5 m 的碰巧基线，各场景只有 3–9%），可只有 6% 算"建对了"。所以小物体主要丢在"摆准"这一关，不是"没建"。按正式口径看，XS 只有 26% 建出来，这是因为正式口径的宽松门槛按物体大小缩放：10 cm 的杯子偏 15 cm 就算没建，把摆放误差错记成了"没建"。
2. **XS 的"建对了"门槛已经贴着测量误差。** 判据 D 对 XS 的距离容差中位数约 4 cm，而相机轨迹对齐本身的残差就有 2.4–4.2 cm。就算 agent 完美，XS 也会有不少被判"没摆准"。
3. **尺度误差对小物体是致命的。** Pi3X 的尺度在三个场景分别偏 2.7%、6.8%、11.5%。不修尺度时 XS 掉到 0，S 掉到 6%；M、L 几乎不受影响。
4. **看得见不是瓶颈。** 在 10 万像素的流程帧里，97% 的真值物体至少有 100 个像素可见。
5. **L、M 只看"建对了"。** 正式口径的宽松门槛对大物体太宽，随机基线就能拿到 24–52% 的"建出来"（L 档的基线甚至不低于实测），所以 L/M 的"建出来"没有信息量。

**评测协议在开发集上改过两处，测试集还一次没跑：**
- 匹配和宽松门槛加了尺寸条件（最长边比在 1/3–3 之间），否则小预测会抢大真值。
- 真值也去掉门、窗、踢脚线和贴墙的薄壳件，和预测侧去掉结构件对称；标明是地毯的保留（审查后补）。

改之前 L 档召回只有 0.07–0.18，明显不合理。改动写进了设计文档 §8、§9.4。

## 4. 一次运行花多少

| 运行 | 耗时 | 输入 token（缓存率） | 每周额度 | 5 小时窗口 | 建出的物体数 |
|---|---|---|---|---|---|
| A0 office48（试跑） | 22.5 min | 9.2 M（98%） | +4 | +27 | 9 |
| A0 三个开发场景 | 17.6–26.7 min | 7.5–15.0 M（98%） | +3 / +7 / +7 | +22 / +43 / +43 | 11–21 |
| A1 45261575 | 25.2 min | 9.2 M（99%） | +3 | +22 | 116 |
| A1 47331262 | 32.2 min | 12.1 M（99%） | +5 | +29 | 147 |
| A1 47115469 | 55.1 min | 20.1 M（99%） | +8 | +51 | 71 |

- **能跑多少次：**
  - 一个每周窗口（周五 13:57 重置）大约够 18 次 A1。
  - 一个 5 小时窗口够 2–4 次。
  - 设计里的 95 次 Codex 运行要 5 周以上，**按原规模做不完**。
- **上限已写进 `configs/run_caps.json`：** 墙钟 3862 秒、工具调用 184 次，都是 A1 中位数的 2 倍。到上限就停，状态记为 timeout 或 tool_cap。

## 5. G1 要当面定的事（我的建议在前）

> **10-27 已定：全部按下面的建议执行**（Yifan："评测标准按照你的来"）。A0 沿用 major_objects；训练加分项做 (a)，以 SAM 3D 在 Betty 跑通为前提。

1. **规模：设计第 5 节的 5 步削减全做。**
   - A0 缩到 5 个场景。
   - Claude 复跑只保留 A1 和 A3v。
   - 第二次重复缩到 3 个场景。
   - 取消 A4。
   - 测试场景减到 10 个（`splits.json` 测试列表的前 10 个）。

   这样 Codex 共约 51 次，高清帧消融（5 次）放到"额度有剩再做"。到 11/20 还有 4 个每周窗口，约 65–70 次的量，A2、A3 每次不比 A1 贵就够。要赶上进度，还得做到两点：
   - 10/27 起用本周剩下的额度先跑测试集的 A1（10 次）和 A0（5 次）；这两组不依赖第二阶段的新工具。
   - A2、A3 的开发调试改用 Claude 跑，Codex 额度只留给正式运行。
2. **感知分辨率（决定 10/27 能不能开跑）：**
   - 建议：正式实验就用笔记本 10 万像素，所有组共用同一份感知，比较是公平的，报告里注明。Betty 通了以后，可以加一个 5 个场景的 25.5 万像素对照。
   - 另外两个选项：等 Betty 的 25.5 万像素（Mingjian 还没开户，会拖进 11 月）；或者退出桌面会话，在笔记本上跑 15 万像素。
   - 两个剩余开发场景和 15 个测试场景，今天已经按 10 万像素准备好输入和感知，备用（每个约 50 秒；相机轨迹对齐残差都在 2–11 cm，没有对不上的）。
3. **正式口径（必须在测试集打分前定）：**
   - 建议 ①："建出来"在原宽松门槛之外再加"中心距离 ≤ 30 cm 且尺寸比在 1/3–3 之间"，旁边一并报告随机基线。
   - 建议 ②："建对了"仍用判据 D，但距离容差设 10 cm 下限，避免 XS 的结果被对齐误差淹没。
   - 两条都只改评分，不需要重跑。
   - 在 A1 的开发数据上：
     - 加 30 cm 后，XS"建出来"从 26% 升到 80%，S 从 49% 升到 59%。
     - 再加 10 cm 下限，XS"建对了"从 6% 升到 24%，S 仍是 21–22%。
     - M、L 都不变。
4. **Claude 的用法：** 先在 office48 上量一次 Claude 跑一遍要多少额度，再决定第 1 条里的分工。
5. **训练加分项做不做（设计 §10 定在今天决定）：**
   - 建议：先定做 (a) 路由小分类器，前提照设计：SAM 3D 要在 11/2 前在 Betty 上装通，装不通就取消。
   - 如果 Mingjian 想做真正的大规模训练，就改成 (b)：在 Betty 上用 CA-1M 训练集的小物体微调 Boxer。
6. **独立审查（10-23）提出、需要组里确认的四件事：**
   - **事后改协议要认可。** §3 那两处协议修正和地毯豁免，都是看过开发集 A1 输出之后定的，而设计文档原本要求不看 agent 输出调阈值。测试集一次没跑，但要在 G1 明确认可后定死。
   - **配对方式。** 匈牙利配对会优先让配上的对数最多，偶尔把一个"建对了"拆成两个"建坏了"。改成按代价从小到大贪心配对后，3 个开发场景共多 1 个 L、2 个 M"建对了"。建议改，因为它更符合直觉。
   - **A0 用哪个"保真度"。** AHa-3D 没有默认值，我们用的是 major_objects，作者博客用的是 approximate。另外，A1 现在允许用素材库模型，设计里写的是"只用代码和方块"。
   - **护栏的"当期"指哪个窗口。** 现在按每周额度计，单次涨超过 15 个百分点就停。如果按 5 小时窗口算，每次 A1 都会触发（22–51 个百分点）。

## 6. A0 对照（原版，同样 3 个场景，判据 D，Sim(3)）

| 档 | A0 建出来 | A0 建对了 | A1 建出来 | A1 建对了 |
|---|---|---|---|---|
| XS（84） | 0% | 0% | 26% | 6% |
| S（82） | 2% | 0% | 49% | 22% |
| M（89） | 31% | 25% | 61% | 30% |
| L（37） | 24% | 24% | 41% | 24% |

- **A0 基本不建小物体。** 每个场景只建 11–21 个物体，A1 是 71–147 个。XS、S 两档 A0 一个都没建对，这正是作者"小物件可以省略"的设定。
- **A1 多出来的主要在 S 档。** 对 L 档没有帮助，"建对了"都是 24%。M 档多建了一倍，但"建对了"只从 25% 升到 30%，多建的大多没摆准。
- **A0 并不比 A1 便宜。** 每周额度平均 +5.7，A1 是 +5.3；耗时也差不多。花费主要在 AHa-3D 自己的"渲染—审查—修补"循环，和建多少物体关系不大。
- **6 次开发运行全都没通过 AHa-3D 自己的验收。** A0 和 A1 都是在用完提示词允许的 3 轮修补后自行停下，独立审图仍然不通过。我们照样拿最后保存的 .blend 打分，按设计这不算跑崩。之后会把 AHa-3D 自己的验收结果也记进运行记录，单独报告。G1 可以顺带讨论：3 轮修补的预算要不要放宽（放宽会更贵）。
- **我们的场景 ID 被 AHa-3D 拒收过。** 7 次运行里，agent 每次都要先绕开这个问题（ID 带大写 A0/A1，AHa-3D 只收小写），多花了工具调用，网页图库也因此生成失败。10-24 已改成小写；开发集的数据保留原样，测试集从一开始就用小写。

## 7. 下一阶段（P2，10/27–11/02）

- 物体清单两种：Boxer 自动检测的，以及作对照的干净清单。
- 生成和放置工具 `gen3d_request` + `place_mesh`：先用本地 Hunyuan3D-2mini 写通，SAM 3D 批下来后再接上。
- P0 无 agent 流水线在开发集上跑通。
- 验收门在 10 个开发物体上校准。
- 要本人办的：
  - Mingjian 开通 Betty。
  - 问课程 LiteLLM 的地址和 key（可以帮忙起草 Ed 帖子）。
  - 把 Yujing 的 GitHub 用户名发过来，好邀请进仓库。

---

## For the TA (three paragraphs)

**What we built.** We wrapped AHa-3D (monocular room video → editable Blender scene) in a measurement harness. It turns Apple CA-1M scans into input videos plus oriented-box ground truth. It then runs the AHa-3D agent unattended (Codex CLI, gpt-6.1-sol, medium effort), exports the predicted objects from the resulting `.blend`, aligns the pipeline's camera trajectory to ground truth with a gravity-constrained Sim(3), and scores every ground-truth object by size bin: XS < 0.2 m, S 0.2–0.5 m, M 0.5–1.5 m, L ≥ 1.5 m. Each object goes through a funnel: visible → built (within a loose gate) → built correctly (within a strict gate). As of 10/23 the pipeline runs end to end on three development scenes (292 ground-truth objects) and has 65 unit tests. One caveat: perception currently runs on a 12 GB laptop GPU at 100k pixels per frame, below the authors' default of 255k.

**First result.** With the strict criterion, the "careful" baseline (A1: the agent is told to model every visible small object with code and primitives) gets 6% of XS objects right, 22% of S, 30% of M and 24% of L. The funnel shows where XS objects are lost. Almost all of them are visible (97% of all objects pass the visibility test), and 80% have a size-consistent prediction within 30 cm, against a 3–9% chance baseline. So small objects are mostly built but misplaced by a few centimetres to 30 cm, and few are simply skipped. Two more effects:
- Metric scale error from the reconstruction (2.7–11.5% on our scenes) wipes out XS and S accuracy when we do not correct it, while M and L barely change.
- The strict XS tolerance (about 4 cm) is about the same as the camera-alignment residual (2–4 cm).

We made two protocol fixes on the development split: size-aware matching, and removing doors, windows and wall trim from the ground truth to mirror how we drop structural parts from predictions. No test scene has been scored yet.

**Cost and plan.** One agent run takes 25–55 minutes and 9–20 M input tokens (about 99% cached). It uses 3–8% of the weekly subscription quota and 22–51% of a 5-hour window. The 95 planned Codex runs therefore do not fit into the remaining four weeks. At our 10/26 checkpoint we will apply our pre-registered reduction order: A0 on 5 scenes, a second seed on 3 scenes, no GATOR-style refinement arm, and 10 test scenes. That leaves about 51 runs. We will also start the A0/A1 test runs early and use a second subscription (Claude) for development runs. The next phase adds an object inventory (Boxer) and a 3D generator (SAM 3D Objects or Hunyuan3D) with automatic placement, to test whether generation fixes the build stage and where placement still fails.
