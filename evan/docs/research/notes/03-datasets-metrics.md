# 03 评测数据集与指标：小物体 / 难建模物体 / 大家具（截至 2026-10-14）

> 适用项目：单目房间视频 → 物体级 Blender 场景（基于 AHa-3D，难建模物体走 Hunyuan3D 类 image-to-3D）。
> 标记约定：没有特别标注的事实，都读过所给链接的原文、代码或数据文件。**【推断】**是我的推算，**【未核实】**是没找到一手来源。
> 「本次实测」指我在 2026-10-14 用 `python3 -I` 解析小型元数据文件（没有下载任何数据集本体）得到的数字，方法在对应位置注明。
> 前情（只读笔记）：`03-final-project/agentic-3d/notes/landscape-benchmarks-eval.json` 已经覆盖 BVB、VSI-Bench、ARKitScenes 17 类、ScanNet/ScanNet++ 申请流程、HARMONY300、SceneActBench 等。本文只补新的事实，不重复。

---

## 0. 结论先行

1. **原计划的 ARKitScenes/BVB-150 测不出小物体改进。** VSI-Bench 公开的 meta_info 里有这 150 个视频的 GT 框，共 854 个，最长边 < 0.5 m 的只有 42 个（4.9%），< 0.2 m 的一个都没有，而且这 42 个是凳子和电视（本次实测，数据见 https://github.com/vision-x-nyu/thinking-in-space/tree/main/data/meta_info ）。ARKitScenes 的 17 个类里本来就没有小物体（https://github.com/apple/ARKitScenes/blob/main/threedod/benchmark_scripts/utils/taxonomy.py ）。
2. **小物体定量评测（i），首选 ScanNet++ v2，CA-1M 作零等待的补充。**
   - ScanNet++ v2：真实手持 iPhone 视频 + 激光 mesh 上的稠密实例标注，84 个实例类里有 cup、book、monitor、table lamp、plant 等。BVB/VSI-Bench 的 50 个 ScanNet++ 场景都来自验证集，BVB 已有现成基线产物。缺点是要导师手签申请，审批约 4–7 天，2026 年 9 月服务器不稳定。
   - CA-1M（Apple，Cubify Anything）：不用申请，curl 直接下载。它对 ARKitScenes 视频做了穷举式、无类别的 3D 框标注，每个视频约 125 个框。和 BVB-150 有 27 个视频重叠，去掉覆盖不全的 5 个后剩 22 个可用。
3. **大家具和前人对比（ii），用 ARKitScenes 的 BVB-150。** 取 50 个测试场景，其中包含上面 22 个 CA-1M 重叠视频，这样同一批视频能同时测大家具（17 类有向框）和小物体（CA-1M 穷举框）。BVB-results 里各配置的 .blend 可以直接当基线重新打分。
4. **指标**：按 GT 有向框最长边分档，XS<0.2 m、S<0.5 m、M 0.5–1.5 m、L≥1.5 m。匹配同时报两套：IoU3D≥0.25（和前人可比），以及按尺寸归一化的中心距离（小物体上更稳）。每个 GT 物体归入三类之一：放对 / 检出但放错 / 没检出。形状用逐物体 Chamfer 和 F@5%·对角线。对齐用相机轨迹做 Sim(3) Umeyama，同时报不估尺度的 SE(3) 版本。**我没找到任何室内物体级重建论文按物体尺寸分档报 3D 指标**，最接近的是 DSPDet3D 的 0.05 m³ 类别级定义和 COCO 的 2D 面积档，所以分档阈值要在报告里写明是我们自己定义的。
5. **可选**：ReplicaCAD 在 Blender 里渲染受控视频，用来给 Hunyuan3D 物体测形状（GT 完美，132 MB，CC-BY-4.0）。ADT 的小物体 mesh 真值最好，但只有一套公寓，而且许可禁止公开展示衍生作品，只适合做补充。

---

## 1. 候选数据集逐个看

### 1.1 总表

| 数据集 | 随手拍的手持 RGB 视频？ | GT 类型 | 小物体覆盖（每景约多少） | 许可 / 获取 / 等待 | 约 20 个场景的下载量 | 逐物体 GT 框工具 |
|---|---|---|---|---|---|---|
| ARKitScenes 3DOD | 有。iPad .mov，1920×1440 HEVC 60 fps [A3] | 17 类有向框（z-up，基本只有 yaw）[A1][A2] | 几乎没有：最小框最长边 0.30 m [A2]；VSI-150 的 854 个框里 <0.5 m 的占 4.9%（本次实测） | Apple 非商业许可；脚本直接下，零等待 [A0] | annotation+mesh+traj 每景约 45 MB；.mov 中位 934 MB [A3] | 官方 JSON 直接给 centroid/axesLengths/normalizedAxes；有官方 AP@0.25 脚本 [A2] |
| **CA-1M** | 只有帧，没有 .mov：1024×768 RGB，约 10 fps，竖拍已经转正 [C1][C3] | 穷举、无类别的框（9-DoF，评测时转成重力对齐的 7-DoF），世界系和逐帧都有，带 2D 投影 [C1][C2] | **多**：每视频约 125 个框 [C2]；抽样 6 个视频 1,173 个框，38% 最长边 <0.30 m，15% <0.15 m [C1] | CC BY-NC-ND 4.0；curl 直接下，零等待 [C1] | 每视频一个 tar，中位 0.51 GB；20 个约 11–12 GB [C1] | 有官方 loader（dataset.py）；仓库没有评测脚本 [C1] |
| **ScanNet++ v2** | 有。iPhone 13 Pro，1920×1440，60 fps，每个房间约 2 分钟 [S1][S2] | 激光 mesh 上的实例和语义标注；segments_anno.json 里每个实例带 obb [S2][S5] | **多**：v2 共 111k 个实例，约每景 116 个【推断】[S3]；84 个实例类里有 cup、book、monitor、table lamp、plant 等 [S4] | 非商业 ToU，**需要导师手签**；审批约 4–7 天（issue 里的用户反馈）[S6][S7] | iPhone+mesh+标注约 22–25 GB；只要 mesh、标注、位姿约 3–4 GB【推断】[S2] | obb 字段（没有文档，要转置）；toolkit 的 load_annotation 能给逐实例顶点 [S5] |
| ScanNet v2 | 有，但不是随手拍。Structure 传感器 + iPad，彩色 1296×968，30 Hz [N1] | 网格实例分割；ScanNet200 有 200 类 [N1][N2] | 中等：ScanNet200 有 cup、book、monitor、lamp、plant 等 [N2]；VSI-88 里 <0.5 m 占 14.5%（本次实测） | ToU 邮件申请，约 1 周 [N3] | 每个扫描全部文件平均约 0.75 GB【推断】[N4] | VoteNet 脚本产轴对齐框 [N5]；Scan2CAD 提供 9-DoF CAD [N6] |
| EmbodiedScan（v1/v2β） | 用上游数据集的视频（ScanNet/3RScan/MP3D/ARKitScenes） | 9-DoF 有向框，760+ 类 [E1] | 有：284 类里有 cup、book、bottle、monitor、lamp、plant 等 [E2]；标注时专门补过小物体 [E1] | CC BY-NC-SA 4.0；填 Google 表单，等待时间不明【未核实】；还要单独拿上游数据 [E3] | 只有标注文件（大小不明）+ 上游数据 | EmbodiedScanExplorer 可以转成 Open3D 框 [E1] |
| ADT | 头戴 Aria 眼镜，鱼眼 1408×1408，30 fps，卷帘快门；拍的是活动，不是扫描 [D1][D2] | 每个物体有精确 GLB mesh 和逐时刻 6DoF 位姿，还有深度和实例分割 [D1][D3] | **很多**：样例序列 349 个实例，94 个 <15 cm [D4] | 非商业；填邮箱立即拿链接（14 天有效）；**禁止公开展示数据或衍生作品** [D5][D6] | 20 个序列的 RGB+GT 约 25–35 GB，另加物体模型 5.5 GB【推断】[D3] | projectaria_tools 直接给框和位姿 [D7] |
| Replica | 没有视频，要自己渲染 | 每个面带实例 id，物体不是独立 mesh [R1][R2] | 有 cup、book 等，平均约 84 个物体/景 [R1][R3] | 研究用条款，直接下载 [R1] | 全部 33.9 GB [R1] | vMAP 的脚本按 id 拆出子网格 [R2] |
| **ReplicaCAD** | 没有视频，Blender 渲染 | 92 个独立 GLB + 摆放变换 [R4] | apt_0 有 113 个刚体：20 本书、3 个杯子、3 盆植物、3 盏灯等 [R4] | CC-BY-4.0，不设门槛 [R4] | 132 MB [R4] | 每个物体本身就是一个 mesh，GT 完美 |
| HSSD（hssd-scenes） | 没有视频，要渲染 | 整景 GLB，每个物体是一个节点 [H1] | 2,198 个杂物模型（107 类）[H1] | CC BY-NC 4.0；HF 门槛 [H1] | 每景 0.2–0.5 GB [H1] | 节点上的 extras.fp_name 给出物体名 [H1] |
| MultiScan | iPad/iPhone RGB-D，4.3 分钟中位 [M1] | 物体和部件实例 + OBB + 铰接参数 [M2] | 弱：基准排除 <0.008 m³ 的物体 [M1] | CC BY-NC 4.0；HF 点同意 [M3] | 全量 390 GB；基准子集 4.1 GB [M3] | 自带 OBB [M2] |
| 3RScan | Tango 手机，540×960 竖拍，约 245 帧/扫描 [T1][T2] | mesh 实例 + OBB [T1] | 弱：低分辨率 mesh【推断】 | 填 ToU 表单，时长不明 [T3] | 【未核实】 | 自带 OBB [T1] |
| Hypersim | 没有视频（100 帧随机游走）[Y1] | 每个实例有 9-DoF 框；mesh 要另买 [Y1] | 多：平均 127 个物体/景 [Y2] | CC BY-SA 3.0 [Y1] | 每块 zip 1–20 GB [Y1] | 有 hdf5 框 |
| 3D-FRONT | 没有视频，要渲染 | 家具 mesh + 位姿 [F1] | **缺**：基本只有 34 类家具 [F1][F2] | 签协议发邮件 [F3] | — | BlenderProc 有 Front3DLoader [F3] |
| Infinigen Indoors | 没有视频，程序生成后在 Blender 渲染 | 实例分割 + 物体 JSON（能导出框和 mesh）[I1] | **很多**：19 个小物体生成器 + 15 个装饰生成器 [I2] | BSD-3 [I1] | 需要自己生成；单个房间约 11 分钟 CPU，整套房子很慢 [I1] | 原生 .blend，有 export 工具 [I1] |
| InteriorGS | 没有视频（3DGS） | 有向框，755 类 [G1] | 多：554k 个实例 / 1,000 景 [G1] | 自定义许可，门槛 [G1] | 全部 43.8 GB [G1] | 只有框，**没有 mesh** [G1] |
| Aria Everyday Objects (AEO) | Aria 真实视频 | 1,037 个静态 OBB，17 类 [D8] | **无杯子和书**，只有 Lamp、Plant、Screen 等 [D8] | Aria 许可 | — | — |

