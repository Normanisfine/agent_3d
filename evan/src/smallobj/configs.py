"""划分和阈值：设计文档第 8、9 节定的值。生成后写进 configs/，之后不再改。"""
import random

from smallobj.ca1m import SHELL_DEFAULT, STRUCTURAL_DEFAULT

# CA-1M 验证集和 BVB-150 重叠、覆盖率 ≥80% 的 22 个视频（research/notes/03-datasets-metrics.md §1.3）
CA1M_IDS = [
    "42897538", "42897647", "42898849", "42899617", "42899698", "42899712", "42899725", "42899729",
    "44358442", "44358451", "45261121", "45261575", "45663164", "47115469", "47115525", "47115543",
    "47204552", "47331068", "47331262", "47331319", "47334239", "47430475",
]
SEED = 20261020


def make_splits(ids, seed=SEED):
    ids = sorted(ids)
    random.Random(seed).shuffle(ids)
    return {"seed": seed, "dev": ids[:5], "test": ids[5:20], "spare": ids[20:22]}


def default_thresholds():
    return {
        "iou_strict": 0.25,
        "dhat_strict": 0.5,
        "size_ratio": [0.67, 1.5],
        "dhat_loose": 1.0,
        "iou_loose": 0.1,
        "visible_min_px": 100,
        "bin_edges_m": [0.2, 0.5, 1.5],
        "structural_categories": sorted(STRUCTURAL_DEFAULT),
        "shell_max_thickness_m": SHELL_DEFAULT[0],
        "shell_min_length_m": SHELL_DEFAULT[1],
        "shell_keep_categories": ["carpet", "mat", "rug"],
        "loose_size_ratio_max": 3.0,
        "align_residual_max_m": 0.15,
        # 10-27 G1 冻结：贪心配对、"建对了"的距离下限 10 cm、"建出来"另加 30 cm 绝对门槛（设计 §9.4）
        "match_mode": "greedy",
        "strict_floor_m": 0.10,
        "loose_abs_m": 0.30,
        "align_scale_range": [0.7, 1.4],
    }
