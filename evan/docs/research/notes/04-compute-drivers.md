# 04 算力与驱动模型调研：PARCC/Betty、LiteLLM + GLM 5.2、AHa-3D 该用哪个模型驱动

调研日期 2026-10-14。所有价格是 USD / 百万 token（下文简写 `/M`）。每条事实后面附来源链接。【未核实】表示我没找到一手来源，或者只能推断，需要团队实测或在 Ed #69 下面问。

---

## 0. 结论速览

1. **Betty 的 GPU 是 NVIDIA B200（180 GB HBM3e）**，31 个 8 卡 DGX B200 节点。另外有 90 GB 和 45 GB 两种 MIG 切片。用 SSH + Slurm，要求 Penn 校园网或 GlobalProtect VPN，并完成两种认证（三选二）。公开文档里没有 Open OnDemand，也没有 Apptainer，容器走 Pyxis/Enroot。价格：整卡 $1.00/h（补贴价）或 $4.51/h（非补贴价），mig45 是 $0.25/h 或 $1.13/h。**课程的 $50 按哪档价格计费，公开文档没写**。按补贴价算，$50 能买 50 个 B200 整卡小时或 200 个 mig45 小时；按非补贴价，只有约 11 个整卡小时或约 44 个 mig45 小时。
2. **Betty 不适合跑 Blender 的 Workbench/EEVEE 预览**。MIG 切片明确不支持任何图形 API（OpenGL、Vulkan）。整卡能不能用图形 API【未核实】。计算节点能否上网也没写清楚，文档里只出现过一句 "egress restricted"。建议的分工是：**Betty（或 Colab A100）只批量跑 Pi3X/SAM3 感知预处理，用作者默认的 255k px；agent 循环和 Blender 留在本地笔记本上跑**。
3. **GLM-5.2 只接受文本输入，不能看图**。Z.ai 文档、NVIDIA NIM 和 HF 模型卡写的都是 text-only。AHa-3D 要求 agent 看渲染叠图，reviewer 也要看图，所以 **GLM-5.2 不能单独当驱动**。同一家族能看图的是 GLM-5.3-Flash（2026-08-26，开源权重，$0.15/$0.03 缓存/$0.50）和 GLM-5V-Turbo。建议在 Ed #69 问课程的 LiteLLM 能不能开放 GLM-5.3-Flash。
4. **公开证据**：Agentic RSR v2（2026-10-11）新加的表 3，在同一个 DSH harness、18 个 Blender 场景上比较：Claude Opus 5.5 和 Fable 5.1 都是 18/18，GPT-6 Astra 和 Sonnet 5.5 是 15/18，GPT-6.1 Sol 是 12/18，GPT-5.6 Sol 是 4/18，Kimi K3 是 0/18。**你们引用的「Table 4: Astra 18/18 vs 5.6 Sol 10/18」是 v1 的编号**，v2 把它移到了附录表 9（Codex harness）。BVB 排行榜（2026-10-13 更新）上，GPT-6.1 Sol xhigh 73.29 分、每场景 $0.50，几乎追平 Astra xhigh 的 73.82 分、$1.72；GPT-6 Luna xhigh 68.11 分，只要 $0.011。
5. **推荐**：开发阶段用 **GPT-6 Luna + Codex CLI**。这是 AHa-3D 原生的 harness，reviewer 不用 shim，每次约 $0.1–0.25。主实验用 **GPT-6.1 Sol + Codex CLI**，每次约 $1.5–6.6；再用 2–3 次 Astra 做锚点，和作者对齐。便宜消融用 Luna，或者课程 LiteLLM 上的 GLM 模型（GLM-5.2 只能当「不看图」的变体）。20 场景 × 3 变体 × 2 种子共 120 次主跑，用 Sol 约 **$330–660**，用 Astra 约 **$1,500–2,700**（不现实）。全部用 Luna 约 **$15–27**。

---

## 1. PARCC / Betty

### 1.1 硬件

| 项目 | 内容 | 来源 |
|---|---|---|
| GPU 节点 | 31 个 DGX B200 节点（"(31) 8-way GPU nodes"），每节点 8× NVIDIA Blackwell B200，NVLink/NVSwitch | https://parcc.upenn.edu/systems/betty/ |
| GPU 显存 | 每卡 180 GB HBM3e，每节点 1.4 TB | https://parcc.upenn.edu/systems/betty/ |
| GPU 节点 CPU/内存 | 2× Xeon Platinum 8570（112 核），2 TB DDR5，30.72 TB 本地 NVMe | https://parcc.upenn.edu/systems/betty/ |
| 互联 | 专用 NDR400 InfiniBand 计算网，单个实验可以扩展到整个 SuperPOD | https://parcc.upenn.edu/systems/betty/ |
| CPU 节点 | 64 个 AMD EPYC 9374F 标准内存节点（64 核，384 GB），10 个大内存节点（1152 GB） | https://parcc.upenn.edu/systems/betty/ |
| 系统软件 | DGX OS / Ubuntu 24.04 Pro；调度器是 SLURM 和 Run:AI；Lmod 模块；文件系统 VAST 和 Ceph | https://parcc.upenn.edu/systems/betty/ |
| CUDA | Zero-to-MNIST 教程写着 "The cluster only supports CUDA 12.8 currently"；容器页要求 CUDA ≥12.8 | https://parcc.upenn.edu/training/getting-started/zero-to-mnist/ ，https://parcc.upenn.edu/training/software/containers/ |