后面「来源」一节列出了表内每个 [键] 对应的 URL。

### 1.2 ARKitScenes（原计划，用于对比大家具）

- 17 类：cabinet、refrigerator、shelf、stove、bed、sink、washer、toilet、bathtub、oven、dishwasher、fireplace、stool、chair、table、tv_monitor、sofa。没有一类是小物体（https://github.com/apple/ARKitScenes/blob/main/threedod/benchmark_scripts/utils/taxonomy.py ）。
- 3DOD 划分：Validation 549、Training 4,498（https://github.com/apple/ARKitScenes/blob/main/threedod/3dod_train_val_splits.csv ）。VSI-Bench 的 150 个视频全部属于 Validation。download_data.py 列出 24 个缺 3DOD 资产的视频，这 150 个都不在其中（https://github.com/apple/ARKitScenes ）。
- 坐标：标注 JSON 给出 centroid、axesLengths、normalizedAxes（3×3），坐标系是 z 轴朝上。在 27 个视频里核对，287 个框中 282 个只绕 z 轴转，椅子高度（z 方向）中位 0.94 m。官方 IoU 代码也把 z 当竖直轴。官方评测是 VOC 风格的 AP@IoU 0.25（https://github.com/apple/ARKitScenes/tree/main/threedod ）。
- 原始视频（解析 47331068 的 .mov 文件头）：第一条轨道 1920×1440 HEVC 60 fps，旋转矩阵是单位阵，所以**竖拍视频是横着存的**（https://github.com/apple/ARKitScenes/blob/main/raw/README.md ；文件头是本次用 range 请求读的）。lowres_wide.traj 是 10 Hz。
- `sky_direction`：每个视频一个值，VSI-150 里 Left 66、Up 50、Down 34，Left 对应竖拍（metadata.csv，https://github.com/apple/ARKitScenes ）。第三方 HF 卡说这个标签「is wrong for ~60% of sampled sequences」（https://huggingface.co/datasets/rerun/arkitscenes-rrd ，Apple 没有确认）。我们组 10-09 在 41125700 上也遇到过：metadata 写 Up，但 1034/1064 帧的位姿显示是 Left（内部记录，没有 URL）。**做法：按位姿逐帧算朝向**，CA-1M 的 `orientation.py` 就是这么做的（https://github.com/apple/ml-cubifyanything ）。
- VSI-Bench 视频：ScanNet++ 和 ARKitScenes 抽到 30 FPS，统一 640×480；ARKitScenes「normalize their rotation to maintain a consistent upward orientation」（https://arxiv.org/abs/2412.14171 附录 B.1）。BVB 用的就是这些视频（https://arxiv.org/abs/2609.15478 ）。
- 卷帘快门和运动模糊：ARKitScenes 的论文和文档都没提【未核实】。手机 CMOS 一般是卷帘快门【推断】。
- 隐私打码：没有找到相关说明【未核实】。

### 1.3 CA-1M / Cubify Anything（Apple，CVPR 2025）

- **标注内容**：论文称标注是「exhaustive」「class agnostic」，约 3.5K 个视频共 439K+ 个物体，表 1 写的类别数是「440K (1)」（https://arxiv.org/abs/2412.04458 ）。实际数据里还有自由文本的 `category` 字段；2025-09 又加了 caption（https://github.com/apple/ml-cubifyanything ，loader 见 https://github.com/apple/ml-cubifyanything/blob/main/cubifyanything/dataset.py ）。
- **小物体（本次抽样）**：用 range 请求读了 6 个重叠视频的 `world.gt/instances.json`，没有下载整包。
  - 共 1,173 个框，每个视频 105–336 个，自由文本类别 200 种。
  - **48% 的类别是笼统的「object」**。具体类别里有 bottle 31、lamp 11、cup、book、vase、remote control、candle、outlet 等。
  - 最长边中位 0.43 m，第 10 百分位 0.12 m，最小 0.046 m。
  - 按本文的尺寸档：XS 269（22.9%）、S 363（30.9%）、M 285（24.3%）、L 256（21.8%）。注意 L 档里有墙、门框等结构件，评测前要去掉。
