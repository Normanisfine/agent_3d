import numpy as np

from smallobj import boxes, configs, score

TH = configs.default_thresholds()


def test_score_predictions_after_alignment_all_correct():
    gts = [boxes.record("g1", "cup", (1.0, 2.0, 218.8), 0.2, (0.08, 0.08, 0.1)),
           boxes.record("g2", "sofa", (-1.0, 0.5, 218.4), 1.1, (2.0, 0.9, 0.8))]
    # 流程坐标 = 真值经过 x' = (R⁻¹(x − t))/s；对齐结果 (s, R, t) 把它变回去
    s, yaw, t = 1.07, 0.4, np.array([0.3, -0.2, 218.0])
    R = boxes.rot_z(yaw)
    preds = [boxes.transform(boxes.transform(g, 0.0, -t), -yaw, (0, 0, 0), scale=1 / s, source="pred") for g in gts]
    out = score.score_predictions(preds, gts, {"s": s, "R": R, "t": t}, TH)
    assert all(r["I"] == "correct" and r["D"] == "correct" for r in out["rows"])
    assert out["summary"]["XS"]["recall_D"] == 1.0 and out["summary"]["L"]["recall_I"] == 1.0
    assert out["n_pred"] == 2


def test_predictions_not_shell_filtered_rug_and_rod_still_match():
    # 预测侧不按几何规则去薄壳：同一根窗帘杆，预测厚 5 cm、真值厚 10 cm，几何规则会只去掉预测一侧；
    # 标明是地毯的真值在 ca1m 里豁免（见 test_ca1m），预测的地毯要能配上它
    gts = [boxes.record("rod", "object", (0.0, 1.0, 2.2), 0.0, (0.1, 2.6, 0.1)),
           boxes.record("rug", "rug", (2.0, 0.0, 0.02), 0.0, (1.53, 0.87, 0.04))]
    preds = [boxes.record("curtain_rod", "fixtures/curtain_rod", (0.0, 1.0, 2.2), 0.0, (0.06, 1.98, 0.05)),
             boxes.record("rug", "decor/rug", (2.0, 0.05, 0.005), 0.0, (1.6, 1.05, 0.01))]
    out = score.score_predictions(preds, gts, {"s": 1.0, "R": np.eye(3), "t": np.zeros(3)}, TH)
    assert out["n_pred"] == 2
    assert all(r["D"] in ("correct", "misplaced") for r in out["rows"])


def test_alignment_check_flags_bad_residual_and_scale():
    assert score.alignment_ok({"s": 1.07, "residual_median_m": 0.04}, TH)
    assert not score.alignment_ok({"s": 1.07, "residual_median_m": 0.40}, TH)
    assert not score.alignment_ok({"s": 2.5, "residual_median_m": 0.04}, TH)


def test_score_inventory_aligns():
    # 清单框和预测一样要先对齐；不做结构件过滤（清单里本来就没有墙和地面）
    gts = [boxes.record("g1", "cup", (1.0, 2.0, 218.8), 0.2, (0.08, 0.08, 0.1)),
           boxes.record("g2", "sofa", (-1.0, 0.5, 218.4), 1.1, (2.0, 0.9, 0.8))]
    s, yaw, t = 1.07, 0.4, np.array([0.3, -0.2, 218.0])
    R = boxes.rot_z(yaw)
    items = [boxes.transform(boxes.transform(g, 0.0, -t), -yaw, (0, 0, 0), scale=1 / s, source="boxer") for g in gts]
    items[1]["object_id"] = "structure/sofa"  # 名字像结构件也不能被去掉
    rows = score.score_inventory(items, gts, {"s": s, "R": R, "t": t}, TH)
    assert [r["D"] for r in rows] == ["correct", "correct"]