和 AHa-3D 的兼容性：AHa-3D 各环境固定 torch 2.7.1+cu128（见本机之前的记录），正好对上 CUDA 12.8。B200 是 sm_100，cu128 的 wheel 是否包含 sm_100 的 kernel【未核实，大概率包含，上集群后跑一次 `torch.cuda.get_arch_list()` 确认】。

### 1.2 访问方式

- SSH 主机名是 `login.betty.parcc.upenn.edu`，另有 login01/02/03 三个节点。来源：https://parcc.upenn.edu/training/getting-started/logging-in/
- 认证要求 "any two" 种：Kerberos（`kinit <PennKey>@UPENN.EDU`）、SSH key、Duo。Kerberos 票据每 10 小时续一次。来源同上。
- 网络要求 "You must be on Penn's campus or on the Penn GlobalProtect VPN"。来源同上。
- 账号：PI 要在 ColdFront 里把你加进项目；新账号最多要一小时才生效。来源：https://parcc.upenn.edu/training/getting-started/ ，https://parcc.upenn.edu/training/faculty-info/coldfront/
- **Open OnDemand**：公开文档里没有提到，没有网页 GUI 或桌面会话的说明【未核实，按「没有」规划】。Logging In、Looking Around、Slurm 三页都没有提到 X11/VNC：https://parcc.upenn.edu/training/getting-started/logging-in/
- 登录节点规则是 "Login nodes: edit, sync, submit, _not_ train"，重活要走 `srun/sbatch/salloc`。来源：https://parcc.upenn.edu/training/getting-started/looking-around/

### 1.3 Slurm 分区与限额

| 分区 | 说明 | 每个 Slurm 账户的上限 | 来源 |
|---|---|---|---|
| `dgx-b200` | B200 整卡，每节点 8 卡 | 32 GPUs | https://parcc.upenn.edu/training/slurm/ |
| `b200-mig90` | 90 GB MIG 切片 | 8 MIGs | 同上 |
| `b200-mig45` | 45 GB MIG 切片 | 8 MIGs | 同上 |
| `genoa-std-mem` | CPU 节点 | 640 CPU | 同上 |
| `genoa-lrg-mem` | 大内存 CPU 节点 | 128 CPU | 同上 |

- GPU 用 `--gpus=N` 申请，示例只给了 `dgx-b200`。MIG 是按分区名选的。来源：https://parcc.upenn.edu/training/slurm/
- MNIST 示例的写法是 `--partition=dgx-b200 --gpus=1 --cpus-per-task=14 --mem=256G`。来源：https://parcc.upenn.edu/training/getting-started/zero-to-mnist/
- 自带工具：`parcc_sfree.py` 看空闲资源，`parcc_sqos.py` 看 QOS 上限（walltime、最大 GPU 数），`parcc_sreport.py` 看自己的用量，`parcc_quota.py` 看存储配额。来源：https://parcc.upenn.edu/training/getting-started/parcc-tools/
- 单个作业的最长时限、QOS 名称，公开文档都没写，要用 `parcc_sqos.py` 查。

### 1.4 容器与软件

- 文档写的容器方案是 **Pyxis + Enroot**，例如 `srun --partition=dgx-b200 --container-image=docker://nvcr.io/nvidia/pytorch:25.06-py3 ...`。拉 NGC 镜像要在 `$HOME/.config/enroot/.credentials` 里配置 API key。**Apptainer/Singularity 没有被提到**【未核实是否安装，登录后跑 `which apptainer` 确认】。来源：https://parcc.upenn.edu/training/software/containers/
- 有 `anaconda3` 模块，教程用 `conda create -p $HOME/envs/... python=3.11 uv`。来源：https://parcc.upenn.edu/training/getting-started/zero-to-mnist/ ，https://parcc.upenn.edu/training/software/
- 公开的软件列表里没有 Blender。需要自己下载 Linux tarball 放到 home 或 project 目录【按自装规划】。来源：https://parcc.upenn.edu/training/software/

### 1.5 存储

| 位置 | 配额 | 来源 |
|---|---|---|
| Home `/vast/home/<首字母>/<PennKey>` | 50 GB，250,000 inodes；每两周快照一次 | https://parcc.upenn.edu/training/storage/ |
| VAST 默认项目 `/vast/projects/<PI-PennKey>/default` | 50 GB，250,000 inodes | 同上 |
| 计算节点本地 `/tmp/$USER` | 约 500 GB，节点内共享，用完要自己拷走并删除 | 同上 |
| 额外 VAST/Ceph 项目空间 | 按申请分配，按 TB·月计费（VAST 补贴价 $7.00，Ceph $2.40） | https://parcc.upenn.edu/about/rates/ |

提醒：AHa-3D 每次运行会产生大量帧和中间文件，**250k 的 inode 上限可能比 50 GB 的容量更早用完**。建议运行时写到 `/tmp/$USER`，结束后打成 tar 包再拷回。

### 1.6 计算节点能不能上网（API 调用、HF 下载都需要）

- 公开文档唯一的线索是 MNIST 教程的排错条目："No MNIST download (egress restricted) → Run a short interactive job to prefetch"，给的命令是 `salloc -p genoa-std-mem` 预先下载。来源：https://parcc.upenn.edu/training/getting-started/zero-to-mnist/
- 这句话暗示至少有些节点限制出网，但没说 GPU 节点能不能访问 huggingface.co 或外部 LLM API【未核实】。
- **建议**：(a) 在登录节点或一个短的 CPU 作业里预先下载好 Pi3X/SAM3 权重（放到 `HF_HOME`），GPU 作业里设 `HF_HUB_OFFLINE=1`；(b) 用 `srun -p b200-mig45 --gpus=1 -t 5 curl -sI https://huggingface.co` 和 `curl -sI <课程 LiteLLM 地址>` 各测一次；(c) 结果不明确就在 Ed #69 下问。

