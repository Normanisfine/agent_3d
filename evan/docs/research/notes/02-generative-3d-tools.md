<!-- 02 生成式 3D 工具调研（2026-10-14，研究子 agent；只读网页、README、模型卡、论文和代码，没有下载权重，也没有运行任何模型） -->

# 生成式 image-to-3D 工具：现状、摆放、小物体与接入方案

日期：2026-10-14。标注规则：
- **已核实**：读过原始来源（README、HF 模型卡或 API、论文 HTML、官方价格页、源码）。
- **推算**：附了理由。
- **未核实**：没找到一手来源，或者只有第三方说法。

每条事实后面都附 URL。

---

## 0. 结论先行

1. **Hunyuan3D 最新版本。**
   - 最新的是 **Hunyuan3D 3.1**（2026-01 上线全球平台），但**只有 API**。2.5、3.0 也只有 API。
   - 最后一批开源权重是 2025-09 的 Hunyuan3D-Omni 和 Part；2026 年的 Buffalo 1.0 只有论文。
   - 开源许可**排除欧盟、英国、韩国**。
2. **当前最值得用的开源生成器：**
   - **SAM 3D Objects**（CVPR 2026）：带相机系位姿，可以吃外部点图，专门为遮挡和小物体训练，需人工审批。
   - **TRELLIS.2**（MIT，≥24 GB）。
   - 2026 年新出的 **Pixal3D**（MIT，SIGGRAPH 2026，输出和输入视图像素对齐）。
   - 12 GB 笔记本上能稳定跑的，只有 **Hunyuan3D-2.0 / 2mini 纯形状**（6 GB）、TripoSG（8 GB）、Hunyuan3D-2.1 / Omni 形状（10 GB，勉强）。
   - 其他的放到 **Betty 的 B200 MIG 45 GB 切片**（补贴价 $0.25/小时，非补贴价 $1.13/小时）、Colab A100，或者 fal 托管（SAM 3D $0.02，TRELLIS.2 $0.25–0.35）。
3. **摆放是关键。** 现成、不训练的方案里，SAM 3D 联合预测位姿最准：
   - R2S-Object（Pi3X 深度）上 ADD-SB 0.050 m、3D IoU 0.482。
   - Any6D 是 0.086 m、0.388。
   - 用生成网格配 FoundationPose 明显更差（SAM 3D 表 3）。
   - 可微渲染比对比 ICP 再降约 31% 的场景 CD（Scene-SAM3D：7.18 → 4.76 cm）。
   - 最准的 GizmoAct（0.017 m）没有代码。
4. **规范空间生成器（Hunyuan、TRELLIS）有现成的配准配方**，见 φ-RIE、ReScene：稳健 OBB 定尺度，偏航按 10° 多起点，部分对完整做 ICP，换朝上轴重试，加接受门槛。
5. **小物体：**
   - 生成器内部都把裁剪缩放到 518–1024 px。60 px 的物体会被放大 7–17 倍，信息量不变。
   - **没有论文直接测过「分辨率 vs 质量」**。
   - 有证据的做法：先做 2D 补全（DeOcc V-IoU 0.16→0.32）；按覆盖度挑视角，而不是随机挑（Scene-SAM3D CD 61.96→41.60）；多候选打分加重试（φ-RIE F1 0.301→0.383，但构建时间翻倍）。
6. **几何指标：**
   - **没有任何论文在真实数据上证明「生成网格比基本体或包围盒有更好的 Chamfer、F-score」。**
   - 场景级指标主要由摆放决定。
   - VIGA 在 Blender agent 里加 SAM-3D 后，图像指标反而下降。
   - 小物体占房间表面积极小，几乎不影响整屋 CD。**要报物体级、按尺寸分组的指标。**
7. **复核旧结论：** 「Hunyuan3D 只适合当可选的外观升级」大体仍然成立，但要改成：
   - 默认后端用带位姿的 SAM 3D（先用 fal），第二候选用 TRELLIS 加自己配准。
   - Hunyuan3D-2 纯形状作本地开发后端。
   - Hunyuan3D-Omni 的包围盒条件值得做一个小实验。
   - 每个生成网格都必须在剪影和配准上**比基本体好**才接受，否则退回基本体。
8. **接入方式：** 拆成异步的 `gen3d_request` 和 `place_mesh` 两个工具。每个候选约 30–90 s（推算），失败自动退回基本体（§7）。

---

## 1. 生成器现状（截至 2026-10-14）

### 1.1 Hunyuan3D 家族：哪些开源，哪些只有 API

