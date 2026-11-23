import numpy as np

from smallobj import tiles


def test_windows_cover_frame_with_half_overlap():
    # 1024×768 的高清帧切 3×3，每个窗口占一半宽高，相邻窗口重叠一半（SceneRig 第 2 层是 1/3 窗口放大再检测）
    wins = tiles.windows(1024, 768, n=3, frac=0.5)
    assert len(wins) == 9
    assert wins[0] == (0, 0, 512, 384) and wins[-1] == (512, 384, 1024, 768)
    assert all((x1 - x0, y1 - y0) == (512, 384) for x0, y0, x1, y1 in wins)
    cover = np.zeros((768, 1024), bool)
    for x0, y0, x1, y1 in wins:
        cover[y0:y1, x0:x1] = True
    assert cover.all()
    assert tiles.windows(1024, 768, n=1) == [(0, 0, 1024, 768)]


def test_cut_by_inner_edge():
    # 掩码碰到窗口在画面内部的那条边：物体被窗口切开了，相邻窗口里有完整的，这个丢掉；碰到画面本身的边不算
    m = np.zeros((384, 512), bool)
    m[100:150, 0:30] = True
    assert tiles.cut_by_inner_edge(m, (256, 0, 768, 384), 1024, 768)
    assert not tiles.cut_by_inner_edge(m, (0, 0, 512, 384), 1024, 768)
    m2 = np.zeros((384, 512), bool)
    m2[100:150, 200:260] = True
    assert not tiles.cut_by_inner_edge(m2, (256, 192, 768, 576), 1024, 768)


def test_paste_back_to_frame():
    m = np.zeros((384, 512), bool)
    m[10:20, 30:40] = True
    full = tiles.paste(m, (256, 192, 768, 576), 1024, 768)
    assert full.shape == (768, 1024) and full.sum() == 100
    assert full[202:212, 286:296].all()


def _det(label, score, y0, y1, x0, x1, source="tile"):
    m = np.zeros((60, 80), bool)
    m[y0:y1, x0:x1] = True
    return {"label": label, "score": score, "mask": m, "source": source}


def test_dedupe_keeps_full_frame_and_adds_new_tile_finds():
    # 整帧的检测一个不动（和旧干净对照完全一样，消融"只看整帧"才可比）；窗口的只在和已有的都不重复时才加，
    # 窗口之间重复的留高分的
    dets = [_det("cup", 0.6, 10, 20, 10, 20, "full"), _det("cup", 0.55, 10, 20, 10, 21, "full"),  # 整帧自己重复也都留
            _det("cup", 0.9, 10, 20, 11, 21),                                                   # 和整帧的重复：丢
            _det("book", 0.7, 10, 20, 10, 20),                                                  # 不同类别：留
            _det("cup", 0.8, 40, 50, 60, 70), _det("cup", 0.85, 40, 50, 61, 71)]                # 窗口之间重复：留高分的
    kept = tiles.dedupe(dets, iou_min=0.5)
    assert sorted((d["label"], d["score"], d["source"]) for d in kept) == [
        ("book", 0.7, "tile"), ("cup", 0.55, "full"), ("cup", 0.6, "full"), ("cup", 0.85, "tile")]