### 1.7 价格，以及 $50 能买多少 GPU 小时

PARCC 的 FY27 费率表（"Valid through 6/30/2027 as of 7/1/2026"），来源：https://parcc.upenn.edu/about/rates/

| 资源 | 补贴价 | 非补贴价 | $50 能买（补贴价） | $50 能买（非补贴价） |
|---|---|---|---|---|
| `betty.b200`（180 GB 整卡） | $1.00/GPU·h | $4.51/GPU·h | 50 h | 11.1 h |
| `betty.b200.mig90`（90 GB 切片） | $0.50/h | $2.25/h | 100 h | 22.2 h |
| `betty.b200.mig45`（45 GB 切片） | $0.25/h | $1.13/h | 200 h | 44.2 h |
| Genoa CPU（标准内存） | $0.010/core·h | $0.028/core·h | 5,000 core·h | 1,786 core·h |

- 费率页说所有费用都 "Direct Billed against an internal Penn Budget Code"，没有提到课程或学生的免费额度。**课程的 $50 按补贴价还是非补贴价计算，公开页面没写**【未核实，问 Lyle】。来源同上。
- 用量只能事后看（课程 README 记录的 Ed #69 原话：硬上限只设在整个课程账户上）。来源：本地课程仓库 `03-final-project/README.md`「算力」一节，原帖 https://edstem.org/us/courses/101036/discussion/8388441 （需要登录）。
- 三个人合计约 $150 的 Betty 额度。**只用来跑感知预处理的话足够**：假设每个场景 Pi3X（64 帧、255k px）+ SAM3 + TSDF 约 0.5 GPU·h【假设，需要试跑测】，20 个场景在 mig45 上约 10 h，补贴价 $2.5、非补贴价 $11；整卡 B200 是 $10 或 $45。

### 1.8 在 Betty 上无界面跑 Blender

- **MIG 切片不能用 Workbench/EEVEE**。NVIDIA MIG 文档写着 "No graphics APIs are supported (for example, OpenGL, Vulkan and so on)"，只有 RTX Pro 6000 Blackwell 例外。来源：https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/deployment-considerations.html
- AHa-3D 的 `clay` 预览默认用 Workbench，`material` 默认用 EEVEE（`src/aha3d/blender/rendering.py` 的 `configure_render`），都需要图形上下文。来源：https://github.com/KevinXu02/aha-3d/blob/82f4b1110cfe4b55fff19df3b3790852ce07b171/src/aha3d/blender/rendering.py
- AHa-3D 的文档说，Blender 5.2.1 在 96 GB RTX PRO 6000 上无界面跑 EEVEE 和 Workbench 都成功了；其他驱动组合还要实测，"If fast engines lack a graphics context, use `--backend cpu` or an explicit Cycles recipe"。来源：https://github.com/KevinXu02/aha-3d/blob/82f4b1110cfe4b55fff19df3b3790852ce07b171/docs/RENDERING.md
- Blender 从 2022 年起在 Linux 后台模式下支持 EGL 无界面 OpenGL（headless 后端）。来源：https://lists.blender.org/pipermail/bf-blender-cvs/2022-August/176810.html 。B200 整卡在 DGX OS 上有没有 EGL/Vulkan、Blender 5.2 的 Cycles 是否原生支持 sm_100，都【未核实】。
- **结论**：Blender 留在本地笔记本上跑，本机之前已经用 Blender 5.2.1 无界面完成过 office48。Betty 只跑感知。真要在 Betty 上渲染，就用 Cycles（CUDA）在 `dgx-b200` 整卡上跑，或者用 CPU 在 genoa 节点上跑。

### 1.9 公开内容和需要登录的内容

- 公开：PARCC 网站上的系统、费率、Logging In、Slurm、Storage、Containers、Software、Tools 各页（上面已经引用）。
- 需要登录：Wharton 的 "PARCC's Betty Cluster Q&A"（https://research-it.wharton.upenn.edu/hpc/parcc/parcc-betty-cluster-qa/ ，页面只显示 "Please login to view this content"），Ed #69 原帖，ColdFront（https://coldfront.parcc.upenn.edu ）。
- **PARCC 的公开站点上没有任何 LiteLLM 页面**。我抓了 sitemap（https://parcc.upenn.edu/page-sitemap.xml ，https://parcc.upenn.edu/training-sitemap.xml ），也搜索了 "parcc.upenn.edu LiteLLM"，都没有。所以课程 LiteLLM 的地址、模型列表、计费方式只能看 Ed 帖子。

### 1.10 建议的分工

```
本地笔记本 (RTX 5070 Ti 12 GB)                    Betty（或 Colab A100）
──────────────────────────────                     ──────────────────────
agent CLI (Codex / Claude Code)                    sbatch: Pi3X(255k px, 64 帧) + SAM3 + TSDF
  └─ 调 API（OpenAI / Anthropic / 课程 LiteLLM）     → 每个场景一个参考包
  └─ Blender 5.2.1 -b（Workbench/EEVEE 预览）        → tar 包 rsync 回本地
  └─ reviewer: codex exec --image
```

这样做可以绕开三个问题：计算节点能否出网、MIG 不支持图形 API、登录节点不许跑重活。感知结果按场景缓存一次，之后所有驱动和变体共用，还能保证不同变体的输入完全一致。

---

