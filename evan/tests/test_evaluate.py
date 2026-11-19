import numpy as np
import pytest

from smallobj import boxes, configs, evaluate

# 判据本身的边界（d̂、IoU、尺寸比）：不含 10-27 G1 加的 10 cm 下限、30 cm 门槛和贪心配对，这些在后面单独测
TH = {k: v for k, v in configs.default_thresholds().items() if k not in ("match_mode", "strict_floor_m", "loose_abs_m")}


def cube(oid, x=0.0, side=0.08, cat="cup"):
    return boxes.record(oid, cat, center=(x, 0.0, 0.5), yaw=0.0, size=(side, side, side))


def outcome_at(shift_m, key):
    rows = evaluate.outcomes([cube("p", x=shift_m)], [cube("g")], TH)
    return rows[0][key]


def test_gt_vs_gt_all_correct():
    gts = [cube("a"), boxes.record("b", "sofa", (2, 1, 0.4), 0.3, (2.0, 0.9, 0.8)),
           boxes.record("c", "book", (-1, 2, 0.7), 1.0, (0.25, 0.18, 0.04))]
    rows = evaluate.outcomes([dict(g, source="pred") for g in gts], gts, TH)
    assert all(r["I"] == "correct" and r["D"] == "correct" for r in rows)


def test_iou_flip_at_4_8cm():
    assert outcome_at(0.047, "I") == "correct"
    assert outcome_at(0.049, "I") == "misplaced"


def test_dhat_flip_at_3_46cm():
    assert outcome_at(0.034, "D") == "correct"
    assert outcome_at(0.035, "D") == "misplaced"


def test_loose_edge_6_93cm():
    assert outcome_at(0.069, "D") == "misplaced"
    assert outcome_at(0.070, "D") == "missed"


def test_size_ratio_breaks_D():
    big = boxes.record("p", "cup", (0, 0, 0.5), 0.0, (0.13, 0.13, 0.13))  # 最长边比 1.625 > 1.5
    rows = evaluate.outcomes([big], [cube("g")], TH)
    assert rows[0]["D"] == "misplaced"


def test_bins_edges():
    edges = TH["bin_edges_m"]
    assert evaluate.size_bin(boxes.record("a", "x", (0, 0, 0), 0, (0.19, 0.1, 0.1)), edges) == "XS"
    assert evaluate.size_bin(boxes.record("a", "x", (0, 0, 0), 0, (0.2, 0.1, 0.1)), edges) == "S"
    assert evaluate.size_bin(boxes.record("a", "x", (0, 0, 0), 0, (0.1, 0.5, 0.1)), edges) == "M"
    assert evaluate.size_bin(boxes.record("a", "x", (0, 0, 0), 0, (0.1, 0.1, 1.5)), edges) == "L"


def test_iou_rotated_overlap():
    a = boxes.record("a", "x", (0, 0, 0), 0.0, (2.0, 2.0, 1.0))
    b = boxes.record("b", "x", (0, 0, 0), np.pi / 4, (2.0, 2.0, 1.0))
    # 两个正方形转 45° 的重叠是正八边形，面积 8(√2−1)
    inter = 8 * (np.sqrt(2) - 1)
    assert evaluate.iou3d(a, b) == pytest.approx(inter / (8 - inter), rel=1e-6)


def test_one_to_one_matching():
    gts = [cube("g1", x=0.0), cube("g2", x=0.05)]
    preds = [cube("p1", x=0.051)]  # 只能配给一个真值
    rows = evaluate.outcomes(preds, gts, TH)
    got = {r["gt_id"]: r["D"] for r in rows}
    assert got == {"g2": "correct", "g1": "missed"}


def test_structural_excluded():
    preds = [dict(cube("p1"), category="architecture/room"), dict(cube("p2"), category="decor/cups"),
             dict(cube("structure/back_left"), category="structure"), dict(cube("p4"), category="floor"),
             dict(cube("exterior/door"), category="fixture"), dict(cube("decor/clock"), category="fixture")]
    kept = evaluate.filter_predictions(preds)
    assert [p["object_id"] for p in kept] == ["p2", "decor/clock"]


