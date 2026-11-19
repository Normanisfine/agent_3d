from smallobj import configs

IDS = configs.CA1M_IDS


def test_split_sizes_disjoint():
    s = configs.make_splits(IDS, seed=20261020)
    assert (len(s["dev"]), len(s["test"]), len(s["spare"])) == (5, 15, 2)
    allids = s["dev"] + s["test"] + s["spare"]
    assert len(set(allids)) == 22 and set(allids) == set(IDS)


def test_split_deterministic():
    assert configs.make_splits(IDS, seed=20261020) == configs.make_splits(IDS, seed=20261020)


def test_thresholds_values():
    t = configs.default_thresholds()
    assert t["iou_strict"] == 0.25
    assert t["dhat_strict"] == 0.5
    assert t["size_ratio"] == [0.67, 1.5]
    assert t["dhat_loose"] == 1.0
    assert t["iou_loose"] == 0.1
    assert t["visible_min_px"] == 100
    assert t["bin_edges_m"] == [0.2, 0.5, 1.5]
    assert "wall" in t["structural_categories"]


def test_ids_are_the_22_overlap_videos():
    assert len(IDS) == 22 and IDS[0] == "42897538" and IDS[-1] == "47430475"


def test_structural_covers_real_variants():
    s = set(configs.default_thresholds()["structural_categories"])
    assert {"wall", "floor", "ceiling", "doorframe", "door_frame"} <= s
    assert "ceiling light" not in s and "switch" not in s and "outlet" not in s  # 10-23：门改为结构件，开关插座保留


def test_shell_rule_and_structural_doors():
    t = configs.default_thresholds()
    assert {"door", "window", "window sill", "baseboard", "base board"} <= set(t["structural_categories"])
    assert t["shell_max_thickness_m"] == 0.06 and t["shell_min_length_m"] == 1.5
    assert t["loose_size_ratio_max"] == 3.0


def test_protocol_frozen_g1():
    # 10-27 G1 定（Yifan："评测标准按照你的来"）：贪心配对、"建对了"10 cm 下限、"建出来"另加 30 cm 绝对门槛
    import json
    from pathlib import Path
    t = configs.default_thresholds()
    assert t["match_mode"] == "greedy" and t["strict_floor_m"] == 0.10 and t["loose_abs_m"] == 0.30
    frozen = json.loads((Path(__file__).resolve().parents[1] / "configs" / "thresholds.json").read_text())
    assert frozen == t