- **GT 形式**：世界系框在激光扫描坐标系里（z-up），带完整 3×3 旋转和 8 个角点。1,173 个框里有 24 个带俯仰或横滚。论文训练和评测都用「gravity-aligned 7-DOF」（默认 `BoxDOF.GravityAligned`）。逐帧 instances.json 在相机坐标系下，带 `box_2d_rend`（可见部分）和 `box_2d_proj`（完整投影）。每帧还有 `T_gravity.json`。**没有发布 mesh 或掩码**（https://github.com/apple/ml-cubifyanything ；https://arxiv.org/abs/2412.04458 ）。
- **格式和大小**：每个视频一个 WebDataset tar，地址形如 `https://ml-site.cdn-apple.com/datasets/ca1m/{split}/ca1m-{split}-{id}.tar`。每帧包括：
  - 1024×768 PNG；
  - ARKit LiDAR 深度 256×192；
  - **FARO 激光渲染的 GT 深度** 512×384；
  - 注册到激光坐标系的位姿 `RT.json`。

  帧间隔 100 ms（约 10 fps），**没有 .mov**。验证集 107 个 tar 共 64.3 GB，中位 0.51 GB（对 CDN 发 HEAD 请求得到）。
- **许可和划分**：CC BY-NC-ND 4.0（https://github.com/apple/ml-cubifyanything/blob/main/data/LICENSE_DATA ）；val 107 个、train 3,118 个（`data/val.txt`、`data/train.txt`）。**视频 ID 和 ARKitScenes 的 video_id 一致。**
- **和 BVB/VSI 的重叠（本次实测）**：VSI-Bench 的 test.jsonl 里有 150 个 ARKitScenes 场景，和 CA-1M val.txt 取交集得 **27 个**，和 train 的交集是 0。这 27 个的 tar 共约 16.3 GB。
  - 对比 CA-1M 帧的时间跨度和 ARKitScenes 轨迹时长，5 个覆盖不到 80%：42898486（2%）、42897692（19%）、45662970（65%）、47334107（74%）、42897688（76%）。
  - **剩下 22 个可用**：42897538、42897647、42898849、42899617、42899698、42899712、42899725、42899729、44358442、44358451、45261121、45261575、45663164、47115469、47115525、47115543、47204552、47331068、47331262、47331319、47334239、47430475。
- **评测**：仓库里没有评测脚本，只有 demo。论文按逐帧、无类别报 AP/AR@IoU 0.25/0.50，每帧最多 100 个检测。只有一种按距离的拆分：near 0–2 m、medium 2–4 m、far 4–5 m（表 10）。**没有按尺寸拆分**（https://arxiv.org/abs/2412.04458 ）。
- **其他问题**：
  - 论文说有「over 1.8M validation frames」，但已发布的 val tar 估计只有约 68K 帧【推断：两者不一致】。
  - 两个仓库都关闭了 GitHub issues。
  - 论文和仓库都没提隐私打码。

### 1.4 ScanNet++ v2

- **iPhone 数据**：
  - iPhone 13 Pro，RGB 1920×1440、LiDAR 深度 256×192，都是 60 FPS；每个房间约 2 分钟手持视频。v2 改为 `iphone/rgb.mkv`（https://arxiv.org/abs/2308.11417 §3.3；https://kaldir.vc.in.tum.de/scannetpp/documentation ；https://kaldir.vc.in.tum.de/scannetpp/changelog ）。该域名已重定向到 scannetpp.mlsg.cit.tum.de（https://github.com/scannetpp/scannetpp/issues/213 ）。
  - 三种位姿：`pose_intrinsic_imu.json` 里的 `poses` 是原始 ARKit；`aligned_poses` 已变换到 mesh 坐标系；`iphone/colmap` 是注册到激光扫描的米制 COLMAP 位姿，只覆盖部分帧（documentation；https://github.com/scannetpp/scannetpp/issues/104 ）。
  - 论文提到 iPhone 有运动模糊和位姿噪声（§6）。
- **隐私**：iPhone 视频里匿名化的区域涂成品红 (255,0,255)，另给掩码。被匿名化的 mesh 顶点不参与评测（documentation；https://kaldir.vc.in.tum.de/scannetpp/benchmark/insseg ）。具体遮了什么（人脸、屏幕）文档没写【未核实】。
- **标注**：
  - 在 5% 降采样的激光 mesh 上标注，文件是 segments.json 和 segments_anno.json；一个顶点可以有多个标签（documentation；论文 §3.5）。
  - 论文称「densely annotated … close to 100% completion for every scene」（论文图 6）。
  - v2 共 3.4k 个标签、111k 个实例（changelog），平均每景约 116 个实例【推断】。
- **实例基准的 84 类里的小物体**：cup、book、monitor、table lamp、ceiling lamp、plant、plant pot、bottle、keyboard、mouse、laptop、bowl、jar、kettle、headphones、stapler、marker、telephone、clock、tissue box、power strip 等（https://kaldir.vc.in.tum.de/scannetpp/benchmark/insseg ）。没有笼统的「lamp」类。
- **划分**：nvs_sem_train 856、nvs_sem_val 50（GT 公开）、sem_test 50（隐藏）、nvs_test 50（documentation）。VSI-Bench 的 50 个 ScanNet++ 场景取自验证集（https://arxiv.org/abs/2412.14171 ），**大概率就是 nvs_sem_val 的 50 个**【推断：拿到 split 文件后核对】。
- **逐物体框**：segments_anno.json 的每个 segGroup 都带 `obb`（centroid、axesLengths、normalizedAxes、min、max）。几点注意：
  - 这个字段没有文档；维护者 2023 年说「We have not released any code for handling the bounding boxes」（https://github.com/scannetpp/scannetpp/issues/31 ）。
  - normalizedAxes 要先 reshape(3,3) 再转置（https://github.com/scannetpp/scannetpp/issues/196 ）。
  - 有用户报告这些框不是重力对齐的（issue #31）。不过本次实测发现，VSI-Bench 的 ScanNet++ 框 1,119 个里 933 个有一条竖直轴，说明大多是重力对齐的（VSI 可能重新算过）。
- **其他工具**：`common/utils/anno.py` 的 `load_annotation(..., return_vertex_obj_ids=True)` 返回逐实例顶点；`semantic/prep/semantics_2d.py` 用 Open3D OBB 裁出物体 mesh，并能栅格化出逐帧 2D 实例掩码（https://github.com/scannetpp/scannetpp ）。
- **坐标**：米制。粗对齐方式是 XY 平面上做 PCA，再平移到正坐标，所以墙不一定和坐标轴平行（https://github.com/scannetpp/scannetpp/issues/25 ）。z 轴朝上【推断】。
- **申请流程**：注册 → 新建申请 → 上传 ToU → 批准后拿个人 token（https://kaldir.vc.in.tum.de/scannetpp/ ）。
  - ToU 要求**申请人和 PI/导师手写签名**（https://kaldir.vc.in.tum.de/scannetpp/static/scannetpp-terms-of-use.pdf ）。
  - 审批时长（issue 记录）：4–5 天（#136，2024-12-25）；维护者说「at least once a week」处理一次（#176，2025-09-08）；「may take up to 1 week」（#195，2025-12-25）。token 14 天过期，可以在面板续期（#190）。
  - **2026 年服务器不稳定**：HTTP 500（#208，6 月）、429 和超时（#211，7 月）、站点宕机（#213，2026-09-22）、大文件下载卡住（#214，2026-09-24，仍未关闭）。以上 issue 都在 https://github.com/scannetpp/scannetpp/issues 。