## 2. LiteLLM + GLM 5.2

### 2.1 GLM-5.2 基本信息

| 项目 | 内容 | 来源 |
|---|---|---|
| 发布 | Z.ai 发布记录写 2026-06-16；HF 合集 6 月 16 日更新，博客 6 月 17 日 | https://docs.z.ai/release-notes/new-released ，https://huggingface.co/zai-org/GLM-5.2 |
| 规模和许可 | 753B MoE，MIT 许可（HF）；激活参数约 40B 只有第三方说法【未核实】 | https://huggingface.co/zai-org/GLM-5.2 ，https://docs.api.nvidia.com/nim/reference/z-ai-glm-5.2 |
| **输入模态** | **只有文本**："Input Modalities: Text"（Z.ai）；NVIDIA NIM 也说只接受文本 | https://docs.z.ai/guides/llm/glm-5.2 ，https://docs.api.nvidia.com/nim/reference/z-ai-glm-5.2 |
| 上下文 / 最大输出 | 1M / 128K | https://docs.z.ai/guides/llm/glm-5.2 |
| 工具调用 | 支持 Function Call、MCP、结构化 JSON 输出、多种思考模式（`thinking`、`reasoning_effort`） | https://docs.z.ai/guides/llm/glm-5.2 |
| 编码和 agent 基准（厂商自报） | SWE-bench Pro 62.1（GLM-5.1 58.4，Claude Opus 4.8 69.2，GPT-5.5 58.6）；Terminal-Bench 2.1 81.0（Opus 4.8 85，GPT-5.5 84）；MCP-Atlas 76.8；Tool-Decathlon 48.2（Opus 4.8 59.9） | https://huggingface.co/zai-org/GLM-5.2 |
| 官方 API 价格 | 输入 $1.40，缓存命中 $0.26，缓存存储限时免费，输出 $4.40 | https://docs.z.ai/guides/overview/pricing |
| 后续版本 | GLM-5.3（2026-08-18，仍然 text-only，DeepSWE 66.9 对 5.2 的 46.2），GLM-5.3-Flash（2026-08-26，"first native multimodal model in the GLM-5 series"） | https://docs.z.ai/release-notes/new-released ，https://docs.z.ai/guides/llm/glm-5.3 ，https://docs.z.ai/guides/llm/glm-5.3-flash |

几点说明：
- GLM-5.2 对比的都是 Opus 4.8、GPT-5.5 这一代模型，没有和 Opus 5.5、GPT-6 系列比。在编码和 agent 基准上它也落后 Opus 4.8。
- 对缓存很重的 agent 任务，GLM-5.2 并不便宜：它的缓存命中价 $0.26 高于 GPT-6.1 Sol 的 $0.10 和 Sonnet 5.5 的 $0.10（见第 3 节）。

### 2.2 GLM-5.2 不能看图对 AHa-3D 的影响

- AHa-3D 的 reviewer 硬编码为 `codex exec --ephemeral --sandbox read-only --skip-git-repo-check --output-last-message <f> --image <png> ... -`，代码注释写着 "Use the installed Codex image-input CLI, never a path-only review prompt"。`tools/review_images.py` 还会加上 `--output-schema`。来源：https://github.com/KevinXu02/aha-3d/blob/82f4b1110cfe4b55fff19df3b3790852ce07b171/src/aha3d/workflow/review_contract.py ，https://github.com/KevinXu02/aha-3d/blob/82f4b1110cfe4b55fff19df3b3790852ce07b171/tools/review_images.py
- 所以 GLM-5.2 **只能当「看不见图的规划者」**：要么 (a) 配一个看图模型做 reviewer 和视觉检查，要么 (b) 专门作为「无视觉反馈」的消融变体。注意这种消融会把「换模型」和「去掉视觉」两个因素混在一起。更干净的做法是同一个模型分别开关图片输入。
- 如果用 Claude Code 驱动 GLM-5.2，Claude Code 的 Read 工具读 PNG 时会发 image block，经过 LiteLLM 转给 text-only 模型后会报错还是被丢掉【未核实，需要实测】。

**同一家族能看图的模型**（建议请课程在 LiteLLM 上开放）：

| 模型 | 视觉 | 上下文 | 价格（Z.ai 官方） | 其他 | 来源 |
|---|---|---|---|---|---|
| GLM-5.3-Flash | Video/Image/Text/File | 1M | $0.15 / 缓存 $0.03 / 输出 $0.50 | 320B 总参数、18B 激活，MIT 开源权重；DeepSWE 63.4（GLM-5.2 是 46.2）；BVB xhigh 63.96 分，每场景 $0.024 | https://docs.z.ai/guides/llm/glm-5.3-flash ，https://docs.z.ai/guides/overview/pricing ，https://huggingface.co/zai-org/GLM-5.3-Flash ，https://yoloytang.me/BVB/results.csv |
| GLM-5V-Turbo | Video/Image/Text/File | 200K | 官方价格页没有列出（第三方报约 $1.2/$4.0【未核实】） | 文档写 "works seamlessly with agents such as Claude Code"；BVB 56.47 分 | https://docs.z.ai/guides/vlm/glm-5v-turbo ，https://yoloytang.me/BVB/results.csv |
| GLM-4.6V | 是 | — | $0.30 / $0.05 / $0.90 | 较老 | https://docs.z.ai/guides/overview/pricing |

### 2.3 把 agent harness 接到 LiteLLM 代理

LiteLLM 代理对外提供 OpenAI 兼容接口（`/v1/chat/completions`、`/v1/responses`），也提供 Anthropic 兼容的 `/v1/messages`。用户拿到的是一个 base_url 和一个 virtual key（`sk-...`）。

