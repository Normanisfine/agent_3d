# 测试集 A1（旧规则，Codex）

- 10 个测试场景（configs/splits.json 的前 10 个），10-26 到 10-27 跑完。
- 驱动：Codex CLI，gpt-6.1-sol，推理强度 medium。前 9 个场景用 CLI 0.162.0-alpha.17.2，最后 1 个（47204552）扩展升级后用 0.164.0-alpha.11.1。
- 旧规则：每次最多 64 分钟、184 次工具调用，提示词里"一个阶段修约 3 次还不过就停"。10-27 起主实验改为 AHa-3D 原版规则（不设运行上限，修复轮数按 AHa-3D 默认的 repair_budget 3）、Opus 5.5 驱动，这一组保留为对照。
- AHa-3D 自己的验收：10 次都没通过（按 AHa-3D 自己的只读判定 `acceptance.evaluate`；10-27 之前按 SUMMARY.md 的字面判断，把 44358442 误记成通过）。42898849 在最后的验收检查时被外部结束（状态 interrupted，场景已存好，照常打分）。
- 按物体合并的判据 D（Sim(3) 对齐）：XS 459 个，建对 10%、建了没摆准 32%、漏掉 58%；S 568 个：20% / 36% / 44%；M 390 个：27% / 24% / 48%；L 190 个：29% / 20% / 51%（见 summary.json）。
- 文件由 `scripts/report_checkpoint.py --split test --out results/test_a1` 生成；渲染图在 `results/renders/`（按大小上色）和 `results/renders/color/`（颜色取自视频）。
