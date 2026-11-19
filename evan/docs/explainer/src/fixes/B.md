# 审稿修改清单 B：02-aha.html、03-sys.html、06-gen.html、09-cost.html

上一个写作 agent 还没开始改就被限流打断了。**每条先看文件现状，已改好的跳过**，没改的按资料核实后再改（审稿人给的改写句也要核）。AHa-3D 细节在 /home/user/6220/Project/CIS-6220-Deep-Learning-at-Scale/03-final-project/agentic-3d/notes/deep-aha3d.json。

说明：06-gen.html 第 343 行附近的 VIGA 段落主会话已改成 SEIG（arXiv 2606.02580）对 VIGA 的对比实验，保留改动；这一条现在太长（约 278 字），拆成三条：对照设置、结果、作者解释。

设计文档 /home/user/6220/Project/ubuntu_final_project/docs/design.md 已更新：第 5 节运行上限等 A1 在开发集跑出中位数（10/20–10/26）再定，写进 configs/run_caps.json，第 1 周只量额度；第 6 节工具表验收门四条齐全；第 13 节新增 Pi3X/π³ 同源风险（π³ 训练用过 ARKitScenes）；**新增 15b 节文件约定**（3.4 文件表要和它完全一致）。人员配色全页统一：Yifan 蓝 f1、Mingjian 黄 f3、Yujing 绿 f2。

## 第 2 章
1. #b-small 节首"AHa-3D 有意把小物体降级处理"、易错框"作者的设置本来就叫它近似"：把对比实验的任务描述当成了默认设置。改成"从公开材料看，AHa-3D 对小物体的要求本来就放得很低"。节首"定量结果：一个都没有公布"改成"没有任何精度数字（只有对比视频和一张 token 表）"。
2. #b-loop 第 1 步"它看到的就是那 32 帧"是推断，改成"量尺寸和画叠加图都在 Pi3X 那 32 帧上做（约 574×434）；agent 一开始也会看原视频"。
3. #b-loop"验证一共四层"框末句和第 6 步矛盾，改成"几何准不准，除了可选的 source_fit 没有现成的数值指标，主要靠 agent 看图；物理检查的报告要 agent 自己去读"。
4. #b-loop 时序图缺回程箭头：②⑤⑥ 的结果（measurements.json、叠加图、report.json）各加一条回到 agent 的虚线箭头。
5. #b-cost 表"显卡"行改成"作者文档记录在 96 GB RTX PRO 6000 上无界面渲染成功，其他显卡没说明"。
6. 引文先中文再原文：#b-pipeline 的 "triage heuristics, not calibrated"、易错框的 "predicted metres; uncalibrated"。
7. 可选：#b-keep 里 A2 框在 A1 左边，对调。

## 第 3 章
8. #b-flow：P0 单独画一条绕过"④ agent 运行"的箭头，标"P0：不经 agent"（第 3 步文字已这么说）。
9. #b-components：加"P0 流水线"小框（接 inventory.json 和 inventory_clean.json，输出 export/objects.json 和 scene.blend）；Boxer 补一条从 Pi3X 进来的"位姿 + 点图"箭头；"AHa-3D harness（不改）"改成"AHa-3D harness（原有工具和检查不改）"；MIG、mig45 加一句白话。
10. #b-fair 数据分隔图左栏"位姿、点图"那行加注"（π³ 训练用过 ARKitScenes，绝对精度可能偏乐观）"。
11. "生成为什么不卡住"框补：命中缓存时成本仍按一次生成记账；墙钟上限扣不扣等待生成的时间第 1 周定，所有生成组一样。
12. 3.4 文件表照设计文档 15b 改（文件名、谁写谁读、export/objects.json 由评测脚本导出且 P0 直接写、configs/thresholds.json 和 run_caps.json）。
13. 3.3 表里运行上限的时间按更新后的第 5 节写。
14. 按人上色的图（#b-files 目录树等）改成 Yifan 蓝 f1、Mingjian 黄 f3、Yujing 绿 f2，图注一起改。

## 第 6 章
15. 6.4 图注"前三条在设计文档工具表；第四条来自笔记 02"改成"四条都写在设计文档第 6 节工具表里"。
16. 6.5"论文里的证据互相打架"：GizmoAct 表 2 只有 R2S-Object 用 Pi3X 深度，CA-1M 用 LiDAR 加 LingBot-Depth 补全，分开写；"中心误差"改成"ADD-SB 误差"并补一句解释；F1@0.01、FoundationPose 加白话，或收进 details。
17. 6.2 逐步图"⑥ 缓存，返回 job_id"改成"⑥ 缓存，按 job_id 取结果"。
18. 6.5 图注"两条路只在第三格不同"改成"关键差别在第三格"。
19. 6.6 失败去向图：accepted 改普通箭头；backend_error 补一条绿色重试成功箭头（图注说绿色是重试成功）。
20. 第 354 行附近"是剪影上的比较，不是真值上的比较"改成"门只能比剪影：它只拿得到 SAM 3 掩码和 Pi3X 点云，看不到真值"。
21. 第 139 行附近"60×60 像素的杯子"写明是 574 宽的帧；518 ÷ 60 ≈ 8.6，写"加上留边约 8 倍"。

## 第 9 章
22. 9.2 Agentic RSR 条形图：Fable 5.1 是 Anthropic 的 Claude Fable 5.1，条改用 f5，标签写"Claude Fable 5.1"。
23. 9.2 驱动路线图 Codex 那条最后一格"✓ 不用改"和图注矛盾（`.codex/hooks.json` 没随仓库发布，两条路都要补 Stop hook）：改成"要补：Stop hook 配置"，图注第一句改成"审查这一步两条路不同"。
24. 9.1 发给 fal 的箭头"掩码 + 点图"改成"图像 + 掩码 + 点图"。
25. 9.3 图和正文里运行上限的时间按更新后的第 5 节写。
26. 9.1 第 1、3 步超过 120 字，各拆两句。

## 全章
27. 引号统一用 ""，粗体开头后接句号（第 6、9 章现在是 “” 加冒号）。
