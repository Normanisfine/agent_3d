# 课程算力怎么用：Betty GPU 集群和 LiteLLM

2026-10-22 整理。依据：Ed 第 69、77 帖原文（10-22 用 Ed API 读过）、PARCC 公开文档（https://parcc.upenn.edu/training/getting-started/ 及其子页）、`research/notes/04-compute-drivers.md`。**本文的脚本还没在 Betty 上实测过**，第一次跑通后请回来改正。

## 课程给了什么

- 10 月 13 日起，全班开通了 Penn 新的计算集群 **PARCC**，包括两样东西：
  - **Betty**：GPU 集群，NVIDIA B200（单卡 180 GB），也能按 45 GB、90 GB 的切片（MIG）申请；
  - **LiteLLM**：一个大模型 API 代理，帖子里举的例子是 GLM 5.2。
- 每人大约各 50 美元额度。**硬上限只设在整个课程账户上**，个人用量只能事后看报告，所以要自己控制花销。

## Ed 上的最新情况（10-22 读过原文）

- **第 69 帖（老师，10/13）**：大家应该都能用 LiteLLM（GLM 5.2）和 Betty，各约 50 美元；老师自己也还没测过，文档有限，有问题在帖子下问。**帖子没有给 LiteLLM 的地址和 key**，目前也没有回复。
- **第 77 帖（10/19–10/21）**：有同学能 SSH 进 Betty，但 `sacctmgr show user $USER withassoc` 看不到账户关联，交不了作业。助教 Sashank 10/21 回复已修好，现在可以提交作业。老师补充：**大一点的作业可能要排队 1–2 天才开始跑**，所以要早提交、拆成小作业（我们每个场景一个短作业，用 mig45 小卡）。

## 我们拿它做什么

| 用途 | 用 Betty 还是笔记本 | 为什么 |
|---|---|---|
| Pi3X + SAM 3 感知（20 个场景，作者默认 25.5 万像素） | **Betty** | 笔记本 12 GB 只能跑 10 万像素；B200 切片 45 GB 足够 |
| Boxer 清单、干净对照（第二阶段） | **Betty** | 批量 |
| SAM 3D Objects 生成（第二阶段） | **Betty** | 官方要 32 GB 显存 |
| agent 运行、Blender 渲染和物理检查 | 笔记本 | MIG 切片不支持 OpenGL/Vulkan；agent 要用我们的订阅 |
| 驱动 agent 的大模型 | 订阅（Codex、Claude） | 课程 LiteLLM 上的 GLM 5.2 只能读文本、看不了图，不能单独驱动 agent |

**花费估算**：感知一个场景在 B200 切片上约 1–2 分钟；20 个场景不到 1 小时。mig45 补贴价每小时 0.25 美元（非补贴价 1.13 美元），所以只要几美元。SAM 3D 约 13 秒一个物体，1,000 个物体约 4 小时，也是几美元。50 美元的额度足够，大头留给第二阶段的生成和可选的训练加分项。

## Yifan 的笔记本（10-27 核对过）

- 这台笔记本不在 Penn 网内（直连 Betty 的 22 端口不通），要先连 VPN。VPN 入口是 `vpn.upenn.edu`，用浏览器单点登录（PennKey + Duo）。
- 本机缺 `kinit` 和 VPN 客户端：运行一次 `bash scripts/betty/login_setup.sh`（要 sudo），会装 `krb5-user`（realm 设好 UPENN.EDU，KDC 由 DNS 自动找到）和开源的 GlobalProtect 客户端。
- `~/.ssh/config` 已经配好 `Host betty`（PennKey 按 Ed 上的邮箱推断为 `hu5`），打开了 Kerberos、DNS 核对主机指纹、连接复用（登录一次保持 10 小时）。
- 官网公布的登录节点指纹：`SHA256:gQPU5K0JY7/0gTwEmQG9dCF+eCrfqqEXvbDzmVzJZ3c`、`SHA256:rFIuRhUoQP+YApM/qvY1D/EOmxccqGEcOX9rFcOiO6s`、`SHA256:talnzpFHiLmQR0xFrC8ZaPdQ9LxfDMb/iamK2pbBd7I`。
- 顺序：连 VPN → `kinit hu5@UPENN.EDU` → `ssh betty`（手机上确认 Duo）。连上之后，同一台机器上的其他 ssh/rsync 都复用这条连接。

## 10-27 第一次实际登录后核实的事