- **按需下载**：下载配置的 `default_assets` 可以改，只选 iphone_video、pose_intrinsic_imu、colmap、scan_mesh、scan_anno_json、scan_mesh_segs 等（https://github.com/scannetpp/scannetpp/issues/167 ）。维护者建议先下一个场景试（#166）。能否在 yaml 里按场景 ID 选【未核实】。
- **大小**：全量默认 1.5 TB；mesh 加语义 132 GB（documentation），约合每景 1 GB iPhone 数据 + 0.14 GB mesh 和标注【推断】。
- **许可**：只限非商业研究和教育；只能分享给同样签了条款的人；要能按 GDPR 要求删除个人数据（ToU PDF）。
- **VSI-Bench 里的副本**：scannetpp.zip（1.03 GB）有 50 个 640×480 的 mp4，不用申请就能拿到，但没有位姿和深度（https://huggingface.co/datasets/nyu-visionx/VSI-Bench ）。帧号对应关系可能是原始帧 = 2i，内参缩为 1/3【推断】。

### 1.5 VSI-Bench meta_info：不用申请就能用的现成 GT 框（新发现）

- 仓库 2025-08-05 发布了 `data/meta_info/{arkitscenes,scannet,scannetpp}_meta_info_val.json`（仓库许可 Apache-2.0，见 https://github.com/vision-x-nyu/thinking-in-space ）。覆盖全部 288 个场景，按类别给出 Open3D OrientedBoundingBox 格式的框，另有房间面积、房间中心和视频路径。
- 论文说明类别是精选的：「we exclude both rare categories and those with extremely small object sizes」（https://arxiv.org/abs/2412.14171 ）。**所以这份框不是穷举的**，但仍然包含不少小物体。
- 本次实测：

| 子集 | 景数 | 类数 | 框数 | 每景均值 | XS <0.2 m | S 0.2–0.5 m | M 0.5–1.5 m | L ≥1.5 m |
|---|---|---|---|---|---|---|---|---|
| ARKitScenes | 150 | 13 | 854 | 5.7 | 0 | 42（4.9%） | 621 | 191 |
| ScanNet | 88 | 33 | 1,224 | 13.9 | 1 | 177 | 790 | 256 |
| ScanNet++ | 50 | 43 | 1,119 | 22.4 | 60 | 254（XS+S 合计 28.1%） | 618 | 187 |

- ScanNet++ 子集里的小物体类别：computer mouse 33、cup 15、telephone 15、shoes 15、plant 10、power strip 10、kettle 5、laptop 5、bowl 3、headphones 2，另有 keyboard 39、monitor 70（多数落在 M 档）。
- 重力对齐情况：ARKitScenes 834/854、ScanNet++ 933/1119 的框有一条竖直轴；ScanNet 只有 235/1224，推断是 PCA 框，不是只绕 yaw 转的框。
- 用途：在 ScanNet++ 申请批下来之前，**用这份框和 VSI 视频就能先跑小物体评测的开发版本**。限制是没有 GT 相机位姿，只能用物体做对齐（见 2.5），而且这会把一部分信息泄漏给对齐步骤。

### 1.6 ScanNet v2 / ScanNet200 / Scan2CAD

- **传感器和规模**：Structure 传感器，深度 640×480、彩色 1296×968，都是 30 Hz；自动曝光，平均曝光约 30 ms，容易运动模糊（https://arxiv.org/abs/1702.04405 ）。标注要求至少覆盖 25% 的表面，平均每个扫描 24.1 个标注物体（同上，表 2）。
- **ScanNet200**：取实例数最多的 200 类，按训练集标注点数分成 head/common/tail = 66/68/66（https://arxiv.org/abs/2204.07761 ）。按档的小物体：
  - head：book、monitor、lamp、plant；
  - common：bottle、keyboard、laptop、telephone；
  - tail：cup、mouse、bowl、clock、headphones、tissue box。

  （https://github.com/ScanNet/ScanNet/tree/master/BenchmarkScripts/ScanNet200 ）
- **检测框**：VoteNet 先用 `axisAlignment` 对齐，再对每个实例取点的 min/max，得到轴对齐框（https://github.com/facebookresearch/votenet/blob/main/scannet/load_scannet_data.py ）。
- **Scan2CAD**：1,506 个扫描、14,225 个 CAD 对齐，平均每扫描 9.3 个，主要是椅子、桌子、柜子；要填表，还要申请 ShapeNet（https://arxiv.org/abs/1811.11187 ；https://github.com/skanti/Scan2CAD ）。
- **申请**：用机构邮箱签 ToU 后发邮件，README 写「If you have not received a response within a week, it is likely that your email is bouncing」（https://github.com/ScanNet/ScanNet ）。用户反馈约 1 周（issue #36），也有 8 天没回复的（#118）；2025-09 出现过 ToU 链接打不开（#179）。
- **结论**：小物体覆盖不如 ScanNet++，彩色质量低，还要三套申请。只作为和 Vid2CAD/ROCA 对比的备选，不进主线。

### 1.7 EmbodiedScan（v1 / v2 beta）

- **v1**：5,185 个扫描（ScanNet、3RScan、Matterport3D），160K 个 9-DoF 有向框，760+ 类。检测基准用 284 类，head/common/tail = 90/94/100。标注时用 SAM 辅助工具专门补了朝向和小物体（https://arxiv.org/abs/2312.16170 ）。
- **284 类里的小物体**：cup、book、bottle、bowl、monitor、keyboard、mouse、laptop、lamp、plant、vase、clock、remote control、tissue box、headphones 等（https://github.com/OpenRobotLab/EmbodiedScan 的 configs/detection/mv-det3d_8xb4_embodiedscan-3d-284class-9dof.py）。
- **注意**：已发布的标注只含 288 个常见类，其余标成「object」；长尾版本的 issue 还开着（EmbodiedScan issue #60）。
- **v2 beta（2024-09）**：新增约 5K 个 ARKitScenes 扫描，data/README 的目录结构里 Training 和 Validation 都有（https://github.com/OpenRobotLab/EmbodiedScan ）。**所以它可能覆盖 BVB-150，从而在原视频上直接提供带类别的小物体框**【未核实：要拿到数据才能确认具体扫描列表】。
- **获取**：填 Google 表单，等待时长不明。许可 CC BY-NC-SA 4.0。表单成本很低，建议本周顺手提交，作为对冲。

### 1.8 Aria Digital Twin（ADT）及 Aria 系

- **规模**：论文和官网写 200 个序列、约 400 分钟、2 个空间；文档页写 236 个序列，同一页的分项数字又对不上（https://www.projectaria.com/datasets/adt/ ；https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset ）。物体共 398 个：公寓 281 个独特静态物体（324 个实例），办公室 15 个独特物体，74 个动态物体两处共用（同上）。
- **小物体**：解析仓库里的公寓样例序列 GT（https://github.com/facebookresearch/projectaria_tools 的 data/gen1/aria_digital_twin_test_data）：
  - 349 个实例，106 个类别；
  - book ×19、vase ×19、house plant ×13、cup ×6、desk lamp ×2；
  - 框最长边中位 0.25 m，94 个 <15 cm。
- **视频**：RGB 1408×1408、30 fps、110° 鱼眼、卷帘快门（https://facebookresearch.github.io/projectaria_tools/docs/tech_spec/hardware_spec ）。内容是头戴视角下的脚本化活动，不是专门的扫描（https://arxiv.org/abs/2306.06362 ）。
- **GT**：
  - `instances.json`（静态/动态标记、规范的 up/front 向量）；
  - `scene_objects.csv`（逐时刻位姿）；
  - `3d_bounding_box.csv`（物体自身坐标系下的框）；
  - 深度、实例分割、2D 框及可见比例；
  - 每个物体一个 GLB，全部约 5.5 GB。

  位姿误差均值 6.83 mm / 1.29°（https://arxiv.org/abs/2306.06362 ；文档的 data_format 和 object_models 页）。