第一步，先确认课程开放了哪些模型、能不能看图、自己花了多少：

```bash
export LITELLM_BASE_URL="https://<Ed #69 给的地址>"   # 不要把 key 写进仓库
export LITELLM_API_KEY="sk-<个人 virtual key>"
curl -s "$LITELLM_BASE_URL/v1/models" -H "Authorization: Bearer $LITELLM_API_KEY"
curl -s "$LITELLM_BASE_URL/model_group/info" -H "Authorization: Bearer $LITELLM_API_KEY"   # 看 supports_vision
curl -s "$LITELLM_BASE_URL/key/info" -H "Authorization: Bearer $LITELLM_API_KEY"          # spend 字段
```

- `/model_group/info` 返回的 `supports_vision` 字段，以及按 OpenAI `image_url` 格式发图片，见 https://docs.litellm.ai/docs/completion/vision
- `/key/info` 返回的 `spend` 以美元计。文档示例用的是 master key，**普通用户能不能用自己的 key 查自己的 spend【未核实】**。来源：https://docs.litellm.ai/docs/proxy/virtual_keys
- LiteLLM 接 Z.ai 时用 `zai/` 前缀和 `ZAI_API_KEY`。不过 LiteLLM 的 Z.ai 页面目前只列到 glm-4.7 和 glm-4.5v，没有 glm-5.2。课程代理可能是自定义映射或别的后端（比如自托管）【未核实】。来源：https://docs.litellm.ai/docs/providers/zai

### 2.4 哪些开源 agent CLI 能接 OpenAI 兼容端点

| CLI | 怎么接 LiteLLM | 看图 | 注意事项 | 来源 |
|---|---|---|---|---|
| **Codex CLI**（AHa-3D 原生） | `~/.codex/config.toml` 里写 `[model_providers.litellm]`，设 `base_url="<proxy>/v1"`、`env_key="LITELLM_API_KEY"`、**`wire_api="responses"`**；顶层设 `model_provider="litellm"`、`model="<proxy 里的 model_name>"` | `codex exec --image` 会把图发出去；能不能经 LiteLLM 的 `/v1/responses` 正确转给非 OpenAI 模型【未核实】 | Chat Completions 线路（`wire_api="chat"`）已经在 2026-02 移除，第三方来源说法一致，官方 changelog 没找到；不认识的模型名会用 fallback 元数据，没有 reasoning-effort 选项；`openai`、`ollama`、`lmstudio` 是保留 ID | https://docs.litellm.ai/docs/proxy/client_setup/codex_cli ，https://learn.chatgpt.com/docs/config-file/config-advanced ，https://openrouter.ai/blog/tutorials/codex-cli-openrouter/ |
| **Claude Code** | `ANTHROPIC_BASE_URL=<proxy>`，`ANTHROPIC_AUTH_TOKEN=<virtual key>`，`claude --model <model_name>`；LiteLLM 负责在 `/v1/messages` 和各家格式之间转换 | 取决于后端模型 | 可选 `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`（要求 v2.1.129+），`/model` 选单里只保留 id 含 claude/anthropic 的模型，但 `--model` 可以直接写任意名字；base URL 不是 Anthropic 官方地址时，Claude Code 会关掉 tool search，需要设 `ENABLE_TOOL_SEARCH=true` | https://docs.litellm.ai/docs/tutorials/claude_non_anthropic_models ，https://docs.litellm.ai/docs/tutorials/claude_responses_api |
| Claude Code 直连 Z.ai | `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`（需要 Z.ai 自己的 key，不是课程的 LiteLLM key） | — | Z.ai 文档默认映射的已经是 glm-5.3 / glm-5.3-flash | https://docs.z.ai/devpack/tool/claude |
| **OpenHands** | 模型写 `litellm_proxy/<model>`，再填 Base URL 和 API Key；无界面运行用 `openhands --headless -t "<task>"`（headless 模式总是 always-approve） | 文档没写 | 内部本来就用 LiteLLM | https://docs.openhands.dev/openhands/usage/llms/litellm-proxy ，https://docs.openhands.dev/openhands/usage/run-openhands/headless-mode |
| opencode | `opencode.json` 里用 `@ai-sdk/openai-compatible` 加 `baseURL` 和 `apiKey`；`/v1/responses` 端点改用 `@ai-sdk/openai` | 文档没写 | — | https://opencode.ai/docs/providers/ |

**OpenAI 模型走 LiteLLM 的坑**：GPT-6 Luna 在 Chat Completions 下 "supports function calling only with `reasoning_effort` set to `none`"；gpt-6.1-sol 的 Chat Completions "works but without tool calling"。所以 GPT 系列应该让 Codex 直连 OpenAI 的 Responses API，不要走「Claude Code → LiteLLM → chat completions」这条路。来源：https://developers.openai.com/api/docs/models/gpt-6-luna ，https://developers.openai.com/api/docs/models/gpt-6.1-sol

**对 AHa-3D 的建议**：不管驱动换成什么模型，**reviewer 都固定成同一个看图模型**，比如 Codex + GPT-6.1 Sol 或 GPT-6 Luna。这样不同驱动之间的差别不会掺进评审标准的差别。reviewer 调用次数少，花费不大。如果用 Claude 驱动，可以继续用本机之前写的 `codex` shim，或者直接装 Codex CLI。

---

## 3. 驱动模型对比

### 3.1 估算假设