- **登录方式**：`sudo -E gpclient connect vpn.upenn.edu` 连 VPN（不加 sudo 会因为建不了虚拟网卡而失败），`kinit hu5@UPENN.EDU`，`ssh betty`，手机批准 Duo。之后本机公钥已加到 Betty，以后用"密钥 + Duo"登录，不用再 kinit。
- **账户**：Slurm 账户 `zives-cis-academic-curri`（PI 账户 `pi-zives`），可用 QOS 为 dgx、genoa-lrg、genoa-std、mig、normal，可以提交作业。home 是 `/vast/home/h/hu5`，配额 50 GB / 25 万个文件。
- **作业过滤器（2026-08-03 起强制）**：资源必须按比例申请。
  - GPU 分区只写 `--gpus=N`，CPU 和内存由过滤器自动补：dgx-b200 每 GPU 28 个 CPU，mig90 14 个，mig45 6 个，每 CPU 8 GB。
  - genoa-std-mem 不要写 `--mem`，或者写成 5632M 的整数倍。
  - 说明：https://docs.parcc.upenn.edu/docs/notes/filter.html （要在 VPN 内）。
- **计算节点能上网**：在 genoa-std-mem 上测过，pypi 和 Hugging Face 都通，所以装环境用 CPU 批处理作业，不占登录节点。
- **非登录 shell 里没有 `module`、`squeue`**：从笔记本 `ssh betty '...'` 或批处理作业里，要用 `bash -l` 或先 `source /etc/profile`。
- **有的模块**：anaconda3/2023.09-0、miniconda3/25.5.1、python/3.11.11 等。
- **10-27 凌晨的空闲 GPU**：mig45 0/32、mig90 3/16、整卡 5/216，mig45 可能要排队。

## 第一次登录（每个人都要做一次）

1. **连 Penn 的 GlobalProtect VPN**（在校园网内可以省略）。
2. **确认已经开通 Penn 两步验证（Duo）。**
3. 登录。Betty 要求三种认证里任选两种：Kerberos、SSH 密钥、Duo。最简单的是 Kerberos 加 Duo：
   ```bash
   conda deactivate                      # 本机有 conda 环境时要先退出，否则 kinit 会失败
   kinit <PennKey>@UPENN.EDU             # UPENN.EDU 必须大写；票据 10 小时后过期，要重新 kinit
   ssh <PennKey>@login.betty.parcc.upenn.edu
   ```
   然后按 Duo 的提示确认。第一次登录时，核对主机指纹和官网公布的一致再接受。
4. **（推荐）配 SSH 密钥和连接复用**，之后 rsync 不用每次都过 Duo。在本机 `~/.ssh/config` 加：
   ```
   Host *.parcc.upenn.edu
       VerifyHostKeyDNS yes
       GSSAPIAuthentication yes
       ControlMaster auto
       ControlPath ~/.ssh/control:%h:%p:%r
   ```
   再运行 `ssh-keygen -t ed25519` 和 `ssh-copy-id <PennKey>@login.betty.parcc.upenn.edu`；开一个后台主连接 `ssh -fNM <PennKey>@login.betty.parcc.upenn.edu`，之后的 ssh 和 rsync 都复用它。
5. **看自己有没有被加进课程的项目**（能不能提交作业，取决于有没有 Slurm 账户关联）：
   ```bash
   sacctmgr show assoc user=$USER format=account,partition,qos   # 能看到课程的 account 就说明开通了
   parcc_sfree.py      # 现在哪些 GPU 空着
   parcc_sqos.py       # 自己的作业时长、GPU 数上限
   parcc_quota.py      # home 用了多少空间和文件数
   parcc_sreport.py    # 自己花了多少（事后报告）
   ```
   如果 `sacctmgr` 里没有课程的 account，`sbatch` 会报错。这时在 Ed 第 69 帖下面问，或者让老师在 ColdFront 里把你加进课程项目（新加的成员最多要一小时才生效）。

## 要知道的限制

- **集群只支持 CUDA 12.8。** AHa-3D 的环境用的正好是 torch 2.7.1+cu128，可以直接用。
- **计算节点上网受限。** 下载权重、`pip install` 都在登录节点或者 CPU 交互作业（`salloc -p genoa-std-mem`）里做；GPU 作业里设 `HF_HUB_OFFLINE=1`。
- **home 目录上限是 50 GB、25 万个文件。** AHa-3D 的三套环境约 15 GB、7.5 万个文件，加上权重约 24 GB。作业中间结果写到计算节点本地的 `/tmp/$USER`，跑完再拷回 home。
- **登录节点只用来编辑、同步、提交作业**，不要在上面跑模型。
- **分区**：`dgx-b200`（整卡）、`b200-mig90`、`b200-mig45`（切片）、`genoa-std-mem`（CPU）。感知用 `b200-mig45` 就够，最便宜。

