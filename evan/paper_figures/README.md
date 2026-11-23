# 论文里小物体部分的图

论文只有一篇：组里的稿子 `third_party/agent_3d/paper/paper_file`（分支 `evan/small-object-additions`）。这个目录只放小物体部分的图和它们的中间文件，
脚本在 `scripts/paper/`。11-22 试过单独写一篇小物体的稿子，Yifan 说不要两篇，已经删掉、内容并进组里的稿子。

重新生成（都在项目根目录跑；除了材质版，都不需要 agent 额度）：

```bash
source scripts/env.sh
PYTHONPATH=src .runtime/venv/bin/python scripts/paper/figure_data.py     # figures/data.json：重新配对一遍，和已存的打分逐档核对
.runtime/venv/bin/python scripts/paper/make_charts.py                    # figures/results.pdf（三栏组合图）
PYTHONPATH=src .runtime/venv/bin/python scripts/paper/qualitative.py --top 2 --overview --samples 128   # figures/qual/（原始渲染，不进 git）
bash scripts/paper/run_materials.sh runs/A5-claude/<房间>/0 ...          # 材质版（agent 运行，每个房间约 6 美元、半小时到一小时）
PYTHONPATH=src .runtime/venv/bin/python scripts/paper/materials_views.py # 材质版从同一机位渲染 → figures/qual/<房间>/MAT_<k>.png
.runtime/venv/bin/python scripts/paper/pipeline_assets.py                # 架构图里的小图 → figures/pipeline/
(cd paper/smallobj/pipeline && ../../../.runtime/tex/tectonic system.tex) # 架构图 system.pdf
.runtime/venv/bin/python scripts/paper/assemble_panels.py                # figures/panels/*.jpg，并把论文用到的图拷进组里的稿子
```

- 对比图统一用一套灯光和中性材质，只有 50 cm 以下的实例按评测结果上色（蓝：建对；橙：配上但摆错；绿：没有对应的标注）；最后一列是材质版。
- 机位：房间 1、2、3、6 取能看到最多 50 cm 以下标注目标的那一帧；房间 4、5 那一帧对着空墙，换成第二候选（`assemble_panels.py` 里的 `VIEW`）。
- 图表版式参考 github.com/ChenLiu-1996/figures4papers（竖条、无网格、本文方法深蓝）。