- **坐标**：场景系 **Y 朝上**，重力是 (0, −9.81, 0)，导入 Blender 前要转成 Z 朝上（样例数据 aria_trajectory.csv）。
- **许可**：§3 禁止「publicly display or perform any of the Dataset or materials or works derived from the Dataset」。§2 允许发表研究的「observations, commentary, analysis and summaries」，但要注明「[Aria Digital Twin Dataset, Meta Reality Labs Research]」（https://www.projectaria.com/datasets/adt/license/ ）。**论文里放 ADT 渲染图是否算允许的「summaries」，条款没明说**；放之前建议邮件问 projectaria@meta.com（同页）。
- **对我们的问题**：
  - 实际上只有一套公寓，20 个序列等于反复看同一布局；
  - 动态物体会被人移动；
  - 要先把鱼眼和卷帘快门校正成针孔图像；
  - 视角是头部运动，覆盖不全。

  以上为【推断】。所以 ADT 只适合当「小物体形状」的补充测试。
- **其他 Aria 数据**：
  - AEO：17 类，没有杯子和书（https://www.projectaria.com/datasets/aeo/ ）。
  - ASE：合成数据，约 23 TB；EFM3D 给了 43 类有向框，只有验证子集有 GT mesh（https://arxiv.org/abs/2406.10224 ）。
  - DTC（2025）：2,400+ 个扫描物体，以物体为中心，适合单独评 image-to-3D 这一步（https://www.projectaria.com/datasets/dtc/ ）。
  - HOT3D：33 个手持物体，主题是手物交互（https://arxiv.org/abs/2406.09598 ）。

### 1.9 合成数据（GT 完美的受控实验）

- **ReplicaCAD（最快能用）**：
  - 92 个独立 GLB，PNG 纹理，有 books、cups、bowls、plates、plants、lamps、monitor、remote、vase。apt_0 用 JSON 变换摆放了 113 个刚体（20 本书、3 个杯子、3 盆植物、3 盏灯）。CC-BY-4.0，不设门槛，132 MB（https://huggingface.co/datasets/ai-habitat/ReplicaCAD_dataset ）。
  - 只有一套公寓布局，但可以重新摆放物体，生成多种场景。
  - Habitat 是 Y 朝上、wxyz 四元数【未核实】。
- **HSSD**：211 个场景、18,656 个物体、466 类（https://arxiv.org/abs/2306.11290 ）。
  - `hssd-hab` 的 GLB 强制使用 KHR_texture_basisu（KTX2），Blender 可能导入失败。
  - 改用 `hssd/hssd-scenes`：168 个整景 GLB，普通纹理，每个物体是一个节点（https://huggingface.co/datasets/hssd/hssd-scenes ）。
  - 能否直接导入 Blender【未核实】。
- **Replica**：物体不是独立 mesh。按面 id 拆分要用 vMAP 的 extract_inst_obj.py（https://github.com/kxhit/vMAP ）。BlenderProc 拆开后只剩顶点色（https://github.com/DLR-RM/BlenderProc/blob/main/blenderproc/python/loader/ReplicaLoader.py ）。
- **Infinigen Indoors**：小物体最密，原生 Blender，BSD-3（https://github.com/princeton-vl/infinigen ；https://arxiv.org/abs/2406.11824 ）。
  - 有内存超 55 GB 崩溃的报告（issue #333）。
  - 小物体经常浮在支撑面上方，issue #376 仍未关闭。
  - 预计要约 1 周才能跑通【推断】。
- **3D-FRONT**：基本只有家具，不适合评小物体（https://arxiv.org/abs/2009.09633 ）。
- **Hypersim**：没有视频，mesh 要购买（https://github.com/apple/ml-hypersim ）。
- **领域差距和训练集重叠**：
  - VGGT 的训练数据包括 Hypersim、Habitat、Replica、ASE、ADT（https://arxiv.org/abs/2503.11651 ）。用 Pi3X/VGGT 类模型的管线在这些数据上的分数可能偏高。Pi3X 的训练集有没有这些【未核实】。
  - 合成视频要加运动模糊、噪声、曝光抖动和手抖。Replica 论文提到渲染图因为没有运动模糊而容易被识破（https://arxiv.org/abs/1906.05797 ）。

### 1.10 2025–2026 新东西（筛过）

- **OCH3R（arXiv 2605.13018）**：明确写了「Existing indoor benchmarks … primarily emphasize room layout and large furniture, while providing limited coverage of the object interaction scale」，然后改用 HOPE、YCB-Video、PACE、Omni6DPose、NOCS 评小物体。但它是单图、桌面场景，也没有按尺寸分档（https://arxiv.org/html/2605.13018 ）。这句话**可以直接在报告里引用，作为我们关注小物体的动机**。
- **OVOW（arXiv 2606.31388）**：单目视频 → 4D 场景。合成基准 2×120 个场景，每景 3–5 个 Objaverse 物体，指标是 Scene-IoU、匈牙利匹配后的 Object-IoU 等。没有看到数据发布（https://arxiv.org/html/2606.31388v1 ）。不适合室内房间。
- **SceneFun3D**（ARKitScenes 上的功能部件）、**Articulate3D**（ScanNet++ 上的铰接标注）、**OpenLex3D**（23 个场景的开放词汇标签）、**ARKit LabelMaker**（自动标签，不是人工真值）：都不能直接提供小物体框真值（https://arxiv.org/abs/2412.01398 ；https://arxiv.org/abs/2503.19764 ；https://arxiv.org/abs/2410.13924 ）。
- **SpatialLM-Testset**：107 个由 RGB 视频重建的点云 + GT 布局（https://huggingface.co/datasets/manycore-research/SpatialLM-Testset ）。没有原视频可用，不适合我们。

---

## 2. 指标方案：按尺寸分档的物体级评测

### 2.1 前人怎么分档（结论：室内物体级重建没有按尺寸分档的先例）

| 来源 | 分档依据 | 阈值 |
|---|---|---|
| COCO（2D 惯例） | GT 面积（像素²） | small <32²，medium 32²–96²，large >96²；落在档外的未匹配检测忽略，不算 FP（https://github.com/cocodataset/cocoapi/blob/master/PythonAPI/pycocotools/cocoeval.py ） |
| Omni3D / Cube R-CNN | 物体中心深度（不是尺寸） | near 0–10 m，medium 10–35 m，far >35 m；AP3D 在 τ∈{0.05…0.50} 上平均（https://arxiv.org/abs/2207.10660 ） |
| CA-1M / CuTR | 距离（不是尺寸） | near 0–2 m，medium 2–4 m，far 4–5 m（https://arxiv.org/abs/2412.04458 表 10） |
| **DSPDet3D**（ECCV'24） | **类别平均体积** | 小物体类 = 平均体积 <0.05 m³，按类不按实例（https://arxiv.org/abs/2305.03716 ） |
| ScanNet200 | 训练集标注点数（频率，间接受尺寸影响） | 66/68/66（https://arxiv.org/abs/2204.07761 ） |
| EmbodiedScan | 类别频率 | 90/94/100（https://arxiv.org/abs/2312.16170 ） |
| Waymo（LiDAR 参考） | 点数 / 难度 | ≤5 个点算 LEVEL_2（https://arxiv.org/abs/1912.04838 ） |

另外，SpatialLM、SceneScript、ODAM、SceneActBench 都没有按尺寸分档（https://arxiv.org/abs/2506.07491 ；https://arxiv.org/abs/2403.13064 ；https://arxiv.org/abs/2108.10165 ；https://arxiv.org/abs/2607.22393 ）。