## 我们的流程（10-27 起由 Yifan 开户，Claude 在 Yifan 登录后接着装环境；脚本在 `scripts/betty/`）

1. **装环境（一次）**：在 Betty 上开一个 CPU 交互作业，运行安装脚本：
   ```bash
   salloc -p genoa-std-mem --cpus-per-task=8 --mem=32G -t 2:00:00
   bash ~/smallobj/scripts/betty/setup_betty.sh    # 克隆 AHa-3D（固定 82f4b11）并安装 static 级的三套环境
   ```
   脚本本身要先推上去，见第 2 步。第一次可以先只推脚本：`bash scripts/betty/push.sh <PennKey> 45261575`。
2. **从笔记本推数据和权重**：
   ```bash
   bash scripts/betty/push.sh <PennKey> --weights      # 第一次带 --weights（约 8.4 GB）
   bash scripts/betty/push.sh <PennKey>                # 以后只推场景视频（20 个开发和测试场景）
   ```
   权重直接从笔记本拷过去，就不用在 Betty 上登录 Hugging Face，SAM 3 的权限也不受影响。
3. **检查 GPU**：
   ```bash
   srun -p b200-mig45 --gpus=1 -t 5 ~/smallobj/aha-3d/.runtime/pi3x-inference/venv/bin/python -c 'import torch;print(torch.cuda.get_device_name(0))'
   ```
4. **批量算感知**：
   ```bash
   cd ~/smallobj && sbatch --array=1-20 scripts/betty/reference.sbatch
   squeue -u $USER                 # 看排队和运行
   tail -f logs/ref-<作业号>_1.out  # 看日志
   ```
5. **拉回笔记本**：`bash scripts/betty/pull.sh <PennKey>`，结果放在 `perception_betty/<场景>/bundle`。笔记本上原来 10 万像素的结果不会被覆盖。正式实验换用这份结果之前，先用 `align.pipeline_to_gt` 检查对齐残差。
6. **记账**：每周跑一次 `parcc_sreport.py`，把花费记进 `results/compute_log.md`。

## LiteLLM

**还没有公开的接入方式**：第 69 帖只说有 LiteLLM，没给地址和 key（10-22 核实）。需要在第 69 帖下问老师或助教，或者等 PARCC 文档更新。要拿到的是：

- 接口地址（base URL）；
- 每人的 API key 怎么领；
- 能用哪些模型。

拿到之后，先查有没有能看图的模型：

```bash
export LITELLM_BASE=<帖子里的地址>   # 例如 https://…/v1
export LITELLM_KEY=<你的 key>        # 不要写进仓库
curl -s $LITELLM_BASE/models -H "Authorization: Bearer $LITELLM_KEY" | python3 -m json.tool
```

**对我们项目的用处**：

- **GLM 5.2 只能读文本、不能看图**（Z.ai、NVIDIA、Hugging Face 三处的说明一致），所以不能单独驱动 AHa-3D。AHa-3D 每一轮都要看叠加图和渲染图。
- **如果列表里有能看图的模型**（比如同一家族的 GLM-5.3-Flash 或 GLM-5V），可以当"便宜驱动"做一个消融实验：
  - Codex CLI 用自定义 provider 接 LiteLLM，`wire_api="responses"`；
  - Claude Code 设 `ANTHROPIC_BASE_URL` 接 LiteLLM 的 Anthropic 兼容接口。
  
  两种接法都要先在 office48 上试一次。
- **只用文本也能干的活**：给 CA-1M 里写着 "object" 的框补类别名、批量写图注、汇总日志等。用 OpenAI 兼容的 Python 客户端就行：
  ```python
  from openai import OpenAI
  client = OpenAI(base_url=os.environ["LITELLM_BASE"], api_key=os.environ["LITELLM_KEY"])
  client.chat.completions.create(model="glm-5.2", messages=[{"role": "user", "content": "..."}])
  ```
- **花销**：GLM 5.2 官方价格是每百万 token 输入 1.40 美元、缓存 0.26 美元、输出 4.40 美元。课程账户的计价方式要看帖子说明。

## 还没确认的事

- 课程的 50 美元按补贴价还是非补贴价计费（差 4.5 倍）。
- 排队时间：老师说大作业可能等 1–2 天；mig45 小作业要等多久，第一次提交时记下来。
- GPU 计算节点到底能不能访问外网（文档只写了 "egress restricted"）。
- B200（sm_100）上 torch 2.7.1+cu128 的 Pi3X 和 SAM 3 能不能直接跑（大概率可以，第 3 步会验证）。
- LiteLLM 的地址、key 和模型列表（第 69 帖没写，要去问）。
