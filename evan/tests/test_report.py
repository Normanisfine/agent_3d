from smallobj import report


def test_funnel_counts_monotone_and_correct():
    rows = [  # 判据 D 的结局
        {"gt_id": "a", "bin": "XS", "D": "correct"},
        {"gt_id": "b", "bin": "XS", "D": "misplaced"},
        {"gt_id": "c", "bin": "XS", "D": "missed"},
        {"gt_id": "d", "bin": "L", "D": "correct"},
    ]
    vis = {"a": {"visible": True}, "b": {"visible": True}, "c": {"visible": False}, "d": {"visible": True}}
    f = report.funnel_counts(rows, vis, key="D")
    assert f["XS"] == {"n": 3, "visible": 2, "built": 2, "correct": 1}
    assert f["L"] == {"n": 1, "visible": 1, "built": 1, "correct": 1}


def test_built_but_not_visible_still_counts_built():
    rows = [{"gt_id": "a", "bin": "S", "D": "correct"}]
    f = report.funnel_counts(rows, {"a": {"visible": False}}, key="D")
    assert f["S"] == {"n": 1, "visible": 0, "built": 1, "correct": 1}


def test_merge_counts_across_scenes():
    a = {"XS": {"n": 3, "visible": 2, "built": 2, "correct": 1}}
    b = {"XS": {"n": 1, "visible": 1, "built": 0, "correct": 0}, "L": {"n": 2, "visible": 2, "built": 2, "correct": 2}}
    m = report.merge_counts([a, b])
    assert m["XS"] == {"n": 4, "visible": 3, "built": 2, "correct": 1} and m["L"]["n"] == 2


def test_chance_built_is_low_for_far_random_layout():
    from smallobj import boxes, configs
    th = dict(configs.default_thresholds(), loose_abs_m=0.30)
    gts = [boxes.record(f"g{i}", "cup", (i * 2.0, 0, 0.8), 0, (0.08, 0.08, 0.1)) for i in range(5)]
    preds = [boxes.record(f"p{i}", "cup", (i * 2.0 + 0.05, 0, 0.8), 0, (0.08, 0.08, 0.1)) for i in range(5)]
    real, chance = report.chance_built(preds, gts, th, n=30, seed=0, key="D")
    assert real == 1.0
    assert chance < 0.5


def test_plot_recall_writes_png(tmp_path):
    from PIL import Image
    rows = [{"gt_id": "a", "bin": "XS", "I": "missed", "D": "correct"},
            {"gt_id": "b", "bin": "L", "I": "correct", "D": "correct"}]
    out = tmp_path / "recall.png"
    pooled = report.plot_recall({"A1": {"sim3": rows, "noscale": rows[:1]}}, out, "t")
    assert Image.open(out).size[0] > 100
    assert pooled["A1"]["sim3"]["XS"]["recall_D"] == 1.0 and pooled["A1"]["sim3"]["XS"]["recall_I"] == 0.0
    assert "L" not in pooled["A1"]["noscale"]


def test_built_fraction_uses_full_matching_across_bins():
    # 一个预测夹在 XS 和 S 两个真值之间：正式口径是全体真值一起配对，只能配上一个；
    # 分档单独配对会让它在两档各算一次"建出来"（审查发现的敏感性表偏高）
    from smallobj import boxes, configs
    th = configs.default_thresholds()
    gts = [boxes.record("xs", "book", (0.0, 0, 0.8), 0, (0.18, 0.12, 0.03)),
           boxes.record("s", "box", (0.12, 0, 0.8), 0, (0.25, 0.2, 0.15))]
    preds = [boxes.record("p", "book", (0.06, 0, 0.8), 0, (0.21, 0.15, 0.08))]
    xs = report.built_fraction(preds, gts, th, bin="XS")
    s = report.built_fraction(preds, gts, th, bin="S")
    assert xs + s == 1.0
    real, chance = report.chance_built(preds, gts, th, n=5, seed=0, bin="XS")
    assert real == xs


def test_missing_blend_counts_all_missed():
    # 没得到 .blend 的运行照常计入：所有真值记 missed（设计 §5：失败的运行不剔除）
    from smallobj import boxes, configs
    th = configs.default_thresholds()
    gts = [boxes.record("a", "cup", (0, 0, 0.8), 0, (0.08, 0.08, 0.1)),
           boxes.record("b", "sofa", (2, 0, 0.4), 0, (2.0, 0.9, 0.8))]
    rows = report.missed_rows(gts, th)
    f = report.funnel_counts(rows, {"a": {"visible": True}, "b": {"visible": True}})
    assert f["XS"] == {"n": 1, "visible": 1, "built": 0, "correct": 0}
    assert f["L"]["built"] == 0 and all(r["I"] == "missed" for r in rows)


def test_funnel_detected_stage():
    rows = [{"gt_id": "a", "bin": "XS", "D": "correct"}, {"gt_id": "b", "bin": "XS", "D": "missed"},
            {"gt_id": "c", "bin": "XS", "D": "missed"}]
    vis = {k: {"visible": True} for k in "abc"}
    f = report.funnel_counts(rows, vis, key="D", detected={"a": True, "b": True, "c": False})
    assert f["XS"] == {"n": 3, "visible": 3, "detected": 2, "built": 1, "correct": 1}
    assert "detected" not in report.funnel_counts(rows, vis, key="D")["XS"]
    m = report.merge_counts([f, f])
    assert m["XS"]["detected"] == 4 and m["XS"]["n"] == 6


def test_choose_gate_uses_criterion_d_outcome():
    # 计划 Task 10：通过门槛的候选"按判据 D 的结局不比方块版差"。d̂ 稍大但结局同为 correct 的不算更差
    rows = [{"fit": {"sil_iou_mean": 0.55, "primitive_sil_iou": 0.4, "chamfer_obs2mesh_cm": 1.0, "size_ratio": [1, 1, 1],
                     "penetration_m": 0.0}, "longest": 0.2, "gen_dhat": 0.30, "box_dhat": 0.25, "gen_D": "correct", "box_D": "correct"}]
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("calibrate_gate", Path(__file__).resolve().parents[1] / "scripts" / "calibrate_gate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    base = {"sil_iou_min": 0.6, "sil_margin": 0.03, "chamfer_min_m": 0.015, "chamfer_rel": 0.1, "size_ratio": [0.75, 1.25],
            "penetration_max_m": 0.01}
    best, grid = mod.choose_gate(rows, base)
    assert best is not None and best["sil_iou_min"] <= 0.5 and best["n_worse"] == 0
