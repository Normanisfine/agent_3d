# 审稿修改清单 D：10-steps、11-team、12-timeline、13-risks、14-train、15-related、16-reading、17-gloss

上一个写作 agent 还没开始改就被限流打断了。**每条先看文件现状，已改好的跳过**，没改的按资料核实后再改（审稿人给的改写句也要核）。逐步架构图右边被裁的问题已经在 assets/review.css 末尾用补丁修了，不用改 svg 的 width。

设计文档 /home/user/6220/Project/ubuntu_final_project/docs/design.md 已更新：第 5 节运行上限等 A1 开发集中位数出来再定（configs/run_caps.json）；9.4 节 10/20 前定阈值只用"真值对真值"和"检测器直接输出对真值"做合理性检查，不拿 agent 输出调；9.5 节漏斗第 ① 关按该组实际用到的帧算；第 12 节"10/20 定死测试集和阈值"放在 10/14–19 那行；第 13 节退路是给 harness 打补丁、所有组一样、不许人工干预、砍 A4，新增第 10 个风险 Pi3X/π³ 同源；**新增 15b 文件约定**（input.mp4、gt/boxes.json、configs/*.json、perception/<scene>/bundle/、inventory.json 和 inventory_clean.json、gen/、runs/<arm>/<scene>/<seed>/{scene.blend, run_log.json, export/objects.json}、results/；export/objects.json 由 Yujing 的评测脚本导出，P0 直接写）。人员配色：Yifan 蓝 f1、Mingjian 黄 f3、Yujing 绿 f2。

## 第 12、13 章
1. 13-risks 第 56–59 行"为什么不太担心"框：删第二段；第一段只留"之前用 Haiku 5.5 跑通过 office48（67 轮）"，加"退路是给 harness 打补丁，所有组一样，不缩减实验组"。
2. 13.3 补第 10 个风险：π³ 训练用过 ARKitScenes 和 ScanNet++（π³ 论文 §3.4），Pi3X 本身未核实；对策：报告注明几何绝对值可能偏乐观，所有组共用感知，组间比较不受影响；可选的 ScanNet++ 和 VSI 开发集同样受影响。三处"九个风险"和相关图注一起改。
3. 12-timeline："定死测试集和阈值"移到 10/14–10/19 行，闸门栏补"10/20 测试集和阈值定死"；12.1、12.2、12.3 三张图这个点画在同一位置；11/2 闸门补"ScanNet++ 批没批"；"每个阶段末尾有一个闸门"改"大多数阶段"。

## 第 10、11 章
4. 11.3 文件表照 15b 改；11.2 交接图补"Mingjian → Yujing：bundle/（相机轨迹，评测对齐和'看得见'要用）"。
5. 10.1 依赖图补 S5→S7、S6→S7 箭头，第 80 行改"等三样东西"；"bundle/"标签挪到 S4→S7 那条线旁边。11.1 五个文件名标签贴到各自箭头上方。
6. 10.6"在开发集上看分布"按更新后的 9.4 节写清；图和图注里"提示词"不属于 10/20 封存（A2、A3 提示词 S9 才写，之后也只在开发集上调）。
7. SAM 3 权限：AHa-3D 的 Observe 一步本身就要 SAM 3，卡 S1、S4、S7，最晚日期改"立即，S7 之前必须到位"；可补一句：Yifan 之前在这台机器上跑过 AHa-3D 的 SAM 3，HF 账号可能已有权限，先查。
8. 10.5 干净对照要另跑一遍 SAM 3（物体类别做提示），bundle/ 里只有结构类掩码；图上另画"SAM 3（物体提示）"，注明"提示词设计文档没定，Mingjian 定"。
9. 改成待定或推断：第 121 行 fal 自费记在 Mingjian 名下 → "谁出待定"；第 452、472 行和 11 章第 46 行高清帧消融归 Mingjian → "Mingjian 准备降采样版清单和生成，Yifan 跑 agent（按我们的理解）"；13.1 第 45 行"补丁的时间和额度从 A4 里出"加"按我们的理解"。
10. 10-steps 第 419 行、17-gloss 第 45 行：验收四项，补"穿进支撑面不超过 1 cm"。
11. S10 的 A4 补"如果 10/26 走了退路，A4 已经砍掉"。

## 第 14 章
12. 训练数据 GPU 估算补上 85 个场景的感知（Pi3X、SAM 3、Boxer），按 04 号笔记每场景约 0.5 GPU·时（标假设）再加约 42.5 小时，合计约 81 小时：补贴价约 20 美元、非补贴价约 91 美元，后者超过一个人的额度，写出来（python3 -I 自己算）。
13. 14.2"如比 d̂"改"按归一化中心距离比"；第 157 行 220 字段落拆开。

## 第 15、17 章
14. 15.1 点阵图：LiteReality-Agent 补点或标"原文没写清"；CoDimRecon 注"生成只作参考"；"我们"补大件空心点；第 73 行 179 字段落拆开。
15. 17-gloss 第 34 行改"CA-1M 论文评测用 7 自由度；我们用哪种见第 8 章"；规范空间统一写"朝向和尺度未知"（10.8 第 434 行"朝向随意"一并改）。

## 第 16 章
16. 16.2 全组必读最前面加两份：课程提案说明（课程仓库 03-final-project/M2-proposal/proposal-instructions.pdf）和设计文档 docs/design.md；组员打不开本地路径，写"找 Yifan 要"。
17. Mingjian：SAM 3 升必读（重点 §2 概念提示）；φ-RIE 升必读（place_mesh 照抄它）；Hunyuan3D 2.0 论文降参考，"仓库 README 的 2mini 用法和低显存模式"保留必看。
18. Boxer"重点看"加附录 0.C.3（mAP by Object Size）和 0.C.2（和 SAM3+SAM3D 对比），谁读"Mingjian、Yujing"。
19. GATOR"重点看"加附录 A.4 Agent Refinement、D.5 Ablation Protocol，注"Yifan 细读，A4 照它"。
20. BVB 从参考升推荐，给 Yujing（要重打分 BVB 的 .blend）。
21. 新条目（核实后放）：RecGen arXiv 2604.27106（表 S3），给 Mingjian 参考；OVOW arXiv 2606.31388（too_small 约 200 px 规则来源），给 Mingjian 参考；PARCC 入门 https://parcc.upenn.edu/training/getting-started/ 给 Mingjian；fal 的 SAM 3D 接口页给 Mingjian；Codex CLI `codex exec` 文档和 Claude Code headless 文档给 Yifan；SimuScene 2606.03994 可选参考。
22. 减负：GATOR 和 LIVIN 全组只读摘要加指定的表，细读分给一个人（GATOR 给 Yifan，LIVIN 给 Yujing）。
23. 小问题：16.2 图下括号只括感知、agent 建场景、检查三块，"清单"和"生成与摆放"标"我们加的"；16.3 TIDE 和 Omni3D 两行对调（对齐 → 匹配 → 判结局）；SAM 3D"布局评测要点图"改"Table 3：物体位姿的定量对比"；DSH 核实全称再解释，核不到写"作者自己的 harness"；Lucida 改"它的摆放模块 GizmoAct 在物体级位姿上和 SAM 3D 比过，是 place_mesh 的另一种做法"；Omni3D 仓库已归档注明；π³ 易错点补"组间比较不受影响；ScanNet++ 和 VSI 开发集同样受影响"。
24. 13.4"Claude 只复跑 2 组"和"重复缩到 3 场景"标签太近，缩短；A4 和高清帧消融两层深色下太像，换一层颜色；10-steps 第 176 行 170 字段落拆开。