### 2.2 本项目的分档定义（建议）

- **主分档：按 GT 有向框最长边 L 分。**
  - XS：L < 0.2 m（杯子、鼠标、遥控器），作为 S 档的子行单独报；
  - S：L < 0.5 m（书、台灯、小盆栽、水壶、键盘的一部分）；
  - M：0.5 ≤ L < 1.5 m（显示器、椅子、床头柜、落地灯）；
  - L：L ≥ 1.5 m（床、沙发、桌子、柜子）。
- **为什么用最长边不用体积**：薄物体用体积分档会偏得很厉害。显示器 0.6×0.05×0.4 m 只有 0.012 m³，按体积会被归成小物体；地毯长 2 m，体积却很小【推断】。体积档作为副表，可以按 DSPDet3D 的 0.05 m³ 和前人对齐。
- **每档都要报物体数 N**。各数据集各档的数量见 1.3 和 1.5 的表，ARKitScenes 的 S 档只有 42 个，正说明它测不了小物体。
- **另报重点类别**：cup、book、monitor、lamp、plant 单独成行，因为用户关心的显示器多数落在 M 档。
- 结构件（墙、地板、天花板、门框、窗）不计入物体指标；CA-1M 的世界系框里有这些（https://github.com/apple/ml-cubifyanything ）。

### 2.3 匹配规则和「三类结果」

记 GT 框中心 c_g、半对角线 r_g（外接球半径），预测框中心 c_p；归一化中心距 d̂ = ‖c_p − c_g‖ / r_g；体积比 ρ = max(V_p/V_g, V_g/V_p)^(1/3)。

1. **类别处理**：
   - GT 有类别（ScanNet++、ARKitScenes、VSI meta）时按类匹配。用一张手写同义词表把 AHa-3D 的物体名映射到 GT 词表，查不到再用文本嵌入兜底。
   - CA-1M 只能做无类别匹配。
   - 所有数据集都另报一份无类别结果。
2. **一对一分配**：以 d̂ 为代价做匈牙利匹配，这和 SceneActBench、SpatialLM 一样（https://arxiv.org/abs/2607.22393 ；https://arxiv.org/abs/2506.07491 ）。
3. **两套「正确」判据并报**：
   - (a) **IoU3D ≥ 0.25**，另报 0.5。这是 ARKitScenes 官方、CA-1M、SpatialLM、SceneScript 的通用口径，和前人可比。用 `pytorch3d.ops.box3d_overlap` 计算，输入是 8 个角点，要按规定顺序排列（https://pytorch3d.readthedocs.io/en/latest/modules/ops.html ）。
   - (b) **按尺寸归一化的判据（小物体主指标）**：d̂ ≤ 0.5 且 ρ ≤ 1.5。另画 d̂ 阈值 ∈ {0.25, 0.5, 1.0} 的曲线。依据如下：
     - 3D-MOOD 的匹配阈值是「∈ [0.5, 0.55, …, 1.0] of the radius of the 3D GT boxes」，并指出 IoU 对小物体和薄物体「too restrictive」（https://arxiv.org/abs/2507.23567 ）；
     - Omni3D 指出 IoU3D 下降「much steeper than 2D」（https://arxiv.org/abs/2207.10660 ）；
     - CatFree3D 指出 IoU 对不重叠的框给不出分，这对薄物体和小物体是个问题（https://arxiv.org/abs/2408.12747 ）。
   - 阈值 0.5 和 1.5 是我的建议【推断】，要在开发集上看看分布再定。
4. **每个 GT 物体归入三类之一**（仿 TIDE 的双阈值：TIDE 用 t_f=0.5、t_b=0.1，Missed 定义为「All undetected ground truth … not already covered by classification or localization error」，见 https://arxiv.org/abs/2008.08115 ）：
   - **放对**：满足 (b)（另报满足 (a) 的比例）。
   - **检出但放错**：在宽松门限内有匹配，但不满足 (b)。宽松门限：按类时，同类且 ‖c_p−c_g‖ ≤ max(2·r_g, 0.5 m)；无类别时，‖c_p−c_g‖ ≤ max(r_g, 0.25 m) 且 ρ ≤ 3【推断，为本方案自定】。再仿 TIDE3D 细分成位置、尺寸、朝向三种错误（https://arxiv.org/abs/2310.05447 ）。朝向只在 L 档、非旋转对称的类别上看，yaw 误差 >30°。
   - **没检出**：宽松门限内没有任何预测。
5. **精确率和幻觉**：没匹配上的预测按**预测框**尺寸归档，这和 COCO 一致。只在穷举标注的数据上算精确率（CA-1M、ScanNet++）。ARKitScenes 只标了 17 类，VSI meta 也是精选类别，**在这两个上不报精确率**，否则会把正确建出的未标注物体算成误检。
6. **和 CAD 对齐文献比较（L 档、M 档可选）**：用 Scan2CAD 判据，同时满足平移 ≤20 cm、旋转 ≤20°、尺度 ≤20%。代码里尺度误差是 `100·|mean(s/s_gt) − 1|`，贪心匹配，同时报实例平均和类平均（https://github.com/skanti/Scan2CAD/blob/master/Routines/Script/EvaluateBenchmark.py ）。Vid2CAD 也报「class avg.」和「global avg」（https://arxiv.org/abs/2012.04641 ）。**20 cm 这个绝对阈值对杯子不公平**，所以不用在 S 档。

### 2.4 形状指标（给 Hunyuan3D 类物体用）

- **逐物体 Chamfer-L1（厘米）和 F-score@τ**，其中 τ = 5% × GT 框对角线，这是 SceneActBench 的 F@5%（https://arxiv.org/abs/2607.22393 ）。SceneActBench 的具体做法：
  - 固定尺度 ICP，尺度取两框对角线之比，ICP 只解旋转和平移，yaw 初值试 0/90/180/270°；
  - 匈牙利匹配，超过 0.6·δ_scene 的匹配拒绝；
  - **没匹配上的物体记 0 分**。

  另报绝对阈值 2 cm 和 5 cm 下的 F-score。
- **两个版本**：
  - (i) **原位**：只做整景对齐，同时反映位置和形状。
  - (ii) **只看形状**：每个物体单独做固定尺度 ICP 后再算。

  对单位球归一化（DepR，https://arxiv.org/abs/2507.22825 ）或重新居中（SceneActBench）会抹掉位姿和尺寸误差，所以必须和 2.3 的放置指标一起报。
- **GT mesh 的来源**：
  - ScanNet++：用 obb 或实例顶点从激光 mesh 裁出物体，但**底面和背面不完整**（ObjectCarver 讨论过这个问题，https://arxiv.org/pdf/2407.19108 ）。因此 GT→预测 的完整度为主指标，预测→GT 的精度只在 GT 观测到的区域内算【推断】。
  - ADT、ReplicaCAD：mesh 完整，两个方向都能算。
  - ARKitScenes、CA-1M：只有框，不评形状。
- 采样：每个物体 10k 点（Total3D、Im3D、DepR 的惯例，https://arxiv.org/abs/2002.12212 ）。

### 2.5 对齐：重力、尺度、坐标系

- **坐标约定**：Blender 是 Z 朝上。
  - Z 朝上：ARKitScenes 标注（实测）、CA-1M、ScanNet++（推断）、ScanNet（https://github.com/ScanNet/ScanNet ）。
  - **Y 朝上**：ADT（重力 (0,−9.81,0)）、Habitat/ReplicaCAD【未核实】。