- 每个房间：**10M 缓存命中输入 token + 0.25M 其他 token**（你们给的口径）。「其他 token」怎么分会让总价差很多，所以给三档：
  - **低**：0.25M 全部是未缓存输入。
  - **中**：0.10M 缓存写入（按各家缓存写入价）+ 0.15M 输出。
  - **高**：0.25M 全部是输出。
- 检验：GPT-6 Astra 按这个口径算出 $12.5–22.5，和作者估计的 $12–22 一致，说明作者的估计就是这么来的。
- 统一按标准档、短上下文的价格计算。OpenAI 单次请求超过 272K 输入时，输入和缓存价 ×2、输出 ×1.5（https://developers.openai.com/api/docs/models/gpt-6-astra ）。**Haiku 5.5 单次请求超过 100K token 时所有单价 ×5**（https://platform.claude.com/docs/en/about-claude/pricing ）。agent 会话的上下文很容易超过 100K，所以 Haiku 两档都列出来。
- 另给一个「**BVB 比例法**」做交叉检验：用 BVB 排行榜上「该模型每场景花费 ÷ 同档 Astra 每场景花费」乘以 Astra 的 $12.5–22.5。这个方法能反映不同模型话多话少、轮数多少的差别，但 BVB 的任务比 AHa-3D 短得多，只能当参考。
- 图片按输入 token 计。例如 Claude 按 28×28 patch 计费，1280×720 的图约 46×26 = 1,196 token（https://platform.claude.com/docs/en/build-with-claude/vision ）。

### 3.2 对比表

| 驱动 | 看图 | 输入 / 缓存命中 / 输出（/M） | 每房间：低–中–高 | BVB 比例法 | 3D、空间、agent 编码方面的公开证据 |
|---|---|---|---|---|---|
| **GPT-6 Astra** | 是（text+image） | $10 / $1.00 / $50（缓存写入 $12.5） | **$12.5 – 18.8 – 22.5** | 基准 | AHa-3D 作者用的驱动；Agentic RSR v1 表 4 / v2 附录表 9（Codex harness）18/18，5.6 Sol 是 10/18；v2 表 3（DSH harness）15/18；BVB xhigh **73.82**（第 1），$1.72/场景，22.4 min |
| **GPT-6.1 Sol** | 是 | $2 / $0.10 / $10（写入 $2.5） | **$1.5 – 2.75 – 3.5** | $3.6–6.6 | OpenAI 的描述是 "Near-Astra performance … at a lower cost"；BVB xhigh **73.29**（第 2），$0.50/场景；Agentic RSR v2 表 3 是 12/18 |
| **GPT-6 Luna** | 是 | $0.10 / $0.01 / $0.50（写入 $0.125） | **$0.13 – 0.19 – 0.23** | $0.08–0.14 | BVB xhigh **68.11**（第 8），只要 $0.011/场景、2.6 min；在 AHa-3D 这种长任务上没有证据 |
| **Claude Opus 5.5** | 是 | $4 / $0.20 / $20（5 分钟写入 $5） | **$3.0 – 5.5 – 7.0** | high：$4.9–8.8；xhigh：$14–26 | **Agentic RSR v2 表 3 是 18/18，所有配置里 Lab 和 SSIM 最好**；AHa-3D README 说 "Opus 5.5 can also drive this repository … not been fully tested"；BVB xhigh 69.83，high 65.73 |
| **Claude Sonnet 5.5** | 是 | $2 / $0.10 / $10（写入 $2.5） | **$1.5 – 2.75 – 3.5** | xhigh：$8.6–15.5 | Agentic RSR v2 是 15/18；BVB xhigh 69.84，$1.18/场景 |
| **Claude Haiku 5.5** | 是 | ≤100K：$0.10 / $0.01 / $0.50；>100K：$0.50 / $0.05 / $2.50 | ≤100K：$0.13–0.19–0.23；>100K：$0.63–0.94–1.13 | $0.20–0.35 | **本机实测 office48：5.7 min、67 轮、约 $0.56（按 API 价折算），结果粗糙（159 个物体，作者是 401）**；BVB xhigh 65.92，$0.027 |
| **GLM-5.2** | **否（text-only）** | $1.40 / $0.26 / $4.40 | $2.95 – 3.40 – 3.70（按 Z.ai 官方价；课程 LiteLLM 的实际计价【未核实】） | 不在 BVB 上 | 只有厂商自报：SWE-bench Pro 62.1，Terminal-Bench 2.1 81.0（都低于 Opus 4.8）；**不能完成看图环节** |
| GLM-5.3-Flash（开源权重） | 是 | $0.15 / $0.03 / $0.50 | $0.34 – 0.39 – 0.43 | $0.17–0.31 | BVB xhigh 63.96，$0.024/场景；厂商自报 DeepSWE 63.4 |
| Kimi K3（开源权重） | 是（HF 卡写 "Text, Image"） | $3.00 / $0.30 / $15（写入 $3） | $3.75 – 5.55 – 6.75 | 不在 BVB 主榜 | **Agentic RSR v2 是 0/18**（"neither model completes the tool interactions required"）；厂商自报 Terminal-Bench 2.1 88.3；2.8T 参数，自托管不现实 |
| Qwen3.6-27B（开源，可自托管） | 是 | 自托管按 GPU 时计费 | Betty mig90 跑 0.5–1 h，补贴价约 $0.25–0.5【假设】 | — | 厂商自报 SWE-bench Verified 77.2、ERQA 62.5；同系列在 BVB 垫底（Qwen3.5-27B 47.50，Qwen3.6-Plus 51.28）；Apache-2.0，BF16 权重约 55 GB |