def test_summarize_recall_by_bin():
    rows = [{"bin": "XS", "I": "correct", "D": "correct"}, {"bin": "XS", "I": "missed", "D": "missed"},
            {"bin": "L", "I": "misplaced", "D": "correct"}]
    s = evaluate.summarize(rows)
    assert s["XS"]["n"] == 2 and s["XS"]["recall_I"] == 0.5 and s["XS"]["missed_D"] == 0.5
    assert s["L"]["recall_D"] == 1.0 and s["L"]["misplaced_I"] == 1.0


def test_loose_requires_size_compat():
    cabinet = boxes.record("g", "cabinet", (0, 0, 1.0), 0.0, (0.5, 1.3, 2.0))
    book = boxes.record("p", "book", (0, 0, 1.0), 0.0, (0.03, 0.2, 0.25))  # 柜子里的一本书，不能算"柜子建坏了"
    assert evaluate.outcomes([book], [cabinet], TH)[0]["D"] == "missed"


def test_small_pred_not_stolen_by_large_gt():
    cabinet = boxes.record("g_cab", "cabinet", (0, 0, 1.0), 0.0, (0.5, 1.3, 2.0))
    book_gt = boxes.record("g_book", "book", (0.05, 0.1, 1.2), 0.0, (0.03, 0.2, 0.25))
    book_pred = boxes.record("p_book", "book", (0.06, 0.1, 1.2), 0.0, (0.03, 0.2, 0.25))
    got = {r["gt_id"]: r["D"] for r in evaluate.outcomes([book_pred], [cabinet, book_gt], TH)}
    assert got == {"g_book": "correct", "g_cab": "missed"}


def test_absolute_loose_gate_is_optional():
    gt = cube("g")                       # 8 cm 的杯子
    pred = cube("p", x=0.15)             # 偏了 15 cm
    assert evaluate.outcomes([pred], [gt], TH)[0]["D"] == "missed"
    th_abs = dict(TH, loose_abs_m=0.30)
    assert evaluate.outcomes([pred], [gt], th_abs)[0]["D"] == "misplaced"
    far = cube("p2", x=0.35)
    assert evaluate.outcomes([far], [gt], th_abs)[0]["D"] == "missed"


def test_greedy_keeps_correct_pair():
    # p1 正好在 g1 上，也在 g2 的宽松门槛内；p2 只在 g1 的宽松门槛内
    from smallobj import configs
    th = configs.default_thresholds()
    g1 = boxes.record("g1", "box", (0.0, 0, 0.5), 0, (0.4, 0.4, 0.4))
    g2 = boxes.record("g2", "box", (0.3, 0, 0.5), 0, (0.4, 0.4, 0.4))
    p1 = boxes.record("p1", "box", (0.0, 0, 0.5), 0, (0.4, 0.4, 0.4))
    p2 = boxes.record("p2", "box", (-0.3, 0, 0.5), 0, (0.4, 0.4, 0.4))
    hung = evaluate.outcomes([p1, p2], [g1, g2], dict(th, match_mode="hungarian"))
    assert [r["D"] for r in hung] == ["misplaced", "misplaced"]
    greedy = evaluate.outcomes([p1, p2], [g1, g2], dict(th, match_mode="greedy"))
    assert [r["D"] for r in greedy] == ["correct", "missed"]
    assert evaluate.match([p1, p2], [g1, g2], dict(th, match_mode="greedy")) == [(0, 0)]


def test_strict_floor():
    from smallobj import configs
    th = configs.default_thresholds()
    g = boxes.record("g", "cup", (0, 0, 0.8), 0, (0.08, 0.08, 0.08))
    p = boxes.record("p", "cup", (0.06, 0, 0.8), 0, (0.08, 0.08, 0.08))
    assert evaluate.outcomes([p], [g], dict(th, strict_floor_m=0.10))[0]["D"] == "correct"
    assert evaluate.outcomes([p], [g], dict(th, strict_floor_m=0.0))[0]["D"] == "misplaced"
    assert evaluate.outcomes([p], [g], th)[0]["D"] == "correct"  # 10-27 冻结的正式口径带 10 cm 下限


def test_frozen_protocol_outcomes():
    # 冻结口径下一个 8 cm 的杯子：偏 6 cm 算建对了（10 cm 下限），偏 15 cm 算建出来但没摆准（30 cm 门槛），偏 35 cm 算漏了
    th = configs.default_thresholds()
    gt = cube("g")
    assert [evaluate.outcomes([cube("p", x=x)], [gt], th)[0]["D"] for x in (0.06, 0.15, 0.35)] == ["correct", "misplaced", "missed"]