- **主方案：用相机轨迹做 Sim(3) Umeyama。** 把 AHa-3D/Pi3X 每帧的相机中心和 GT 相机中心按时间戳对应起来，解 s、R、t，相当于 `evo_ape --align --correct_scale`（https://github.com/MichaelGrupp/evo/blob/master/evo/main_ape.py ）。
  - 先例：SpatialLM 附录 C.3「we align the estimated camera trajectory from MASt3R-SLAM to the ground-truth camera trajectory」，然后再评检测 F1（https://arxiv.org/abs/2506.07491 ）。
  - **不要用被评的物体去解对齐**，否则对齐会把要测的误差吸收掉【推断】。
  - GT 位姿来源：ARKitScenes 用 lowres_wide.traj（10 Hz，要插值）；CA-1M 用 RT.json（激光坐标系，只覆盖注册过的帧）；ScanNet++ 用 aligned_poses 或 colmap。
- **同时报三种**：
  - (a) Sim(3) 对齐后的指标；
  - (b) 只做 SE(3)、保留预测尺度的指标，用来检验米制尺度。rpg_trajectory_evaluation 对单目用 `sim3`，对 VIO 用 `posyaw`（https://github.com/uzh-rpg/rpg_trajectory_evaluation ）；
  - (c) 估出的尺度 s 本身。

  先例：MoGe-2 同时报米制和相对几何（https://arxiv.org/abs/2507.02546 ）。
- **尺度误差会推着物体一起偏**：全局尺度差 10% 时，离对齐中心 3 m 的物体会偏约 30 cm，即使形状完美也过不了 Scan2CAD 的 20 cm【推断】。Vid2CAD 也专门讨论过尺度和深度的歧义（https://arxiv.org/abs/2012.04641 ）。
- **没有 GT 位姿时的退路**（例如只有 VSI meta 框）：先用预测的地面法向做重力对齐，再只拿 **L 档物体中心**做 RANSAC，解 4-DoF（x、y、yaw）加尺度，然后只评 S 档和 M 档。报告里要写明「对齐用了 GT 物体」【推断】。
- **视频帧对应**：
  - VSI-Bench 和 BVB 的视频是重采样过的（30 FPS，640×480），ARKitScenes 还旋转过（https://arxiv.org/abs/2412.14171 ）；
  - ScanNet++ 推测是原始帧 = 2i【推断】；
  - 要用帧数和时长核对。最好直接拿原始资产的时间戳。

### 2.6 全局场景指标

- **整景 Chamfer 和 F-score**：和 GT 激光 mesh 比（ScanNet++ 的 mesh、ARKitScenes 的 mesh），阈值 5 cm 和 10 cm，用同一个 Sim(3)。VGGT 用 Umeyama 对齐后报 Accuracy、Completeness、Chamfer（https://arxiv.org/abs/2503.11651 ）。HARMONY 那种归一化到单位立方体再做 ICP 的做法会抹掉尺度，不要用（见前情笔记）。
- **深度误差**：在 GT 相机位姿下渲染 Blender 场景，和 GT 深度比 AbsRel、δ<1.25。CA-1M 的 FARO 渲染深度最可靠；ARKitScenes 用 lowres_depth。
- **相机**：ATE（Sim(3)）和尺度 s。
- **延续前情笔记的项目**：物体数比、AHa-3D 的物理检查（穿插、悬空、稳定性）、BVB 的 DV/LS，以及成本。
- **统计**：
  - 以场景为单位 bootstrap 95% 置信区间；
  - 方法之间做逐场景配对比较（Wilcoxon）；
  - 每档都报 N；
  - 开发集和测试集分开，最终数字只报测试集。

---

## 3. 推荐（2 个月；12 GB 笔记本 + Colab A100）

### 3.1 小物体定量评测（i）

**首选 ScanNet++ v2：从 BVB/VSI 的 50 个验证场景里挑 20 个。**
- **选法**：按 VSI meta 中最长边 <0.5 m 的物体数排序，取前 20 个（本次实测）。这 20 个合计小物体 236 个、M 档 353 个、L 档 98 个，每景至少 6 个小物体。完整的 ScanNet++ 标注会多得多（每景约 116 个实例【推断】）。
  - 开发集 5 个：b0a08200c9、d755b3d9d8、c49a8c6cff、3f15a9266d、0d2ee665be。
  - 测试集 15 个：578511c8a9、f3d64c30f8、fb5a96b1a2、3db0a1c8f3、acd95847c5、1ada7a0617、25f3b7a318、c50d2d1d42、5eb31827b7、27dd4da69e、09c1414f1b、ac48a9b736、7b6477cb95、9071e139d9、38d58a7a31。
- **理由**：
  - 真实手持视频，激光级 GT；
  - 带类别的稠密实例，可以按类分析 cup、book、monitor、lamp、plant；
  - 有逐物体 mesh，能评形状；
  - 位姿已注册到 mesh 坐标系，可以做轨迹对齐；
  - **BVB-results 里已有这 50 个场景所有配置的 .blend**，基线不用花钱（https://huggingface.co/datasets/yunlong10/BVB-results ）。
- **下载**：只要 mesh、标注和 iPhone 位姿约 3–4 GB；如果还要原始 iPhone 视频，约 22–25 GB【推断】。输入视频可以直接用 VSI 的 640×480 mp4，和 BVB 输入一致。12 GB 显卡本来就要把 Pi3X 的像素上限压到 100k–150k，所以 640×480 不会成为瓶颈。
- **风险和对策**：
  - 申请要导师手签，本周就交；
  - 2026 年 9 月站点宕过机（#213、#214），批下来后立刻按场景下载；
  - 在批下来之前，用 1.5 节的 VSI meta 框 + VSI 视频先跑开发版，用 2.5 节的退路方案对齐。

**零等待的补充：CA-1M ∩ BVB-150 中可用的 22 个视频（ID 见 1.3）。**
- **理由**：
  - 不用申请，今天就能下；
  - 标注是穷举的，小物体占一半以上；
  - 同一个视频同时有 ARKitScenes 的 17 类框，可以和 3.2 共用；
  - FARO 深度给出可靠的深度指标。
- **限制**：
  - 没有类别（48% 是「object」），只能做无类别匹配；
  - 没有 mesh，不评形状；
  - CC BY-NC-ND，不能发布改过的标注。
- **下载**：22 个 tar 约 11–12 GB【推断，按中位 0.51 GB 算】。也可以像这次一样只用 range 请求读 world.gt 和位姿。

### 3.2 大家具和前人对比（ii）

**ARKitScenes 的 BVB-150（3DOD Validation）。** 测试集 50 个，含 3.1 的 22 个 CA-1M 视频，另从剩下的 128 个里用固定种子抽 28 个；开发集再抽 20 个，和前情计划一致。
- **指标**：
  - F1@IoU 0.25/0.5，和 SpatialLM、SceneScript 口径一致（这两篇都因为没有置信度而用 F1，不用 mAP，见 https://arxiv.org/abs/2403.13064 ）；
  - Scan2CAD 式准确率；
  - 中心、尺寸、yaw 误差。
- **基线**：BVB-results 的 blends 重新打分。CuTR、SpatialLM 的数字是另一种设定（单帧，或者 SLAM 点云），只能放在相关工作里定性提一下，不能直接放进同一张表。
- **下载**：annotation+mesh+traj 每景约 45 MB，70 个景约 3 GB；VSI 的 arkitscenes.zip 1.81 GB（https://huggingface.co/datasets/nyu-visionx/VSI-Bench ）。
- **坑**：
  - `sky_direction` 不可靠，要按位姿逐帧定朝向；
  - 原始 .mov 里竖拍视频是横着存的；
  - VSI 的视频已经旋转过并且重采样到 30 FPS，帧对应要核对；
  - 标注 z 朝上，ARKit 相机位姿要和它在同一个坐标系，第一次跑时用一个场景画出来检查。