价格来源：
- OpenAI：https://developers.openai.com/api/docs/pricing ，以及各模型页 https://developers.openai.com/api/docs/models/gpt-6-astra 、https://developers.openai.com/api/docs/models/gpt-6.1-sol 、https://developers.openai.com/api/docs/models/gpt-6-luna 。三个模型都是 text+image 输入，1.05M 上下文，128K 最大输出。
- Anthropic：https://platform.claude.com/docs/en/about-claude/pricing 。Opus 5.5 和 Sonnet 5.5 的缓存命中只收 0.05× 基础价。模型总览说 "All current models support text and image input"，见 https://platform.claude.com/docs/en/about-claude/models/overview
- Z.ai：https://docs.z.ai/guides/overview/pricing
- Moonshot：https://platform.kimi.ai/docs/pricing/chat 。模态见 https://huggingface.co/moonshotai/Kimi-K3
- Qwen：https://huggingface.co/Qwen/Qwen3.6-27B
- Betty 价格：https://parcc.upenn.edu/about/rates/

证据来源：
- Agentic RSR：https://arxiv.org/abs/2610.10479 （v1 表 4：https://arxiv.org/html/2610.10479v1 ；v2 表 3 和附录表 8/9：https://arxiv.org/html/2610.10479v2 ）
- BVB：https://yoloytang.me/BVB/results.csv （页面标注 "Leaderboard updated October 13, 2026"，https://yoloytang.me/BVB/ ），论文 https://arxiv.org/abs/2609.15478
- AHa-3D README：https://github.com/KevinXu02/aha-3d
- 本机 Haiku 实测：用户记忆文件 video2sim-align-workspace

### 3.3 公开证据的要点和局限

1. **Agentic RSR 的两个版本结论不同**。
   - v1（2026-10-07）表 4 是 Codex harness 下的消融：完整系统（GPT-6 Astra）18/18，换成 GPT-5.6 Sol（high）后是 10/18，Depth MAE 从 0.1057 m 涨到 0.2119 m。
   - v2（2026-10-11）把主配置换成 Claude Opus 5.5 + DeepSeek Harness（DSH），新加的表 3 是：Opus 5.5 18/18（Lab 8.01、SSIM 0.734 都是最好），Fable 5.1 18/18（Depth MAE 0.0733 最好），Astra 15/18，Sonnet 5.5 15/18，GPT-6.1 Sol 12/18，GPT-5.6 Sol 4/18，Kimi K3 和 DeepSeek V4.1 Flash 都是 0/18。
   - 作者自己也说 "These outcomes describe performance within the evaluated workflow rather than a general model ranking"，而且 harness 和轮数预算不同，"do not isolate model or harness effects"。
   - 对我们的启发：**harness 和模型是绑在一起的**。Astra 在 Codex 原生 harness 里是 18/18，在 DSH 里是 15/18。AHa-3D 是为 Codex 写的，所以 GPT 系列在 AHa-3D 里可能比在 DSH 里表现更好【推断】。来源：https://arxiv.org/html/2610.10479v2
   - 作者还观察到 Codex + GPT-6 Astra 在不同设备、不同调用方式、不同时间下行为有差别。来源同上。这也说明需要 2 个种子。
2. **BVB 和我们的任务最接近**：从室内视频出发，在 Blender 里写 Python 重建场景。但 agent 看不到自己的渲染结果，任务也短得多，每场景几分钟、几毛钱；AHa-3D 是多小时、几十轮的长任务。它的排序可以参考，花费不能直接照搬。前几名几乎都是 OpenAI 的模型，**GPT-6.1 Sol 用 Astra 约 29% 的价钱拿到了 99% 的分数**。来源：https://yoloytang.me/BVB/results.csv
3. **便宜模型在长任务上可能撑不住**。本机 Haiku 5.5 在 office48 上很快就结束了，结果粗糙，验收在第一道关就没过。BVB 上 Haiku 5.5 xhigh 有 65.92 分，并不差。这说明 AHa-3D 这种长任务对模型的持续执行和自检能力要求更高，**不能拿 BVB 分数直接推断 AHa-3D 的质量**。必须先在 office48 上做对照试跑。

---

## 4. 推荐和预算

### 4.1 各阶段用哪个驱动

| 用途 | 首选 | 备选 | 理由 |
|---|---|---|---|
| (i) 开发迭代：调脚本、调 prompt、跑通流程 | **GPT-6 Luna + Codex CLI**（直连 OpenAI，reasoning 设 high 或 xhigh） | Claude Haiku 5.5 + Claude Code（本机已经跑通） | Luna 用的就是 AHa-3D 原生的 Codex harness，`codex exec --image` reviewer 不用改；每次约 $0.1–0.25；BVB 上比 Haiku 5.5 分数高、价格低 |
| (ii) 主实验 | **GPT-6.1 Sol + Codex CLI**（xhigh） | Claude Opus 5.5 + Claude Code（high） | Sol 和作者的 harness、厂商都一致；BVB 上接近 Astra；token 等量法约 $1.5–3.5/次，BVB 比例法约 $3.6–6.6/次。Opus 5.5 在 Agentic RSR v2 的 Blender 精修任务上最强（18/18），但 AHa-3D 只做过初步测试，xhigh 的花费可能和 Astra 差不多，适合在部分场景上做跨厂商对照 |
| 锚点 | **GPT-6 Astra**，2–3 次（含 office48） | — | 对齐作者设置，证明我们的流水线没有走样；每次 $12.5–22.5 |
| (iii) 便宜消融 | **GPT-6 Luna**（同一 harness，只改变量） | 课程 LiteLLM 上的 GLM：GLM-5.3-Flash（如果开放）可以当「开源权重驱动」变体；**GLM-5.2 只能当「无视觉」变体** | Luna 跑 120 次约 $15–27；GLM 走课程额度，不花自己的钱 |

