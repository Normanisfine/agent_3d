# 材质展示版：开发场景 47331262，Opus A1

展示用，不进实验结果。实验的所有运行都是白膜（`appearance: "whitebox"`），打分只看几何。

- **怎么做的。**
  - 底子是开发场景 47331262 的 Opus A1 运行（`runs/A1-claude/47331262/0/scene.blend`）：几何最完整，小物体最多（预测 130 个，XS 建对 .42）。
  - 用 `scripts/showcase_materials.sh` 让 AHa-3D 按原版的 `appearance: "materials"` 做了一次只改材质和灯光的修订。驱动是 Opus 5.5，10-28 02:39 开跑，用了 28 分钟，每周额度 +1 个百分点。
- **几何没动。**
  - agent 自己做了前后核对。
  - 我们另外在 Blender 里核对过：1215 个网格物体名字一样，世界变换一样，顶点数一样。
- **材质。**
  - 用了 75 种材质：先从 AHa-3D 材质库里找，找不到再自己写 Principled BSDF。墙是暖赭色漆，地板是红褐色条形拼木，家具是樱桃木或深色木，沙发和扶手椅是米色皮革，小物体也都上了色。
  - 画框里的画面是近似的，不是视频里的原画。
  - 灯光是窗外日光加室内补光，用 Cycles 渲染。
- **AHa-3D 自己的验收：** 这次材质任务通过了（accepted）。
- **文件。**
  - `triptych_<帧>.jpg`：视频原帧 | AHa-3D 白膜 | 材质版，同一个相机。
  - `front_whitebox_vs_materials.jpg`：剖切正视图，左白膜、右材质。
  - `front_materials.jpg`、`overview_materials.jpg`：材质版大图。
  - 完整输出在 `runs/showcase/47331262_A1_materials/`：`scene.blend`，`stills/`，`compare/` 里 9 张左视频右渲染的对比图，`SUMMARY.md`。
