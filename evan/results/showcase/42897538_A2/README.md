# 材质展示版：测试场景 42897538，Opus A2

展示用，不进实验结果。实验的所有运行都是白膜（`appearance: "whitebox"`），打分只看几何。

- **怎么做的。**
  - 底子是测试场景 42897538 的 Opus A2 运行（`runs/A2-claude/42897538/0/scene.blend`）。这个场景五组里它最完整：客厅连着走廊和一角厨房，预测 54 个物体。它和开发场景 47331262 是不同的房间。
  - 用 `scripts/showcase_materials.sh` 让 AHa-3D 按原版的 `appearance: "materials"` 做了一次只改材质和灯光的修订。驱动是 Opus 5.5，10-28 08:44 开跑，用了 53 分钟，每周额度 +2 个百分点。
  - 这次要求材质版按白膜图的视频机位、用同样的帧号出图，所以三联图三栏的相机完全一样。
- **几何没动。**
  - agent 自己做了前后核对。
  - 我们另外在 Blender 里核对过：310 个网格物体名字一样，世界变换一样，顶点数一样。新增的只有 9 盏灯。
- **材质。**
  - 墙、门窗木作、地板、不锈钢、电视屏这几类用的是 AHa-3D 材质库的材质。门用的是库里蜂蜜色橡木的调亮版，配视频里偏橙的木门。
  - 其余的材质对着视频帧自己写 Principled BSDF：两组沙发是米色皮革，小沙发上是格子靠垫，三人沙发上是淡紫色灯芯绒靠垫，茶几和电视柜是黑棕色。地毯是程序化的波斯纹样，象牙底、玫瑰色边。茶几上的盘子、饼干、纸巾盒、传单这些小物体也都上了色。
  - 网格没有 UV，花纹都是程序化的，没有逐像素对贴图。
  - 灯光是阴天日光：窗外是天空和草地，窗洞里放了门户光，室内加了补光，吊灯也打亮了。用 Cycles 渲染，GPU，128 采样。
- **AHa-3D 自己的审查。**
  - 独立图像审查（Codex）判最终版 v010 为 accepted，只留一条不阻塞的意见：客厅地毯比视频里偏浅、偏粉。
  - AHa-3D 的审查适配器没有存成正式验收记录。原因是还有不阻塞的意见和没审的方面（几何不在这次范围里），原始判定在 `runs/showcase/42897538_A2_materials/evidence/`。
- **文件。**
  - `triptych_<帧>.jpg`：视频原帧 | AHa-3D 白膜 | 材质版，同一个相机。123 是台灯和电视，246 是小沙发、窗和地毯，431 是小沙发近景，616 是茶几和三人沙发。
  - `overview_whitebox_vs_materials.jpg`、`front_whitebox_vs_materials.jpg`：剖切俯视图和正视图，左白膜、右材质。
  - `overview_materials.jpg`、`front_materials.jpg`、`interior_materials_f000493.jpg`：材质版大图。
  - 完整输出在 `runs/showcase/42897538_A2_materials/`：`scene.blend`；`stills/` 里 23 张图；`compare/` 里 16 张左视频右渲染的对比图，覆盖整段视频；`SUMMARY.md`。AHa-3D 的工作目录在 `aha_scene/`、`aha_delivery/`，从 `third_party/aha-3d/` 移出来，免得同一个视频的实验运行看到。所以 SUMMARY 里写的 `scenes/42897538_showcase_mat_a2/` 现在对应 `aha_scene/`。
