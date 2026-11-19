import io
import json
import tarfile

import numpy as np
from PIL import Image

from smallobj import ca1m

VID = "42897538"
# 帧间隔故意不均匀（90 ms、110 ms），检验 frame_map 用的是真实时间戳
STAMPS = [1_000_000_000, 1_090_000_000, 1_200_000_000]


def _png(w, h, value=128, mode="RGB"):
    buf = io.BytesIO()
    arr = np.full((h, w, 3) if mode == "RGB" else (h, w), value, np.uint8 if mode == "RGB" else np.uint16)
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _add(tf, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tf.addfile(info, io.BytesIO(data))


def _rz(theta):
    c, s = np.cos(theta), np.sin(theta)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def make_tar(path, w=64, h=48):
    with tarfile.open(path, "w") as tf:
        for i, ts in enumerate(reversed(STAMPS)):  # 乱序写入，检验排序
            pre = f"{VID}/{ts}"
            _add(tf, f"{pre}.wide/image.png", _png(w, h, 10 * i))
            _add(tf, f"{pre}.wide/image/K.json", json.dumps([[50, 0, w / 2], [0, 50, h / 2], [0, 0, 1]]).encode())
            _add(tf, f"{pre}.gt/RT.json", json.dumps(np.eye(4).tolist()).encode())
            _add(tf, f"{pre}.gt/depth.png", _png(32, 24, 2000, mode="I;16"))
            _add(tf, f"{pre}.gt/depth/K.json", json.dumps([[25, 0, 16], [0, 25, 12], [0, 0, 1]]).encode())
            _add(tf, f"{pre}.wide/instances.json", b"[]")  # 不该被解出
        world = [
            {"id": "w1", "category": "wall", "position": [0, 0, 1.2], "scale": [4, 0.1, 2.4], "R": np.eye(3).tolist()},
            {"id": "f1", "category": "floor", "position": [0, 0, 0], "scale": [4, 4, 0.02], "R": np.eye(3).tolist()},
            {"id": "c1", "category": "cup", "position": [1, 2, 0.8], "scale": [0.08, 0.06, 0.1], "R": _rz(0.5)},
        ]
        _add(tf, f"{VID}/world.gt/instances.json", json.dumps(world).encode())


def test_extract_sorted(tmp_path):
    make_tar(tmp_path / "raw.tar")
    stamps = ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    assert stamps == STAMPS
    assert (tmp_path / "scene" / "frames" / str(STAMPS[0]) / "image.png").exists()
    assert not list((tmp_path / "scene").rglob("instances.json")) or \
        [p.name for p in (tmp_path / "scene").rglob("instances.json")] == ["world_instances.json"]


def test_frame_map_uses_real_timestamps(tmp_path):
    make_tar(tmp_path / "raw.tar")
    ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    ca1m.make_video(tmp_path / "scene", fps=10)
    fm = json.loads((tmp_path / "scene" / "frame_map.json").read_text())
    assert fm["timestamps_ns"] == STAMPS


def test_video_shape_even_and_upright(tmp_path):
    import imageio.v3 as iio
    make_tar(tmp_path / "raw.tar", w=48, h=64)  # 竖拍：宽 48、高 64
    ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    mp4 = ca1m.make_video(tmp_path / "scene", fps=10)
    frames = list(iio.imiter(mp4))
    assert len(frames) == 3
    h, w = frames[0].shape[:2]
    assert (w, h) == (48, 64)


def test_structural_filtered(tmp_path):
    make_tar(tmp_path / "raw.tar")
    ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    recs = ca1m.world_boxes(tmp_path / "scene", structural={"wall", "floor"})
    assert [r["category"] for r in recs] == ["cup"]
    cup = recs[0]
    assert np.allclose(cup["center"], [1, 2, 0.8])
    assert np.allclose(cup["size"], [0.08, 0.06, 0.1])
    assert abs(cup["yaw"] - 0.5) < 1e-6
    assert (tmp_path / "scene" / "gt" / "boxes.json").exists()


def test_camera_track(tmp_path):
    make_tar(tmp_path / "raw.tar")
    ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    track = ca1m.camera_track(tmp_path / "scene")
    assert sorted(track) == STAMPS
    assert track[STAMPS[0]].shape == (4, 4)


def test_tar_url():
    assert ca1m.tar_url("42897538", "val") == "https://ml-site.cdn-apple.com/datasets/ca1m/val/ca1m-val-42897538.tar"


def test_draw_check_writes_frame_sized_png(tmp_path):
    make_tar(tmp_path / "raw.tar")
    ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    ca1m.world_boxes(tmp_path / "scene", structural=set())
    out = ca1m.draw_check(tmp_path / "scene", tmp_path / "check.png", where=0.5)
    assert Image.open(out).size == (64, 48)


def test_shell_objects_dropped_from_gt(tmp_path):
    import tarfile
    make_tar(tmp_path / "raw.tar")
    ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    extra = [{"id": "m1", "category": "object", "position": [0, 1, 2.5], "scale": [0.03, 3.1, 0.14], "R": np.eye(3).tolist()},
             {"id": "rug", "category": "rug", "position": [0, 0, 0.01], "scale": [2.2, 2.3, 0.01], "R": np.eye(3).tolist()},
             {"id": "tv", "category": "television", "position": [1, 1, 1], "scale": [0.08, 0.75, 0.47], "R": np.eye(3).tolist()}]
    p = tmp_path / "scene" / "gt" / "world_instances.json"
    p.write_text(json.dumps(json.loads(p.read_text()) + extra))
    recs = ca1m.world_boxes(tmp_path / "scene", structural={"wall", "floor"}, shell=(0.06, 1.5))
    assert sorted(r["object_id"] for r in recs) == ["c1", "tv"]


def test_odd_orientation_frames_dropped(tmp_path):
    # 42899698：443 帧里有 8 帧竖着存（拍摄中途转了手机），视频只用多数朝向的帧，丢掉的时间戳记进 frame_map
    make_tar(tmp_path / "raw.tar")
    ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    odd = tmp_path / "scene" / "frames" / str(STAMPS[1]) / "image.png"
    odd.write_bytes(_png(48, 64))
    ca1m.make_video(tmp_path / "scene", fps=10)
    fm = json.loads((tmp_path / "scene" / "frame_map.json").read_text())
    assert fm["timestamps_ns"] == [STAMPS[0], STAMPS[2]]
    assert fm["dropped_timestamps_ns"] == [STAMPS[1]]
    assert (fm["width"], fm["height"]) == (64, 48)


def test_labeled_rug_kept_despite_shell_rule(tmp_path):
    # 薄壳规则本来针对踢脚线、墙板这类；明确标成地毯的真值保留（AHa-3D 把地毯当物体建，不当结构）
    make_tar(tmp_path / "raw.tar")
    ca1m.extract(tmp_path / "raw.tar", tmp_path / "scene")
    extra = [{"id": "rug", "category": "rug", "position": [0, 0, 0.01], "scale": [2.2, 2.3, 0.01], "R": np.eye(3).tolist()},
             {"id": "m1", "category": "object", "position": [0, 1, 2.5], "scale": [0.03, 3.1, 0.14], "R": np.eye(3).tolist()}]
    p = tmp_path / "scene" / "gt" / "world_instances.json"
    p.write_text(json.dumps(json.loads(p.read_text()) + extra))
    recs = ca1m.world_boxes(tmp_path / "scene", structural={"wall", "floor"}, shell=(0.06, 1.5), shell_keep={"rug", "carpet", "mat"})
    assert sorted(r["object_id"] for r in recs) == ["c1", "rug"]