| 版本 | 时间 | 权重 | 说明 | 来源 |
|---|---|---|---|---|
| Hunyuan3D-2.0（DiT-v2-0 1.1B + Paint 1.3B），含 Fast、Turbo | 2025-01 到 04 | **开源** | 形状 6 GB，形状加纹理 16 GB；有 `--low_vram_mode` | [README](https://github.com/Tencent-Hunyuan/Hunyuan3D-2) |
| Hunyuan3D-2mini（0.6B），含 Turbo、Fast | 2025-03 | **开源** | 最小的形状模型 | 同上 |
| Hunyuan3D-2mv（1.1B） | 2025-03 | **开源** | 多视图形状模型（固定前、左、后等视角） | 同上 |
| Hunyuan3D-2.1（Shape 3.3B + PBR Paint 2B） | 2025-06-13 | **开源**，含训练代码 | 形状 10 GB，纹理 21 GB，合计 29 GB | [README](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) |
| Hunyuan3D-Omni（3.3B） | 2025-09-25 | **开源** | 在 2.1 上加控制编码器：点云、体素、骨架、3D 包围盒；README 写 "It takes 10 GB VRAM for generation" | [README](https://github.com/Tencent-Hunyuan/Hunyuan3D-Omni)，[arXiv 2509.21245](https://arxiv.org/html/2509.21245) |
| Hunyuan3D-Part | 2025-09 | 开源 | 部件分割和部件生成 | [HF](https://huggingface.co/tencent/Hunyuan3D-Part) |
| HY3D-Bench 基线（Hunyuan3D-Shape-v2-1 Small，0.8B） | 2026-02 | 开源 | 数据集论文附带的小基线，不是新的主力版本 | [GitHub](https://github.com/Tencent-Hunyuan/HY3D-Bench)，[HF](https://huggingface.co/tencent/HY3D-Bench) |
| Hunyuan3D 2.5 | 2025-06（技术报告） | **只有 API** | — | [arXiv 2506.16504](https://arxiv.org/abs/2506.16504) |
| Hunyuan3D 3.0 | 2025-09-16 发布（二手报道） | **只有 API 和网页** | 腾讯云国际版 API 默认版本 | [Notebookcheck](https://www.notebookcheck.net/Tencent-s-new-Hunyuan-3D-3-0-brings-realistic-AI-model-generation-to-developers-and-creators.1116964.0.html)，[腾讯云 API](https://www.tencentcloud.com/document/api/1284/75540) |
| **Hunyuan3D 3.1**（最新） | 2026-01 上线全球平台 | **只有 API 和网页** | 官方推文写 "supports up to 8 input views"；腾讯云 API `Model` 可选 "3.0, 3.1" | [官方 X](https://x.com/TencentHunyuan/status/2016449283428659599)，[腾讯云 API](https://www.tencentcloud.com/document/api/1284/75540) |
| Hunyuan3D-Buffalo 1.0 | 2026-08 | **只有论文** | 统一的 3D 生成、理解、编辑多模态模型；仓库只有 README，HF 上搜不到权重 | [GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-Buffalo1.0)，[arXiv 2608.02711](https://arxiv.org/abs/2608.02711) |
| WorldClaw | 2026-08 | **只有论文** | 「Agentic 3D Open-world Generation」，做的是开放世界生成，不是重建 | [GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-WorldClaw)，[arXiv 2608.05248](https://arxiv.org/abs/2608.05248) |

**核查方法（已核实）：**
- 用 HF API 列出 `author=tencent` 下按创建时间排序的全部 161 个模型。3D 生成类的最后一批开源权重是 2025-09-23 的 Hunyuan3D-Omni 和 Hunyuan3D-Part。之后只有 HY3D-Bench 的 0.8B 基线（2026-01-13 创建），以及 HY-World 2.0 这类世界模型。
- GitHub 组织 Tencent-Hunyuan 下，2026 年新建的 3D 仓库有 Buffalo 1.0、WorldClaw、R-DMesh、HY-World-2.0、HY3D-Bench。前两个没有权重。
- 来源：https://huggingface.co/api/models?author=tencent&sort=createdAt 、https://api.github.com/orgs/Tencent-Hunyuan/repos

**许可（已核实，2.0、2.1、Omni 的 LICENSE 原文一致）：**
- 原文："THIS LICENSE AGREEMENT DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA"，Territory 定义为 "worldwide territory, excluding the territory of the European Union, United Kingdom and South Korea"。
- 不得在 Territory 以外使用模型、输出或结果（LICENSE 原文中 "You must not use, reproduce, modify, distribute, or display ... outside the Territory" 一款）。
- 发布当月月活超过 100 万的产品要另外申请。
- 在美国（Penn）做课程项目没有问题。如果组员或之后的使用者在欧盟、英国、韩国，Hunyuan 权重和它生成的网格都不能用。
- 来源：https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE 、https://github.com/Tencent-Hunyuan/Hunyuan3D-Omni/blob/main/License.txt
- HF 模型卡 `license: other`、`tencent-hunyuan-community`，不需要申请（HF API `gated: False`）。

**对本项目特别有用的一点：Hunyuan3D-Omni 的条件控制（已核实代码，效果未核实）。**
- **包围盒条件：** `demos/bbox/data.json` 里每个物体给 3 个数，是归一化的长宽高比（例如 `[0.8, 0.64, 1]`）。论文写的是 "length, width, and height ratios into the coordinates of the eight vertices in canonical space"。
  - 意思是：先用 Pi3X 点云量出物体尺寸比，再让生成的形状按这个比例出来。这样各向异性尺度的问题，大部分在生成时就解决了。
- **点云条件：** `inference.py` 的 `infer_point` 先用 `normalize_mesh(mesh, scale=0.98)` 把输入点云中心化、缩放进 [-0.98, 0.98] 立方体，再作为条件。
  - 论文说支持 LiDAR 或 RGB-D 的**不完整**点云，训练时用了 "random drop sampling" 和噪声扰动。
  - 论文还说点云条件让生成结果 "well-aligned in scale with the ground truth"。
  - 但论文**没有定量结果**，也没有明说输出坐标系和输入点云的坐标系一致。
- **推算：** 如果输出确实在输入点云的归一化坐标系里，只要把归一化逆变换回去，就能直接摆进场景，不需要单独做配准。这条要在第 1 周用 1 到 2 个物体实测。
- 来源：https://github.com/Tencent-Hunyuan/Hunyuan3D-Omni/blob/main/inference.py 、https://arxiv.org/html/2509.21245

### 1.2 主要候选的对比表

「12 GB」指你们的 RTX 5070 Ti Laptop（sm_120）。「遮挡」指输入被遮挡时能不能补全不可见部分（amodal）。

| 模型 | 权重与许可 | 推理显存 | 每个物体的耗时 | 12 GB 能否跑 | 输入 | 遮挡 | 输出坐标系 | 托管 API 单价 |
|---|---|---|---|---|---|---|---|---|
| **Hunyuan3D-2.0 / 2mini**（Tencent） | 开源；腾讯社区许可（排除欧盟、英国、韩国） | 形状 6 GB，加纹理 16 GB（[README](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)） | README 没给秒数；FlashVDM 摘要说生成提速 "32x"（[arXiv 2503.16302](https://arxiv.org/abs/2503.16302)）；Replicate 上 2.0 带纹理约 96 s（[Replicate](https://replicate.com/tencent/hunyuan3d-2)） | **形状能跑**（官方 6 GB）。纹理 16 GB 跑不下，`--low_vram_mode` 能否压进 12 GB **未核实** | 单图；2mv 是多视图，但视角固定 | 没有专门训练（推断：训练数据是 Objaverse 类的干净渲染） | **规范空间**，归一化到单位框，朝向和尺度未知 | fal 2.0：形状 $0.16，带纹理 $0.48；2mini turbo $0.08（[fal](https://fal.ai/models/fal-ai/hunyuan3d/v2/mini/turbo/llms.txt)） |
| **Hunyuan3D-2.1** | 同上 | 形状 10 GB，纹理 21 GB，合计 29 GB（[README](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)） | 未核实；Replicate 社区版约 5 分钟（含冷启动） | **形状勉强**（10 GB，余量很小），纹理不行 | 单图 | 没有专门训练 | 规范空间 | fal 2.1 标价 $0.30，已标记弃用 |
| **Hunyuan3D-Omni** | 同上 | 10 GB（README） | 未核实 | 勉强（同 2.1 形状） | 单图，加点云、体素、包围盒、骨架之一 | 点云可以不完整（论文） | 规范空间；点云模式可能和输入对齐（见 1.1） | 没有托管 |
| **Hunyuan3D 3.0 / 3.1** | **闭源**，只有 API | — | API 没写延迟 | 走 API | 单图；Pro 版加多视图（3.1 支持更多视角） | 未核实 | 规范空间 | 腾讯云国际版：纯几何 15 点、默认带纹理 25 点；预付 $0.015/点，后付 $0.02/点，即每次约 $0.23–0.50（[计费页](https://www.tencentcloud.com/document/product/1284/75281)） |
| **TRELLIS**（Microsoft，1.2B） | MIT；不需要申请 | ≥16 GB（[README](https://github.com/microsoft/TRELLIS)） | README 没给；Replicate 约 27 s | 不行（官方 16 GB） | 单图；有免训练的多图模式（README 原话 "may not give the best results"） | 否 | 规范空间 | fal $0.02（[fal](https://fal.ai/models/fal-ai/trellis/llms.txt)） |
| **TRELLIS.2-4B**（Microsoft） | MIT；nvdiffrast、nvdiffrec 是 NVIDIA 非商用许可 | **≥24 GB**；"verified on A100 and H100"（[README](https://github.com/microsoft/TRELLIS.2)） | H100 上：512³ 约 3 s（形状 2 s + 材质 1 s），1024³ 约 17 s，1536³ 约 60 s（README） | **不行**。sm_120 编译很难：issue #19 里有人在 5090 上用 cu128 或 cu130 自己编通，#143 有 5070 Ti 用户卡在 CuMesh 编译（glibc 头文件冲突），靠换 conda 的 kernel-headers 才推进 | 单图 | 否 | 规范空间 | fal：512³ $0.25，1024³ $0.30，1536³ $0.35（[fal](https://fal.ai/models/fal-ai/trellis-2/llms.txt)） |
| **SAM 3D Objects**（Meta，CVPR 2026） | SAM License，允许商用，但有贸易管制和军事用途限制；HF **人工审批**（`gated: manual`） | 官方 "at least 32 Gb of VRAM"（[setup.md](https://github.com/facebookresearch/sam-3d-objects/blob/main/doc/setup.md)）；社区跳过网格解码后能在 24 GB 跑（[issue #6](https://github.com/facebookresearch/sam-3d-objects/issues/6)） | A100-80GB 上 **13.0 ± 1.4 s**，进程显存 22.0 GB（RecGen 论文表 S3，[arXiv 2604.27106](https://arxiv.org/html/2604.27106)）；论文说蒸馏后几何阶段目标是 "sub-second" | **不行** | 整张图加掩码（内部再裁一份物体图）；可选外部点图 `pointmap=` | **专门训练**：合成遮挡数据（可见比例 0.1–0.9），README 原话 "handling small objects and occlusions" | **相机系下的 R、t、s**；传入米制点图，输出才是米制；发布代码里 `refine_scale` 把尺度取 3 轴均值，即**各向同性** | fal $0.02，返回四元数、平移、尺度（[fal](https://fal.ai/models/fal-ai/sam-3/3d-objects/llms.txt)） |
| **Pixal3D**（清华 + 腾讯 ARC，SIGGRAPH 2026）**新** | MIT（代码和 HF 权重都是，不需要申请） | 官方没写；有 `--low_vram`（默认 1024 分辨率）；社区补丁说 1024 峰值约 11 GB（[issue #7](https://github.com/TencentARC/Pixal3D/issues/7)，**未核实**） | 没写 | **也许**（只有社区补丁的说法）；依赖和 TRELLIS.2 相同，sm_120 一样难编 | 单图；2026-09 起支持多视图，要给相机位姿 `transforms.json` | 论文的场景管线先用 Qwen-image-edit 补全遮挡，模型本身没有 amodal 训练 | **像素对齐、相机系**：论文说 "orientation ... already aligned with the input image"；尺度和深度要用点图做最小二乘（[arXiv 2605.10922](https://arxiv.org/html/2605.10922)） | fal：1024 $0.30，1536 $0.42（[fal](https://fal.ai/models/fal-ai/pixal3d/llms.txt)） |
| **RecGen**（TRI 等，2026-04） | CC BY-NC 4.0（[HF `TRI-ML/RecGen`](https://huggingface.co/TRI-ML/RecGen)），只能非商用 | A100 上进程 14.1 GB（[arXiv 2604.27106](https://arxiv.org/html/2604.27106) 表 S3） | A100 上 7.3 s（同表） | 不行（推算：14 GB > 12 GB） | RGB 加米制深度加掩码加内参，1 到 2 个视角 | **专门训练**，比 SAM 3D 的优势随遮挡加重而变大 | 相机系下的 Sim(3)，各向同性尺度 | 没有托管 |
| **TripoSG**（VAST，1.5B） | MIT | "at least 8GB VRAM"（[README](https://github.com/VAST-AI-Research/TripoSG)） | 未核实 | **能**（官方 8 GB） | 单图 | 否 | 规范空间 | fal 没有（只有 TripoSR）；商业版 Tripo 见 §2 |
| **Step1X-3D**（StepFun） | Apache-2.0 | 几何加纹理 27 GB，50 步 152 s（[README](https://github.com/stepfun-ai/Step1X-3D)） | 152 s（含纹理） | 纯几何未核实；整套不行 | 单图 | 否 | 规范空间 | — |
| **Hi3DGen / Stable3DGen** | MIT（去掉了 NVIDIA 依赖，可商用） | 未核实 | 未核实 | 未核实 | 单图（法线桥接） | 否 | 规范空间 | — |
| **Direct3D-S2** | MIT | 512 分辨率 ≥10 GB，1024 约 24 GB（[README](https://github.com/DreamTechAI/Direct3D-S2)） | 未核实 | 512 能跑，但 README 说 512 质量 "noticeably" 差 | 单图 | 否 | 规范空间 | — |
| **Amodal3R**（ICCV 2025） | HF 权重 CC BY 4.0；仓库没标许可（NOASSERTION）（[HF](https://huggingface.co/Sm0kyWu/Amodal3R)） | 未核实（基于 TRELLIS，推算约 16 GB） | 未核实 | 不行（推算） | 单图或多图，不需要位姿；要给三级掩码（可见、被遮挡、背景）（[README](https://github.com/Sm0kyWu/Amodal3R)） | **专门训练**：在 ABO、3D-FUTURE、HSSD 上合成遮挡 | 规范空间 | 没有托管 |

**形状质量的旁证：**

1. SAM 3D 论文表 2，在真实场景物体 SA-3DAO 上（来源 https://arxiv.org/html/2511.16624 ）：

   | 模型 | F1@0.01 | vIoU | Chamfer |
   |---|---|---|---|
   | TRELLIS | 0.1475 | 0.1392 | 0.0902 |
   | HY3D-2.1 | 0.1399 | 0.1266 | 0.1126 |
   | HY3D-2.0 | 0.1574 | 0.1504 | 0.0866 |
   | Direct3D-S2 | 0.1513 | 0.1465 | 0.0962 |
   | TripoSG | 0.1533 | 0.1445 | 0.0844 |
   | Hi3DGen | 0.1629 | 0.1531 | 0.0937 |
   | **SAM 3D** | **0.2344** | **0.2311** | **0.0400** |

   - 在真实、杂乱、带遮挡的输入上，SAM 3D 明显领先。
   - Hunyuan3D-2.1 在这张表里反而比 2.0 差。
   - 表里没有 TRELLIS.2。

2. Pixal3D 论文表 1，Toys4K 合成数据，渲染法线 IoU（来源 https://arxiv.org/html/2605.10922 ）：TRELLIS 79.48，TripoSG 73.54，Hunyuan3D-2.1 83.33，Direct3D-S2 74.23，Pixal3D 93.57。
   - 这里的 IoU 是渲染法线图的重叠，不是 3D 体素 IoU。
   - 这张表同样没有 TRELLIS.2 和 SAM 3D。

### 1.3 Blackwell（sm_120 笔记本，以及 Betty 的 B200 sm_100）上的安装

- **Hunyuan3D-2 纯形状：** 不需要编译 CUDA 扩展。README 里 `custom_rasterizer`、`differentiable_renderer` 只在 "# for texture" 一节，requirements 也是纯 Python 包。所以它是笔记本上**最容易装通**的。（已核实 README 和 requirements.txt；能否在 sm_120 上实际跑通属于推算。）
- **TRELLIS.2 和 Pixal3D：**
  - 要编 flash-attn、cumesh、o-voxel、nvdiffrast、FlexGEMM。
  - issue #19：CUDA 12.4 不支持 sm_120，有人改用 PyTorch 2.9.1+cu128 或 cu130 从源码编通。
  - issue #143：有人在 5070 Ti 上卡在 CuMesh 编译，原因是 glibc 头文件冲突。
  - 有现成 Dockerfile（issue #19 末尾），也有 ComfyUI 原生集成，ComfyUI 博客说 "No custom nodes, compiled CUDA extensions, or PyTorch downgrade"（[Comfy 博客 2026-08-31](https://blog.comfy.org/p/trellis2-and-pixal3d-are-now-native)）。
  - 来源：https://github.com/microsoft/TRELLIS.2/issues/19 、https://github.com/microsoft/TRELLIS.2/issues/143
- **SAM 3D Objects：** setup.md 钉在 cu121 和 kaolin torch-2.5.1_cu121。issue #116 有人要 cu128 的 Docker（仍是 open）。在 Blackwell 上要自己重编 kaolin 和 pytorch3d（推算）。
- **建议：**
  - 笔记本只跑 Hunyuan3D-2mini 或 2.0 的纯形状，以及配准代码。
  - TRELLIS.2、SAM 3D、Pixal3D 放 Colab A100，或者 Betty 的 MIG 切片。
  - 也可以直接用 fal 托管，免装。

### 1.4 算力：Betty 比 Colab 更合适

- Betty 每个节点 8 张 B200，每张 180 GB HBM3e（[PARCC Betty](https://parcc.upenn.edu/systems/betty/)）。
- FY27 价格（2026-07-01 起，[PARCC Rates](https://parcc.upenn.edu/about/rates/)）：

  | 资源 | 非补贴价（每小时） | 补贴价（每小时） |
  |---|---|---|
  | `betty.b200.mig45`（45 GB 切片） | $1.13 | $0.25 |
  | `betty.b200.mig90`（90 GB 切片） | $2.25 | $0.50 |
  | 整卡 B200 | $4.51 | $1.00 |

- 45 GB 切片装得下 SAM 3D（22 GB）、TRELLIS.2（≥24 GB）和 Hunyuan3D-2.1 全流程（29 GB）。
- 每人 $50 额度能买多少小时：
  - mig45 按非补贴价约 44 小时，按补贴价约 200 小时。
  - 学生额度适用哪一档价格，**未核实**。
- B200 是 sm_100，CUDA 扩展编译时要加 `TORCH_CUDA_ARCH_LIST=10.0`（推算）。

---

## 2. 托管 API：价格与能力

以下价格都在 2026-10-14 查过官方页面。fal 的价格我自己又抽查了 SAM 3D、TRELLIS.2、Hunyuan 3.1 Pro 三项，腾讯云国际版的计费页也抽查了。

| 服务 / 模型 | 纯几何 | 几何加纹理 | 免费额度 | 能否返回位姿 | 来源 |
|---|---|---|---|---|---|
| 腾讯云国际版 HY 3D Pro（3.0 或 3.1） | 15 点：预付 $0.225，后付 $0.30 | 25 点：$0.375 / $0.50；PBR、多视图、自定义面数各加 10 点 | 200 点，一次性，有效期 1 年；失败任务不计费 | 否 | [计费页](https://www.tencentcloud.com/document/product/1284/75281)，[API](https://www.tencentcloud.com/document/api/1284/75540) |
| 腾讯云中国站（混元生 3D） | 15 点：约 ¥1.5–1.8 | 20 点：约 ¥2.0–2.4 | 100 点 | 否；开通要实名认证，非中国身份能否通过**未核实** | [计费](https://cloud.tencent.com/document/product/1804/123461)，[快速入门](https://cloud.tencent.com/document/product/1804/120757) |
| Tripo API（v3.1-20260211，默认版本） | 20 点 = $0.20 | 30 点 = $0.30 | 未核实 | 否；但有 `auto_size`（"scale the generated model to real-world dimensions"）和 `orientation: align_image`（只在带纹理时生效） | [价格](https://developers.tripo3d.ai/en/pricing)，[参数](https://developers.tripo3d.ai/en/docs/generation-image-to-model/standard) |
| Meshy API（meshy-7.1 / 6） | 20 点，约 $0.40 | 30 点，约 $0.60；6-lite 只要 5 / 15 点 | API 要 Pro 档（$20/月 1000 点） | 否 | [API 价格](https://docs.meshy.ai/en/api/pricing) |
| fal SAM 3D Objects | — | $0.02 | 无 | **是**：`metadata` 含 rotation（四元数）、translation、scale、camera_pose；坐标系没写明 | [fal](https://fal.ai/models/fal-ai/sam-3/3d-objects/llms.txt) |
| fal TRELLIS.2 | — | $0.25 / $0.30 / $0.35 | 无 | 否 | [fal](https://fal.ai/models/fal-ai/trellis-2/llms.txt) |
| fal Pixal3D | — | $0.30（1024）/ $0.42（1536） | 无 | 输出像素对齐；有 `mesh_scale` 参数，影响相机距离估计 | [fal](https://fal.ai/models/fal-ai/pixal3d/llms.txt) |
| fal ReconViaGen 0.5（多视图） | — | $0.25–0.35 | 无 | 否 | [fal](https://fal.ai/models/fal-ai/reconviagen-0.5/llms.txt) |
| fal Hunyuan 3D v3.1 Pro | $0.225 | $0.375；PBR、多视图、自定义面数各加 $0.15 | 无 | 否 | [fal](https://fal.ai/models/fal-ai/hunyuan-3d/v3.1/pro/image-to-3d/llms.txt) |
| fal TRELLIS v1 | — | $0.02 | 无 | 否 | [fal](https://fal.ai/models/fal-ai/trellis/llms.txt) |

**成本推算：**
- 每个场景约 10–20 个小物体。每个物体生成 3 个候选（GRASE 的做法）。
- 一共 5 个场景，就是 150–300 次调用。
- 只用 fal SAM 3D：约 $3–6。
- 用 TRELLIS.2、Tripo 或腾讯 Pro（每次 $0.20–0.50）：约 $30–150。
- 多数情况下 API 费用比自己装环境的人力便宜得多。

---

## 3. 把生成网格摆进场景（关键问题）

生成器的输出分三类（外加一种条件生成），摆放难度差别很大：

| 类别 | 代表 | 已经给出的 | 还要自己解的 |
|---|---|---|---|
| A. 规范空间 | Hunyuan3D 2.x / 3.x、TRELLIS / TRELLIS.2、TripoSG、Step1X-3D、Tripo / Meshy API | 只有形状。一般是直立的（推断：训练数据大多正放），但朝前的方向、尺度、位置都未知 | 7 DoF（重力已知时：平移 3、偏航 1、尺度 1–3），外加「哪条轴朝上」的离散歧义 |
| B. 相机系联合预测 | **SAM 3D Objects**、RecGen | R、t、各向同性的 s，都在相机系下；给米制点图，结果就是米制 | 把相机系换到世界系（Pi3X 位姿直接给）；做多帧一致性精修 |
| C. 像素对齐 | **Pixal3D** | 朝向和输入视图对齐；物体放在相机视锥里的单位立方体内 | 深度和尺度两个数（论文用 MoGe 点图做最小二乘） |
| （C'）条件生成 | **Hunyuan3D-Omni**（点云或包围盒条件） | 包围盒模式：长宽高比由你给；点云模式：可能和输入点云对齐（未核实） | 包围盒模式还要解平移和偏航；点云模式可能只需把归一化逆变换回去 |

### 3.1 方法与真实场景上报告的精度

**1. SAM 3D Objects 自带的布局**（https://arxiv.org/html/2511.16624 表 3、表 9；代码 https://github.com/facebookresearch/sam-3d-objects ）

- **表 3：生成网格 + 位姿估计器 vs SAM 3D 联合预测。**
  - SA-3DAO 只给 RGB，点图是估计的；ADT 用数据集提供的点图。
  - 每格是 3D IoU / ADD-S@0.1。

| 方法 | SA-3DAO | ADT |
|---|---|---|
| Trellis + MegaPose | 0.2449 / 0.2831 | 0.2531 / 0.1971 |
| HY3D-2.0 + FoundationPose | 0.2937 / 0.5396 | 0.3864 / 0.5992 |
| HY3D-2.1 + FoundationPose | 0.2395 / 0.4177 | 0.2795 / 0.4129 |
| SAM 3D 网格 + FoundationPose | 0.2837 / 0.5079 | 0.3661 / 0.6495 |
| MIDI（联合） | – | 0.0336 / 0.0175 |
| **SAM 3D（联合）** | **0.4254 / 0.7232** | **0.4970 / 0.7673** |

- **表 9：** 在 ADT 上做测试时的布局优化后：
  - 3D IoU 0.4837→0.5258，ADD-S@0.1 0.7545→0.7617，2D IoU 0.5143→0.6487。
  - 1027 个实例里只有 554 个接受了优化结果。
- **代码（已核实）：**
  - `inference_pipeline_pointmap.py` 的 `run()` 有 `pointmap=` 参数，可以直接传入 Pi3X 的点图，还有 `with_layout_postprocess`（默认 False）、`stage1_only`、`use_stage1_distillation` 等参数。
  - `refine_scale()` 把 3 个轴的尺度取均值，所以发布版是**各向同性**尺度。
  - 来源：https://github.com/facebookresearch/sam-3d-objects/blob/main/sam3d_objects/pipeline/inference_pipeline_pointmap.py
- **`layout_post_optimization`（子 agent 读的代码）：**
  - 三步：先对齐点图，再做形状 ICP（阈值 0.05），最后渲染掩码做比较。
  - 掩码 IoU < 0.5，或者没有超过初始 IoU，就拒绝优化结果；被遮挡的物体直接跳过。
  - 管线默认调用时 `Enable_shape_ICP=False`。
  - 来源：https://github.com/facebookresearch/sam-3d-objects/blob/main/sam3d_objects/pipeline/inference_utils.py
- **fal 托管版（已核实 OpenAPI）：**
  - 输入：`mask_urls`（每个物体一个掩码），以及 `pointmap_url`（"external pointmap/depth data (NPY or NPZ format)"）。
  - 输出：`metadata`，含 `rotation` 四元数 [x,y,z,w]、`translation`、`scale` [sx,sy,sz]、`camera_pose`。
  - 一次调用可以处理多个物体。
  - 坐标系约定没有写明，**要用一个已知物体实测**。
  - 来源：https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=fal-ai/sam-3/3d-objects

**2. 学习型位姿估计器：FoundationPose、Any6D、GizmoAct**

- **FoundationPose：**
  - 只估 6 DoF，要求网格已经是米制尺度。
  - SimuScene 说它 "is sensitive to large errors in the initial scale or object center"，所以先用单向 Chamfer 加多起点尺度 {0.5, 0.75, 1.0, 1.25} 解出尺度和平移，再交给 FP 精修旋转（https://arxiv.org/html/2606.03994v1 ）。
  - 许可只限研究或评测（https://github.com/NVlabs/FoundationPose/blob/main/LICENSE ）。
- **Any6D：** 估计 9 DoF（各轴尺寸）。作者自己承认在 "initial 3D shape is inaccurate" 时效果差；只限学术用途（https://arxiv.org/html/2503.18673 ）。
- **Lucida / GizmoAct 表 2**（生成资产 + 估计深度，和你们的设置最接近；https://arxiv.org/html/2608.30821 ）：
  - R2S-Object 的深度来自 Pi3X；CA-1M 的深度是 LiDAR 加 LingBot-Depth 补全。
  - ADD-SB 单位是米。

| 方法 | R2S-Object ADD-SB / @0.05 / 3D IoU | CA-1M ADD-SB / @0.05 / 3D IoU |
|---|---|---|
| Any6D | 0.086 / 46.8% / 0.388 | 0.116 / 42.2% / 0.355 |
| SAM 3D | 0.050 / 61.6% / 0.482 | 0.062 / 56.3% / 0.434 |
| RecGen（1 视图） | 0.040 / 79.2% / 0.499 | — |
| **GizmoAct** | **0.017 / 92.0% / 0.719** | **0.021 / 83.4% / 0.607** |

- GizmoAct 表 3：从 SAM 3D 的位姿出发，R2S-Object 上达到 0.025 / 91.2% / 0.633。
- GizmoAct 表 4，R2S-Scene，SAM 3D vs Lucida：场景 CD 0.022 vs 0.010 m²，场景 F-score 0.794 vs 0.924。
- **GizmoAct 至今没有代码。** 2026-10-14 用 `gh search repos GizmoAct` 没搜到；项目页 https://lucida-r2s.github.io/ 。

**3. ICP、Umeyama 和渲染比对（可以自己写，笔记本就能跑）**

- **Scene-SAM3D**（ScanNet++ 真实数据，网格固定，只优化相似变换；https://arxiv.org/html/2607.16805 ）：

  | 方法 | 场景 CD（cm） | F@0.05 | IoU |
  |---|---|---|---|
  | 反投影 | 8.05 | 0.58 | 0.36 |
  | ICP | 7.18 | 0.60 | 0.39 |
  | 本文 + ICP | 6.89 | 0.61 | 0.40 |
  | 可微高斯渲染 | **4.76** | **0.69** | **0.57** |

  - 渲染比对比 ICP 再降约 31%。
  - H200 上 10 个视角耗时 34.83 s。
  - 代码写的是 "will be released"。
- **ReScene**（ScanNet 30 个真实场景，多视图 RGB，不用深度；https://arxiv.org/html/2606.28060v1 ）：
  - 流程：SAM 3D 生成，FPFH+RANSAC 初始化，Sim(3) ICP。
  - 约束：尺度限在 [0.90, 1.10]，每步和累计旋转都不超过 20°，最多 60 轮。
  - **接受门槛：** RMSE 不能变大，内点率下降不超过 0.01，否则保留原位姿。
  - 结果：CD 8.40 / F@5 68.99 / NC 79.90（CD 单位 ×10⁻²）。单图 SAM 3D 是 17.54 / 36.62 / 57.38，RICO 是 11.47 / 62.45 / 74.72。
- **φ-RIE**（ScanNet++，规范空间生成器 TRELLIS / ReconViaGen；https://arxiv.org/html/2609.26795 ）：
  - 用观测到的稳健尺寸初始化尺度。
  - 在「直立」假设下，偏航按 10° 步长搜索。
  - 部分点云对完整网格做 ICP，再精修尺度和平移。
  - 候选打分：对称最近点距离，截断在 3 cm。
  - 失败就换 5 个候选的「朝上轴」重试。
  - 场景级数字见 §4.3。**这一套正好是「规范空间生成器 + 自己配准」的现成配方。**
- **GRASE**（ICLR 2027 在审，按我们的 PDF 笔记）：
  - 参数：水平位置 2 个、偏航 1 个、尺寸 3 个；底面贴着支撑面。
  - 先 ICP，再让 VLM 对比三帧渲染和原图做微调，最后做有界坐标搜索（3 层 × 4 遍，步长 1 / 0.5 / 0.25）。
  - 目标函数：1 − 掩码 IoU，加边界距离，加最差视角，加点到面距离。
  - 报告的数字：Imaginarium 物体级 mIoU 0.7425（GPT-6 + TRELLIS.2 + 点云基线是 0.2066），物体 CD 2.19 cm；Replica 物体级 mIoU 0.4121，CD 4.52 cm。
  - 这一轮 OpenReview 被反爬挡住，**没能重新核实**（`notes/grase-reading.md`）。
- **其他：**
  - 3D-RE-GEN：4 DoF（平面平移、偏航、统一尺度），剪影加点到网格损失；只有合成数据的数字（IoU 0.63）（https://arxiv.org/html/2512.17459 ）。
  - CAST：AlignGen 预测规范点再做 Umeyama，每个物体约 1 s；只有合成数据的数字（https://arxiv.org/html/2502.12894 ）。
  - HARMONY：统一尺度加偏航，几何指标只报了合成的 Front3D（CD 0.049 vs SAM3D* 0.056）（https://arxiv.org/html/2609.26793 ）。

### 3.2 小结：什么精度是现实的

- **现成的、不训练的最好方案：** SAM 3D 联合预测，再加点图 ICP 和剪影精修。
  - 预期物体中心误差约 5 cm，3D IoU 约 0.45–0.5（R2S-Object、CA-1M 上 SAM 3D 那一行）。
  - 渲染比对还能让场景 CD 再降约 30%（Scene-SAM3D）。
- **规范空间生成器 + 自己配准：** 有 φ-RIE、ReScene 的配方可以抄。真实数据上场景级 CD 能做到约 5–8 cm。
- **单次 FoundationPose 或 Any6D 不推荐：** 尺度没解好就会崩；许可也只限研究。
- **想要 2 cm 级精度：** 目前只有 GizmoAct（训练过的 VLM 迭代精修）做到了，没有代码。
- **小物体额外要注意：** 一个 60 px 的物体，在 Pi3X 点云里可能只有几百个点，深度噪声相对于物体尺寸很大（推算）。
  - 对小物体，剪影项（多帧掩码 IoU）比点云项更可靠。
  - 还要强制「底面落在支撑面上」（GRASE 和 3D-RE-GEN 都这样做），这能消掉高度和一部分深度误差。

---

## 4. 小物体：低分辨率、遮挡与输入预处理

### 4.1 生成器实际看到的是多少像素（读预处理代码，已核实，行号以 2026-10-14 的 main 为准）

| 生成器 | 预处理 | 去背景 |
|---|---|---|
| TRELLIS | `trellis/pipelines/trellis_image_to_3d.py` 的 `preprocess_image`：按 alpha 取框，放大 1.2 倍裁成正方形，再用 LANCZOS 缩放到 **518×518**，送 DINOv2（[源码](https://github.com/microsoft/TRELLIS/blob/main/trellis/pipelines/trellis_image_to_3d.py)） | rembg u2net；输入已有 alpha 时跳过 |
| TRELLIS.2 | `trellis2/pipelines/trellis2_image_to_3d.py`：裁剪逻辑同上，但不留边。DINOv3 ViT-L/16 先在 512、再在 **1024** 上各编码一次（[源码](https://github.com/microsoft/TRELLIS.2/blob/main/trellis2/pipelines/trellis2_image_to_3d.py)） | BiRefNet（RMBG-2.0） |
| Hunyuan3D-2 / 2.1 | `hy3dgen/shapegen/preprocessors.py` 的 `ImageProcessorV2(size=512)`：border_ratio 0.15，物体占画面 85%；白底；conditioner 再缩放、中心裁成 518 送 DINOv2（[源码](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/hy3dgen/shapegen/preprocessors.py)） | **必须**自己给 alpha。没有 alpha 时整张图都被当成物体 |
| SAM 3D Objects | 输入是**整张图加你的掩码**（RGBA）。`preprocess_utils.py` 在掩码周围留 0.1 边、补成正方形，bicubic 缩放到 518；整张图也缩放到 518 作为第二路条件（[源码](https://github.com/facebookresearch/sam-3d-objects/blob/main/sam3d_objects/pipeline/preprocess_utils.py)）。需人工审批下载的 `pipeline.yaml` 是否覆盖了这些默认值：**未核实** | 没有去背景模型，直接用 `image * mask`，所以掩码质量直接决定结果 |
| TripoSG | `scripts/image_process.py` 白底、留 10% 边；HF 的 `BitImageProcessor` 再把短边缩到 256 并**中心裁成 224**（[配置](https://huggingface.co/VAST-AI/TripoSG/blob/main/feature_extractor_dinov2/preprocessor_config.json)） | RMBG-1.4 |
| Step1X-3D | foreground_ratio 0.95；dinov2-with-registers-large，518（[源码](https://github.com/stepfun-ai/Step1X-3D/blob/main/step1x3d_geometry/models/pipelines/pipeline_utils.py)） | rembg bria |
| Hi3DGen | 先用 StableNormal-turbo 在 768 上预测法线，再在 518 上对法线图跑 DINOv2（[源码](https://github.com/Stable-X/Hi3DGen/blob/main/hi3dgen/pipelines/hi3dgen.py)） | BiRefNet |
| Amodal3R | **不裁剪**，整张图缩放到 518；掩码分三级：背景 255、可见 188、被遮挡 0（[README](https://github.com/Sm0kyWu/Amodal3R)，[源码](https://github.com/Sm0kyWu/Amodal3R/blob/main/amodal3r/pipelines/image_to_3d.py)） | 用你给的掩码 |

**换算到一个 60×60 px 的杯子（推算）：**
- TRELLIS：裁出约 72 px，放大约 7 倍到 518。
- TRELLIS.2：放大约 17 倍到 1024。
- SAM 3D：物体那一路放大约 8 倍到 518。
- Amodal3R：不裁剪，杯子在 518 的整图里只占约 16–20 px，大约 1–2 个 14 px 的 patch。**它不适合直接喂整帧，要先自己裁**（推算）。

模型真正拿到的信息就是这约 60 px，放大不会凭空增加细节。

### 4.2 关于低分辨率和遮挡，有哪些证据

- **没有找到任何论文直接测「输入分辨率或物体像素大小 vs 生成质量」的曲线。** 这是一个空白，你们自己可以补一个小实验：同一个物体分别用 60、120、240 px 的裁剪去生成。
- **SAM 3D：**
  - 训练时用了 "Blur augmentation"（先降采样再升采样），论文原话说它 "especially important to handle cases for motion blur and small objects"；另外还对掩码做腐蚀和膨胀增强。
  - 但作者也说这些增强的作用 "get diluted in a holistic evaluation"，没有给按尺寸分组的数字。
  - 来源：https://arxiv.org/html/2511.16624
- **RecGen 按遮挡程度分组（ADD-SB 误差，越低越好）：**
  - SAM 3D：遮挡 0–3% 时 0.053，40–70% 时 0.116。
  - RecGen：从 0.044 到 0.073。
  - 结论：遮挡加重时，联合预测位姿的模型误差约翻一倍。
  - 来源：https://arxiv.org/html/2604.27106v1
- **Amodal3R（GSO，单视图）：** pix2gestalt + TRELLIS 的 FID 58.82、P-FID 26.43；Amodal3R 是 30.64、7.69。用 4 个视图时 Amodal3R 降到 26.27、5.03。来源：https://arxiv.org/html/2503.13439
- **DeOcc-1-to-3（Occ-LVIS）：** 先用 pix2gestalt 做 2D 补全，V-IoU 从 0.1565 升到 0.3232，F-score 从 0.3721 升到 0.4470。来源：https://arxiv.org/html/2506.21544v2
- **ShapeR：** 去掉图像增强（包括降分辨率和遮挡叠加）后，CD 从 2.375 变差到 3.397。这说明训练时有没有低分辨率增强，影响很大。来源：https://arxiv.org/html/2601.11514
- **φ-RIE（2026-09，ScanNet++ 真实物体，29 个，样本小）：**

  | 生成器 | F1@20 | CD（cm） |
  |---|---|---|
  | TRELLIS | 0.3087 | 7.19 |
  | ReconViaGen | 0.2883 | 8.67 |
  | TRELLIS.2 | 0.2305 | 10.22 |
  | SAM 3D Objects | 0.1847 | 9.41 |

  - **在真实扫描的物体裁剪上，分辨率更高的新模型没有赢。** 这和 SAM 3D 论文自己在 SA-3DAO 上的排名正好相反。
  - 我的解读：评测协议（是否允许配准、阈值多大）会决定排名。要在你们自己的数据上测，不能只信论文排行。
  - 来源：https://arxiv.org/html/2609.26795

### 4.3 生成前的预处理技巧

**一、用图像编辑补全遮挡（证据最多）**
- 3D-RE-GEN 用 Nano Banana 补全，再用 Hunyuan3D 2.0 生成。
  - 消融去掉这一步后，CD 从 0.011 变差到 0.030，F 从 0.85 降到 0.68。
  - 但这个消融同时也去掉了背景生成，两个效果混在一起。
  - 来源：https://arxiv.org/html/2512.17459v1
- HARMONY：VLM 先描述物体，Gemini-Flash-2.5 补全；再让 VLM 检查 "object type, completeness, and shape"，不合格就重新生成，然后送 Hunyuan3D-2。没有单独的消融。来源：https://arxiv.org/html/2609.26793
- Gen3DSR：去掉 amodal 补全后，3D-FRONT 上 F 从 68.82 降到 66.81。来源：https://arxiv.org/html/2404.03421
- CAST：不做 2D 补全，改为在 DINOv2 token 上做遮挡掩码。来源：https://arxiv.org/html/2502.12894
- Pixal3D 的场景管线：SAM3 分割，再用 Qwen-image-edit 补全。来源：https://arxiv.org/html/2605.10922
- GRASE（ICLR 2027 在审）：先用图像编辑补全遮挡，三个视角各生成一个候选，让 VLM 挑。
  - 这一条来自我们自己的 PDF 阅读笔记（`CIS-6220-Deep-Learning-at-Scale/03-final-project/agentic-3d/notes/grase-reading.md`）。
  - 这次 OpenReview 的 PDF 被浏览器验证挡住了，只核到摘要。

**二、超分辨率**
- 只找到 Gen3DSR 一例：它用 SeeSR 把 648×484 的输入放大到 1296×968，理由是原分辨率 "insufficient"。
- 没有单独的消融。来源：https://arxiv.org/html/2404.03421

**三、从视频里挑最好的帧**
- OVOW：选掩码面积最大的帧；最大掩码不到 200 px 的物体直接丢掉。来源：https://arxiv.org/html/2606.31388v1
- LiteReality："top-k most visible" 的裁剪（它做的是资产检索，不是生成）。来源：https://arxiv.org/html/2507.02861
- Scene-SAM3D：锚点帧选 3D 占据体积最大的视角，再贪心补覆盖。和随机选帧相比，Replica 上 CD 从 61.96 降到 41.60。来源：https://arxiv.org/html/2607.16805
- AHa-3D 作者自己的指南（`docs/OBJECT_GENERATION.md`）：
  - "Select clear frames with enough visible object pixels. Prefer one reconstruction per object"
  - "Do not regenerate each video frame and assume its meshes are temporally consistent"
  - "Record cropping, occlusion and source resolution as input limitations"
  - 来源：https://github.com/KevinXu02/aha-3d/blob/main/docs/OBJECT_GENERATION.md

**四、生成多个候选再挑**
- φ-RIE 的候选池是 TRELLIS 加 ReconViaGen，按配准误差、尺度、能否落稳打分，失败就重试。
  - 只用 TRELLIS：F1 0.301，CD 11.767 cm。
  - 固定优先级：0.336，7.638 cm。
  - 按证据挑选、不重试：0.348，7.196 cm。
  - 挑选加重试：0.383，5.720 cm。
  - 挑选本身只多带来约 0.012 F1，重试多带来约 0.035，但每个场景的构建时间从 35.68 分钟翻倍到 70.82 分钟。
  - 来源：https://arxiv.org/html/2609.26795
- 没有找到用「剪影 IoU」或「VLM 挑选」做 best-of-N 消融的论文。

### 4.4 能用视频多帧的多视图生成器

- **Hunyuan3D-2mv：** 输入槽位固定为前、左、后、右，每个槽有视角编码，所以要求规范视角，**不适合直接塞任意视频帧**。来源：https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/hy3dgen/shapegen/models/conditioner.py
- **TRELLIS `run_multi_image`：** 接受任意、无位姿的多张图，但这是免训练的拼法，README 原话 "may not give the best results"。
- **ReconViaGen：** 用 VGGT 处理无标定、任意视角的多图。
  - Dora-bench 上 F-score：ReconViaGen 0.953，TRELLIS 单图 0.807，TRELLIS 多图 0.843，Hunyuan3D-2mv 0.937。
  - 代码已发布，fal 上有基于 TRELLIS.2 的 v0.5，$0.25–0.35。
  - 来源：https://arxiv.org/html/2510.23306v1 、https://github.com/GAP-LAB-CUHK-SZ/ReconViaGen
- **Pixal3D 多视图（2026-09）：** 要给每个视角的 camera-to-world 和 FOV（`transforms.json`）。第一帧必须是物体的「规范正面」，图片不会被裁剪或缩放。
  - 视频帧的位姿可以从 Pi3X 拿到，但要先换算成以物体为中心、Z 朝上的坐标系（推算）。
  - 来源：https://github.com/TencentARC/Pixal3D
- **Amodal3R：** 支持多张图、不需要位姿，按可见程度排序。
- **SAM 3D：** 官方只支持单视图。有第三方多视图版本 MV-SAM3D（https://github.com/devinli123/MV-SAM3D ），还有 Scene-SAM3D（需要标定的位姿和深度）。

### 4.5 一个 60×60 px、被遮挡的杯子，具体怎么处理（综合建议）

1. **在整段视频里挑帧。**
   - 按掩码面积 × 可见比例（物体框不贴图像边）排序。加不加清晰度（Laplacian 方差）是我们自己的选择，没有论文依据。
   - 掩码不到约 200 px（约 14×14）的物体直接放弃生成，退回基本体。
2. **用 SAM 3 的掩码，不要让 rembg 或 RMBG 在 60 px 上自己猜。**
   - SAM 3D 正好吃整张图加掩码。
   - 喂 Hunyuan、TRELLIS、TripoSG 时，自己做 RGBA 裁剪。
3. **遮挡超过约 30% 时，先在 2D 补全。**
   - 用 Gemini、Qwen-image-edit 或 FLUX 都可以，再让 VLM 检查补全结果是否完整。
   - 原图也保留下来，作为另一个候选。
   - 遮挡物的掩码可以直接用其他物体的 SAM 3 掩码（SceneComplete 和 Amodal3R 都是这样做的）。
4. **超分辨率（×4，例如 Real-ESRGAN 或 SeeSR）只作为 A/B 对照，不设为默认**，因为没有消融证明它有用。
5. **准备 2–3 个候选**（换生成器、换帧、换随机种子），用 §3 的配准残差加多帧剪影 IoU 打分。重试次数设上限。

---

## 5. 生成网格能不能改善几何指标

**直接证据：没有。** 子 agent 查了 SAM 3D、Lucida、HARMONY、ReScene、Scene-SAM3D、SimuScene、Mira-Scene、VIGA、PrimitiveAnything 等，都没有找到在**真实数据**上做以下任何一种对比的论文：
- 基本体 vs 生成网格
- 包围盒代理 vs 生成网格
- 同一位姿下，生成网格 vs 真值网格

所以「生成网格会改善 Chamfer、F-score」目前**没有现成数字可以引用**，要靠你们自己测。

**间接证据：**

1. **摆放误差决定场景级指标。**
   - 同一批网格，只改摆放方法，场景 CD 就从 6.89 降到 4.76 cm（Scene-SAM3D 表 6，https://arxiv.org/html/2607.16805 ）。
   - Lucida 表 4（R2S-Scene，https://arxiv.org/html/2608.30821 ）：

     | 方法 | 场景 CD（m²） | 场景 F-score | 物体 CD | 物体 F-score |
     |---|---|---|---|---|
     | SAM 3D | 0.022 | 0.794 | 0.038 | 0.704 |
     | Lucida | 0.010 | 0.924 | 0.034 | 0.736 |

   - 场景 CD 减半，物体级的形状指标几乎没动。
   - 注意：Lucida 的资产来自 Seed3D 2.0，它也精修各向异性尺度，所以这不是严格的控制变量实验。
2. **网格来源会影响后面的配准。** 同样用 FoundationPose，SA-3DAO 上 ADD-S@0.1：HY3D-2.0 网格 0.5396，HY3D-2.1 网格 0.4177（SAM 3D 表 3）。
3. **摆得好的生成网格，在真实数据上能赢过稠密重建。**
   - ReScene CD 8.40 vs RICO 11.47（ScanNet，https://arxiv.org/html/2606.28060v1 ）。
   - ShapeR CD 2.375 vs FoundationStereo TSDF 6.483（https://arxiv.org/html/2601.11514 ）。
4. **在 Blender agent 里直接接生成器，反而可能更差。** VIGA（2026-10-14 更正：2606.02580 是 SEIG 的 "Thinking in Blender"，它拿 VIGA arXiv 2601.11109 当对照；下面的数字是 SEIG 表 1、2 里 VIGA full 和 VIGA VLM-only 的对比，https://arxiv.org/html/2606.02580 ）：

   | 数据集 | 只用 VLM 搭基本体（PSNR / CLIP） | 加 SAM / SAM-3D（PSNR / CLIP） |
   |---|---|---|
   | NeRF-synthetic | 12.33 / 0.8451 | 11.18 / 0.7986 |
   | Edit3D | 11.52 / 0.8366 | 12.48 / 0.7883 |

   - 作者的解释："fragmented, mis-colored meshes that fail to assemble into a coherent scene"；agent 还会覆盖掉 SAM-3D 生成的纹理；单视图提升会出现 Janus 问题（正面特征被复制到背面）。
   - 这些都只是图像级指标，没有几何指标。
5. **基本体抽象本身的上限**（物体级，参考用）：PrimitiveAnything 在 HumanPrim 上 CD 0.0404，Voxel-IoU 0.484（https://arxiv.org/html/2505.04622 ）。
6. **AHa-3D 作者的做法：** 试过 SAM 3D Objects 和 TRELLIS.2 后搁置了。文档原话："an earlier object-generation pilot (SAM 3D Objects and TRELLIS.2) was completed and then deferred"，以及 "Generated meshes are candidates for complex static furniture and decor"（https://github.com/KevinXu02/aha-3d/blob/main/docs/OBJECT_GENERATION.md ）。

**推算：小物体对整屋几何指标的贡献很小。**
- 场景级 Chamfer 和 F-score 按表面面积采样。
- 一个马克杯的表面积约 0.03–0.05 m²，一间 4×5 m 的房间光墙、地板、天花板就有约 90 m²。
- 所以杯子从盒子换成精确网格，场景 CD 和 F-score 几乎不会动。
- **要证明「生成小物体有用」，必须报物体级指标，并且按尺寸分组报告：**
  - 物体级 CD 和 F-score：对真值激光扫描按物体框裁剪后再算。ScanNet++ 有激光扫描；ARKitScenes 也有激光扫描（我记得有，本轮**未核实**）。
  - 3D 框 IoU、ADD-S。
  - 留出帧上的剪影 IoU：不需要真值，可以作为补充。

---

## 6. 复核旧结论：「Hunyuan3D 只适合当可选的外观升级」

**结论：这句话大体还成立，但理由要更新，范围也要收窄。**

**仍然成立的部分：**
- **Hunyuan3D 2.x 的输出在规范空间里，不带位姿。**
  - 真实场景的形状指标上，HY3D-2.0 和 2.1 都明显低于 SAM 3D：SA-3DAO F1@0.01 分别是 0.157、0.140，SAM 3D 是 0.234。
  - 配 FoundationPose 后的摆放（SA-3DAO 3D IoU 0.29、0.24）也远低于 SAM 3D 的联合预测（0.43）。
- **2.5、3.0、3.1 都只有 API**，也不返回位姿。按 §5，场景级几何指标主要由摆放决定。
- 所以「用 Hunyuan3D 作为主要的几何和摆放来源」站不住。
- 对于小物体，在场景指标里真正看得出来的主要是外观。所以对小物体，「外观升级」这个定位其实是准确的。

**需要更新的部分：**
1. **主力不该是 Hunyuan，而是 SAM 3D Objects。** 它自带相机系位姿，能吃外部点图，训练时专门处理了遮挡和小物体。
   - fal 上一次 $0.02，可以免去人工审批和安装。
   - 但 φ-RIE 在 ScanNet++ 真实裁剪上测出 SAM 3D 的形状最差（F1@20 0.18），**证据互相矛盾，要在你们的数据上测**。
2. **Hunyuan3D-Omni 不只是外观工具。**
   - 它的包围盒条件可以把「测量出的长宽高比」直接送进生成；点云条件可能直接给出对齐结果。
   - 这是 Hunyuan 家族里唯一值得做个小实验的版本（10 GB，笔记本勉强能跑）。
   - 定量效果未知（论文只有定性图）。
3. **Hunyuan3D-2.0 或 2mini 的纯形状，是 12 GB Blackwell 笔记本上最容易装通的生成器**（6 GB，不用编译 CUDA 扩展），适合开发期做「生成 + 配准」的联调。
4. 新出现的 **Pixal3D**（MIT，像素对齐输出）把「朝向」问题在生成阶段就解决了。这一点比 Hunyuan 3.1 更贴合「视频 → 场景」的需求。

**修正后的说法：** 生成式网格在本项目里是**按物体可选的形状加外观来源**。
- 默认后端用带位姿的 SAM 3D（或 Pixal3D）。
- 每个生成网格都必须过我们自己的配准和剪影门槛。过不了就退回基本体。
- Hunyuan3D 只作为本地开发后端，以及 Omni 包围盒条件的一个小实验。

---

## 7. 建议与 agent 工具接口

### 7.1 选哪个生成器

| 优先级 | 后端 | 跑在哪里 | 为什么用它 | 每次调用的成本 |
|---|---|---|---|---|
| **1（默认）** | **SAM 3D Objects** | 先用 fal（$0.02，传 `mask_urls` 和 `pointmap_url`）。要用 `layout_post_optimization`、`stage1_only`、固定种子时，再到 Betty `mig45` 或 Colab A100 上自己部署（22 GB，13 s/物体），这需要 HF 人工审批 | 唯一一个专门为真实场景遮挡和小物体训练、自带相机系位姿、又能吃外部点图的；摆放精度在现成方案里最好（§3.1） | fal $0.02；Betty mig45 补贴价 $0.25/小时 |
| 2（第二候选，规范空间） | **TRELLIS v1**（fal $0.02），或 TRELLIS.2（fal $0.25–0.35） | fal | φ-RIE 在 ScanNet++ 真实裁剪上测出 TRELLIS v1 的 F1 最高；配准照 φ-RIE、ReScene 的配方自己写 | $0.02–0.35 |
| 3（开发期） | **Hunyuan3D-2mini 或 2.0，纯形状** | 12 GB 笔记本 | 6 GB 显存、不用编译 CUDA 扩展，最容易装通；适合离线调配准代码和 agent 接口 | 本地，免费 |
| 4（小实验） | Hunyuan3D-Omni，包围盒条件 | 笔记本（10 GB，勉强）或 Colab | 用测量出的长宽高比控制生成，是可能的新意点；没有定量证据 | 本地 |
| 5（探索） | **Pixal3D** | fal $0.30，或 Colab | 输出和视图对齐，只剩深度和尺度两个数要解；MIT；SIGGRAPH 2026 | $0.30 |
| 不建议做主力 | Hunyuan 3.1、Tripo、Meshy 的 API | — | 不返回位姿，也没有真实场景的公开评测；只适合给演示渲染换更好看的纹理 | $0.20–0.60 |

**课程期预算（推算）：**
- 规模：5–10 个场景 × 每场景 15 个物体 × 每个物体 3 个候选，约 225–450 次调用。
- SAM 3D 和 TRELLIS v1 走 fal：各约 $5–9。
- 如果全部用 TRELLIS.2：约 $56–158。
- 在 Betty 上自己部署 SAM 3D：450 × 13 s ≈ 1.6 GPU 小时，加上加载和调试，约 $2–10。
- 远低于每人 $50 的额度。

### 7.2 怎么接成 agent 工具

**原则：**
- 生成和配准**拆成两个工具**。这样 agent 可以只重新跑配准（比如换朝上轴、换支撑面），不用重新生成。
- 生成走**异步批处理**：一次提交多个物体，生成期间 agent 继续用基本体搭其他东西，不阻塞。

**工具 1：`gen3d_request`**

```text
gen3d_request(
  object_ids: list[str],        # 来自 SAM 3 轨迹或 AHa-3D measure 阶段的物体清单
  backend: "sam3d" | "trellis" | "trellis2" | "hy3d_shape" | "hy3d_omni_bbox" | "pixal3d" | "auto",
  n_candidates: int = 2,        # 上限 3
  frames: "auto" | list[int],   # auto = 按掩码面积 × (1 − 截断比例) × 清晰度取前 k 帧
  inpaint: "auto" | "on" | "off",   # auto：估计遮挡超过约 30% 时才补全
  texture: bool = False         # 先只要形状，接受之后再补纹理
) -> job_id
```

**工具内部按顺序做这些事：**
1. 小于门槛（最好那一帧的掩码 < 约 200 px）就直接返回 `too_small`。
2. 挑帧、裁 RGBA（留 10–20% 边）。
3. 需要时做 2D 补全，原图也保留成一个候选。
4. 调后端。
5. 清理网格：只留最大连通分量、减面到 ≤ 20k 面、统一成 Z 朝上并以米为单位。
6. 按 (帧, 掩码哈希, 后端, 种子) 缓存。

**工具 2：`place_mesh`**

```text
place_mesh(object_id, candidate_id,
           init: "backend_pose" | "obb",   # SAM 3D 和 Pixal3D 用后端给的位姿，其他用 OBB
           dof: 7 | 9,                       # 9 = 各向异性尺度
           support: plane_id | None,
           yaw_hint: float | None)
-> PlacementResult
```

**`place_mesh` 的步骤（照 φ-RIE、ReScene、GRASE 的做法）：**
1. **初始化。**
   - SAM 3D：先用 Pi3X 位姿把相机系的 R、t、s 换到世界系。
   - 规范空间网格：尺度取 SAM 3 掩码点云（多帧融合）的稳健 OBB 尺寸；偏航每 10° 一个起点，加 5 个候选的朝上轴。
2. **配准。** 部分点云对完整网格做 ICP（单向：观测点到网格）。尺度限在 [0.75, 1.25] 倍 OBB（GRASE）或 [0.9, 1.1]（ReScene）；底面贴着支撑面。
3. **剪影精修。** 用 K=3–5 帧做有界坐标搜索。
   - 目标：1 − 掩码 IoU，加边界距离，加最差视角，加点到面距离（GRASE 表 3 的权重：边界 0.4、最差视角 0.35、点云 0.12；我们的阅读笔记提醒，PDF 抽出的表格有错位，实现前要对照原文）。
   - 剪影不需要 nvdiffrast：把网格表面采样 2 万个点，投影到图像上再膨胀一下就是剪影。这样能避开 sm_120 的编译问题（推算）。
4. **接受门槛**（建议值，第 1 周用 10 个物体校准）：
   - 多帧平均剪影 IoU ≥ max(0.6, 同一物体基本体的 IoU + 0.03)。也就是**必须比基本体好**。
   - 观测点到网格的 Chamfer ≤ max(1.5 cm, 0.1 × 最长边)。
   - 尺寸在 OBB 的 0.75–1.25 倍之内。
   - 穿进支撑面不超过 1 cm。

**返回值（PlacementResult，JSON）：**

```json
{
  "object_id": "obj_017", "status": "accepted",
  "backend": "sam3d@fal", "candidate_id": 1, "frame": 412, "seed": 7,
  "mesh_glb": "gen/obj_017/c1/mesh.glb",
  "matrix_world": [[...4x4...]], "scale_xyz": [0.09, 0.09, 0.11],
  "fit": {"sil_iou_mean": 0.71, "sil_iou_min": 0.55, "n_views": 4,
          "chamfer_obs2mesh_cm": 1.2, "primitive_sil_iou": 0.62, "inlier_ratio": 0.83},
  "input": {"mask_px": 3600, "occlusion_est": 0.2, "inpainted": false},
  "cost_usd": 0.02, "seconds": {"gen": 14, "place": 8},
  "blender_snippet": "bpy.ops.import_scene.gltf(filepath=...); obj.matrix_world = ..."
}
```

- `mesh_glb` 在物体局部坐标系里：Z 朝上，单位是米，原点在底面中心。
- `matrix_world` 是放进世界系的变换。

`status` 的取值：
- `accepted`
- `rejected_fit`：配准或剪影没过门槛
- `too_small`
- `backend_error`
- `timeout`
- `wrong_category`：铰接物体或尺寸敏感的柜体，按 AHa-3D 文档应该走程序化建模

### 7.3 每个物体大约要多久

| 步骤 | 在哪里跑 | 耗时 | 依据 |
|---|---|---|---|
| 挑帧、裁剪 | CPU | < 1 s | 推算 |
| 2D 补全（可选） | Gemini 或 Qwen-image-edit 的 API | 约 5–20 s | **未核实** |
| SAM 3D，自己部署 | A100 | 13.0 ± 1.4 s（不含模型加载） | RecGen 表 S3 |
| SAM 3D 或 TRELLIS，走 fal | fal | 排队加推理时间没有公开 | **未核实**，第 1 周实测 |
| TRELLIS.2，512³ | H100 3 s；A100 估计 5–8 s | — | README；A100 那个数是推算 |
| Hunyuan3D-2mini 纯形状 | 笔记本 | **未核实**（估计 10–30 s） | — |
| 配准加剪影精修 | 笔记本 CPU 或 GPU | 约 5–30 s | 推算。参考：Scene-SAM3D 用可微高斯渲染，10 个视角在 H200 上 34.83 s |
| **合计** | — | **每个候选约 30–90 s**；一个场景 15 个物体 × 2 个候选，串行约 15–45 分钟，异步并发可以缩到约 5–10 分钟 | 推算 |

### 7.4 失败怎么处理

| 失败情况 | 处理 |
|---|---|
| 后端报错或超时 | 换另一个后端重试 1 次（fal 和自己部署互为备份），仍然失败就用基本体 |
| 朝上轴错了（瓶子横躺之类） | 依次试 5 个候选的朝上轴（φ-RIE） |
| 旋转对称物体（杯子、花瓶）偏航定不下来 | 只看剪影；偏航误差不计入失败 |
| 网格碎片化、颜色错（VIGA 观察到的问题） | 只留最大连通分量；连通分量太多就拒绝；**禁止 agent 改写生成网格的材质** |
| 补全幻觉（多出把手之类） | 原图那个候选一起参加打分，剪影 IoU 高的胜出 |
| 场景预算 | 每个场景设生成次数上限，例如 30 次，以及 API 美元上限；超出后剩下的物体都用基本体 |
| 每次决定都记日志 | 后端、帧、门槛值、用的是基本体还是生成网格，方便之后做「基本体 vs 生成」的消融 |

### 7.5 建议的最小实验（课程期）

- **三个对照组，按物体评测：**
  1. 基本体（AHa-3D 默认）
  2. SAM 3D 联合预测，加我们的 ICP 和剪影精修
  3. TRELLIS 加我们的配准
- **按尺寸分组：** < 10 cm、10–30 cm、> 30 cm。
- **指标：**
  - 物体级 CD 和 F-score（对按框裁剪的激光扫描）
  - 3D 框 IoU、ADD-S
  - 留出帧上的剪影 IoU
- **两个便宜的附加实验：**
  1. 补全开 vs 关。
  2. 60、120、240 px 三档裁剪分辨率。这一项能补上 §4.2 指出的文献空白，有可能成为课程报告的一个小贡献。

---

## 8. 未核实清单

- **Hunyuan3D 3.1：** 质量、延迟都没有公开评测。「最多 8 个视图」只来自官方推文。国际版 API 是否只开放 ap-singapore 和 na-siliconvalley 两个区域，只部分核实。
- **Hunyuan3D-Omni：** 点云模式的输出坐标系是否和输入点云的归一化坐标系一致，没核实。包围盒、点云条件的定量效果没有任何数字。
- **Pixal3D：** 显存只有社区补丁的说法（1024 分辨率峰值约 11 GB），官方没给数，耗时也没写。
- **SAM 3D on fal：** 返回的 `rotation` / `translation` / `scale` / `camera_pose` 是什么坐标系约定，`model_glb` 是规范空间还是已经摆好位姿，"$0.02 per unit" 里的 unit 指什么，延迟多少，都没核实。
- **SAM 3D 自己部署：** 需人工审批下载的 `checkpoints/pipeline.yaml` 是否覆盖了裁剪和 518 的默认预处理，没核实。在 Blackwell 上重编 kaolin 和 pytorch3d 是否顺利，没核实。
- **耗时：** Hunyuan3D 2.x、TripoSG、Step1X-3D 纯几何、Hi3DGen、Amodal3R 每个物体的耗时和显存都没核实。Hunyuan3D-2.1 的 10 GB 形状模型在 12 GB 笔记本上能不能实际跑，没核实。
- **Betty：** 学生的 $50 额度适用补贴价还是非补贴价，没核实。
- **API 账户：** Tripo 的免费 API 额度没核实。腾讯云中国站开通需要实名认证，非中国身份能否通过没核实。
- **GRASE：** 本轮 OpenReview 被反爬挡住，所有数字都来自我们自己的 PDF 阅读笔记，没有重新核实。
- **ARKitScenes：** 是否带可用作物体级形状真值的激光扫描，凭记忆，本轮没核实。
- **低分辨率：** 没找到任何「裁剪分辨率 vs 生成质量」的定量研究。超分辨率有没有用，也没有消融证据。
- **RecGen：** HF 权重已核实（CC BY-NC 4.0，2026-04-28 创建）；推理代码仓库没核实。

---

## 9. 主要来源（正文已逐条附 URL，这里汇总）

**生成器仓库和模型卡：**
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- https://github.com/Tencent-Hunyuan/Hunyuan3D-Omni
- https://github.com/Tencent-Hunyuan/HY3D-Bench
- https://github.com/Tencent-Hunyuan/Hunyuan3D-Buffalo1.0
- https://github.com/microsoft/TRELLIS
- https://github.com/microsoft/TRELLIS.2
- https://github.com/facebookresearch/sam-3d-objects （README 原话 "handling small objects and occlusions"；`doc/setup.md`；`LICENSE`）
- https://github.com/TencentARC/Pixal3D
- https://github.com/VAST-AI-Research/TripoSG
- https://github.com/stepfun-ai/Step1X-3D
- https://github.com/Stable-X/Hi3DGen
- https://github.com/DreamTechAI/Direct3D-S2
- https://github.com/Sm0kyWu/Amodal3R
- https://huggingface.co/TRI-ML/RecGen

**论文：**
- SAM 3D：https://arxiv.org/html/2511.16624 ；CVPR 2026 版 https://openaccess.thecvf.com/content/CVPR2026/html/Chen_SAM_3D_3Dfy_Anything_in_Images_CVPR_2026_paper.html
- Pixal3D：https://arxiv.org/html/2605.10922
- RecGen：https://arxiv.org/html/2604.27106
- Lucida / GizmoAct：https://arxiv.org/html/2608.30821
- Scene-SAM3D：https://arxiv.org/html/2607.16805
- ReScene：https://arxiv.org/html/2606.28060v1
- φ-RIE：https://arxiv.org/html/2609.26795
- SimuScene：https://arxiv.org/html/2606.03994v1
- VIGA：https://arxiv.org/html/2606.02580
- Hunyuan3D-Omni：https://arxiv.org/html/2509.21245
- 3D-RE-GEN：https://arxiv.org/html/2512.17459
- HARMONY：https://arxiv.org/html/2609.26793
- Gen3DSR：https://arxiv.org/html/2404.03421
- CAST：https://arxiv.org/html/2502.12894
- Amodal3R：https://arxiv.org/html/2503.13439
- DeOcc-1-to-3：https://arxiv.org/html/2506.21544v2
- ShapeR：https://arxiv.org/html/2601.11514
- ReconViaGen：https://arxiv.org/html/2510.23306v1
- OVOW：https://arxiv.org/html/2606.31388v1
- Any6D：https://arxiv.org/html/2503.18673

**价格和算力：**
- 腾讯云国际版：https://www.tencentcloud.com/document/product/1284/75281 、https://www.tencentcloud.com/document/api/1284/75540
- Tripo：https://developers.tripo3d.ai/en/pricing
- Meshy：https://docs.meshy.ai/en/api/pricing
- fal 各模型页的 `llms.txt`（见 §2 表格）
- PARCC：https://parcc.upenn.edu/systems/betty/ 、https://parcc.upenn.edu/about/rates/

**AHa-3D 作者的生成试点说明：** https://github.com/KevinXu02/aha-3d/blob/main/docs/OBJECT_GENERATION.md

**子 agent 分工：** 本文的 API 价格、摆放精度、小物体证据三部分，由三个并行子 agent 查原始页面后汇总。下面这些我又亲自抽查过：
- fal 的 SAM 3D、TRELLIS.2、Hunyuan 3.1 Pro、Pixal3D、ReconViaGen 价格页
- fal SAM 3D 的 OpenAPI schema
- 腾讯云计费页
- φ-RIE 表 II 和表 V
- ReScene 表 1
- Lucida 表 4
- VIGA 表 1 和表 2
- RecGen 表 S3