**先做一次试跑（约 $30）**：office48 上 Luna、Sol、Astra 各跑一次。用 Codex 的 usage 输出和 OpenAI 用量页记下实际 token 数，然后用实测 token 替换上面「10M + 0.25M」的假设，再决定主实验用 Sol 还是 Luna。

### 4.2 预算：20 个测试场景 × 3 变体 × 2 种子 = 120 次

| 方案 | 构成 | API 花费（自己出钱） | 课程 LiteLLM | Betty |
|---|---|---|---|---|
| **A. 省钱版** | 开发：Luna 约 60 次（约 $15）；主实验：**Luna 120 次**（$15–27）；强驱动复核：Sol 跑 20 场景 × 完整方法 × 1 种子（$30–130）；Astra 锚点 2 次（$25–45） | **约 $85–220** | GLM 消融 | 感知 $3–45 |
| **B. 标准版（推荐）** | 开发 Luna（约 $15）；主实验 **Sol 120 次**（$180–420 token 等量；BVB 比例法 $440–790）；Astra 锚点 3 次（$38–68）；消融 Luna 120 次（$15–27） | **约 $250–900，中位约 $450** | GLM 消融 | 感知 $3–45 |
| C. 照搬作者 | 主实验 **Astra 120 次** | **$1,500–2,700** | — | — |
| 参考：Opus 5.5 当主驱动 | 120 次 | token 等量法 $360–840；BVB 比例法 high 约 $590–1,060，xhigh 约 $1,700–3,100 | — | — |

- **课程 LiteLLM 额度**（三人合计约 $150）：GLM-5.2 按官方价每次约 $3.4，只够约 44 次，所以只适合 20 场景 × 1 种子的「无视觉」变体（约 $68）。GLM-5.3-Flash 每次约 $0.39，够约 380 次。前提是课程按 Z.ai 官方价计费，这一点【未核实】。
- **Betty 额度**（三人合计约 $150）：用来跑 20 个测试场景的默认分辨率感知，加上调试，每场景按 0.5 GPU·h 假设，补贴价 mig45 不到 $5，非补贴价整卡不到 $50。**额度很充裕**。多出来的可以用来自托管 Qwen3.6-27B 做「全开源」变体（可选，工程量大，而且 BVB 上同系列很弱）。
- 如果预算吃紧，**先砍种子，别砍场景**：主实验每个变体先跑 1 个种子，第 2 个种子只补在结论关键的那一组对比上。

### 4.3 控制花销

1. 课程的硬上限是整个课程账户共用的，个人超支只能事后看到。所以每次运行都要把 token 用量写进日志。LiteLLM 那边用 `/key/info` 查；OpenAI 和 Anthropic 用各自控制台的用量页。
2. Haiku 5.5 超过 100K 后单价 ×5，GPT-6 系列超过 272K 后输入 ×2。agent 的上下文要压缩：Claude Code 有 `CLAUDE_CODE_AUTO_COMPACT_WINDOW`（https://docs.litellm.ai/docs/tutorials/claude_non_anthropic_models ，https://docs.z.ai/devpack/tool/claude ），设成 100000 能否把 Haiku 稳定压在低价档【未核实】。
3. 旧图片尽量换成文字摘要，或者降低预览分辨率。在 Claude 上，1280×720 一张约 1.2K token，几十轮重复带上就是可观的缓存读量。
4. 感知结果按场景缓存一次，所有驱动共用，避免重复花 GPU 时间。

---

## 5. 未核实、待确认清单

| # | 问题 | 怎么确认 |
|---|---|---|
| 1 | 课程 LiteLLM 的地址、开放了哪些模型、有没有看图模型、按什么价格计费 | Ed #69；`/v1/models`、`/model_group/info` |
| 2 | Betty 的 $50 按补贴价还是非补贴价计费 | 问 Lyle 或 PARCC |
| 3 | GPU 节点能不能访问外网（HF、OpenAI、LiteLLM） | 在 `srun` 作业里 `curl -sI` 测 |
| 4 | Apptainer 有没有装；有没有 Open OnDemand | `which apptainer`；问 PARCC |
| 5 | B200 整卡上 Blender 能不能用 EGL/Workbench/EEVEE；Cycles 支不支持 sm_100 | 在 `dgx-b200` 上用 `blender -b` 渲一帧测试 |
| 6 | Pi3X 用 255k px、64 帧在 mig45 上会不会 OOM，每个场景要多少 GPU 时间 | 在 mig45 上试一个场景 |
| 7 | Codex 走 LiteLLM `/v1/responses` 时，`--image` 和 `--output-schema` 能不能正确转给 GLM | 实测 |
| 8 | Claude Code 驱动 text-only 的 GLM-5.2 读 PNG 时会怎样 | 实测 |
| 9 | GLM-5.2 激活参数约 40B，以及 GPT-6 Astra 的发布日期 | 只有第三方来源（https://rits.shanghai.nyu.edu/ai/glm-5-2-z-ais-open-weights-coder-beats-gpt-5-5-at-1-6-the-cost/ ，https://blog.neural4d.com/?p=3540 ） |
| 10 | 各模型在 AHa-3D 上的实际 token 量（本文用的是统一的 10M + 0.25M 假设） | office48 试跑 |