### 3.3 可选

- **受控形状实验**：在 Blender 里用 ReplicaCAD 渲 3–5 条漫游视频，每条换一种物体摆放。专门评 Hunyuan3D 物体的 F@5%，以及难建模物体（植物、灯）的形状。要加运动模糊和噪声，并说明可能和 VGGT 类模型的训练集重叠。
- **对冲**：填 EmbodiedScan 表单。如果它的 ARKitScenes v2 覆盖 BVB-150，就能在原视频上得到带类别的小物体框。
- **ADT**：只在时间充裕时做。论文图注要写 Meta 的归属声明，发图前先确认许可。

### 3.4 第一周要做的事（10-14 到 10-20）

1. 提交 ScanNet++ 申请（导师手签）和 EmbodiedScan 表单。
2. 下载 VSI meta_info（3 个 json，共约 4 MB）、CA-1M 的 22 个 tar（或者只读 world.gt 和 RT.json）、ARKitScenes 70 个景的 annotation、mesh、traj。
3. 写打分脚本：
   - 按 2.2 分档；
   - 按 2.3 匹配和三类结果；
   - 按 2.5 的 Sim(3)/SE(3) 双版本对齐。

   先在 3 个 BVB 配置的现成 blends 上验证，只用 CPU。

---

## 4. 没核实或不确定的地方

- VSI-Bench 的 50 个 ScanNet++ 场景是否正好是 nvs_sem_val（split 文件不公开）；VSI 视频帧和原始帧（2i）的对应。
- ScanNet++ 下载 yaml 能否按场景 ID 选；每景大小只是用全量大小除出来的。
- EmbodiedScan v2 的 ARKitScenes 扫描列表，以及表单审批时长。
- ADT 序列数，文档写 236、论文写 200；20 个序列的大小是估的；论文图里放 ADT 渲染图是否违反 §3。
- CA-1M 论文的「1.8M validation frames」和已发布的约 68K 帧不一致；22 个视频的 tar 大小是按中位数估的。
- iPad/iPhone 视频的卷帘快门程度、ARKitScenes 是否打码，都没有官方说明。
- hssd-scenes 能否直接导入 Blender；Habitat 和 ReplicaCAD 的轴约定；Pi3X 的训练集。
- 2.2 到 2.4 的阈值（0.2/0.5/1.5 m、d̂≤0.5、ρ≤1.5、宽松门限）是本方案自定的，没有前人用过完全相同的定义。

---

## 来源

**ARKitScenes**
- [A0] https://github.com/apple/ARKitScenes
- [A1] https://github.com/apple/ARKitScenes/blob/main/threedod/benchmark_scripts/utils/taxonomy.py
- [A2] https://github.com/apple/ARKitScenes/tree/main/threedod （README、eval_utils；框坐标是本次实测）
- [A3] https://github.com/apple/ARKitScenes/blob/main/raw/README.md （.mov 文件头是本次用 range 请求读的）
- 划分：https://github.com/apple/ARKitScenes/blob/main/threedod/3dod_train_val_splits.csv
- sky_direction：https://github.com/apple/ARKitScenes/blob/main/depth_upsampling/dataset.py ；https://huggingface.co/datasets/rerun/arkitscenes-rrd

**CA-1M**
- [C1] https://github.com/apple/ml-cubifyanything （README、data/val.txt、data/train.txt、data/LICENSE_DATA、cubifyanything/dataset.py）；CDN：https://ml-site.cdn-apple.com/datasets/ca1m/val/
- [C2] https://arxiv.org/abs/2412.04458
- [C3] 同 [C1]（orientation.py）

**ScanNet++**
- [S1] https://arxiv.org/abs/2308.11417
- [S2] https://kaldir.vc.in.tum.de/scannetpp/documentation
- [S3] https://kaldir.vc.in.tum.de/scannetpp/changelog
- [S4] https://kaldir.vc.in.tum.de/scannetpp/benchmark/insseg
- [S5] https://github.com/scannetpp/scannetpp ，issues #31、#196
- [S6] https://kaldir.vc.in.tum.de/scannetpp/static/scannetpp-terms-of-use.pdf
- [S7] https://github.com/scannetpp/scannetpp/issues （#136、#176、#190、#195、#208、#211、#213、#214）

**ScanNet**
- [N1] https://arxiv.org/abs/1702.04405
- [N2] https://arxiv.org/abs/2204.07761 ；https://github.com/ScanNet/ScanNet/tree/master/BenchmarkScripts/ScanNet200
- [N3] https://github.com/ScanNet/ScanNet
- [N4] https://github.com/torch-points3d/torch-points3d/blob/master/scripts/datasets/download-scannet.py
- [N5] https://github.com/facebookresearch/votenet/blob/main/scannet/load_scannet_data.py
- [N6] https://arxiv.org/abs/1811.11187

**EmbodiedScan**
- [E1] https://arxiv.org/abs/2312.16170
- [E2] https://github.com/OpenRobotLab/EmbodiedScan （configs/detection/mv-det3d_8xb4_embodiedscan-3d-284class-9dof.py）
- [E3] 同仓库的 README 和 data/README

**Aria 系**
- [D1] https://facebookresearch.github.io/projectaria_tools/docs/tech_spec/hardware_spec
- [D2] https://arxiv.org/abs/2306.06362
- [D3] https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset
- [D4] https://github.com/facebookresearch/projectaria_tools （data/gen1/aria_digital_twin_test_data）
- [D5] https://www.projectaria.com/datasets/adt/license/
- [D6] https://www.projectaria.com/datasets/adt/
- [D7] projectaria_tools 的 ADT quickstart notebook（同 [D4] 仓库）
- [D8] https://www.projectaria.com/datasets/aeo/

**Replica / ReplicaCAD**
- [R1] https://github.com/facebookresearch/Replica-Dataset ；https://arxiv.org/abs/1906.05797
- [R2] https://github.com/kxhit/vMAP
- [R3] https://arxiv.org/abs/2011.02523
- [R4] https://huggingface.co/datasets/ai-habitat/ReplicaCAD_dataset

**其他合成数据**
- [H1] https://arxiv.org/abs/2306.11290 ；https://huggingface.co/datasets/hssd/hssd-scenes ；https://huggingface.co/datasets/hssd/hssd-hab
- [Y1] https://github.com/apple/ml-hypersim
- [Y2] https://arxiv.org/abs/2011.02523
- [F1] https://arxiv.org/abs/2011.09127
- [F2] https://arxiv.org/abs/2009.09633
- [F3] https://dlr-rm.github.io/BlenderProc/examples/datasets/front_3d/README.html
- [I1] https://github.com/princeton-vl/infinigen
- [I2] https://arxiv.org/abs/2406.11824
- [G1] https://huggingface.co/datasets/spatialverse/InteriorGS

**MultiScan / 3RScan**
- [M1] https://proceedings.neurips.cc/paper_files/paper/2022/file/3b3a83a5d86e1d424daefed43d998079-Paper-Conference.pdf
- [M2] https://3dlg-hcvc.github.io/multiscan/read-the-docs/dataset/files/annotation.html
- [M3] https://huggingface.co/datasets/3dlg-hcvc/MultiScan
- [T1] https://github.com/WaldJohannaU/3RScan
- [T2] https://arxiv.org/abs/2312.16170 附录 B.1
- [T3] https://waldjohannau.github.io/RIO/

**VSI-Bench**
- https://huggingface.co/datasets/nyu-visionx/VSI-Bench
- https://arxiv.org/abs/2412.14171
- https://github.com/vision-x-nyu/thinking-in-space/tree/main/data/meta_info

**指标文献**：见第 2 节正文里的各条链接。
