import json
import sys

import numpy as np
import pytest
import trimesh
from PIL import Image

from smallobj import boxes, gen3d

K = [[100.0, 0, 50.0], [0, 100.0, 40.0], [0, 0, 1]]


def _c2w(dx=0.0):
    T = np.eye(4)
    T[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]  # 朝世界 +y 看，世界 z 朝上
    T[0, 3] = dx
    return T


FAKE = '''
import json, os, sys, trimesh
jobs = json.load(open(sys.argv[sys.argv.index("--batch") + 1]))
open(os.environ["FAKE_CALLS"], "a").write(f"{len(jobs)}\\n")
for j in jobs:
    if os.environ.get("FAKE_OOM"):
        print(json.dumps({"out": j["out"], "status": "backend_error", "error": "CUDA OOM"}))
        continue
    trimesh.creation.box(extents=(0.5, 2.0, 0.5)).export(j["out"])  # Y 朝上的高瘦长方体
    print(json.dumps({"out": j["out"], "status": "ok", "seconds": 0.1}))
'''


@pytest.fixture
def scene(tmp_path, monkeypatch):
    """假场景：一帧高清帧 + 两个清单物体的掩码（一个 400 像素，一个 150 像素）+ 假后端。"""
    P = tmp_path / "perception" / "S"
    (P / "hd" / "frames").mkdir(parents=True)
    Image.fromarray(np.full((80, 100, 3), 128, np.uint8)).save(P / "hd" / "frames" / "000000.png")
    (P / "hd" / "cameras.json").write_text(json.dumps({"size_wh": [100, 80], "frames": [{"source_frame": 0, "K": K, "c2w": _c2w().tolist()}]}))
    items = []
    for iid, c in (("big", (0.0, 2.0, 0.0)), ("tiny", (0.5, 2.0, 0.0)), ("away", (0.0, -2.0, 0.0))):
        r = boxes.record(iid, "cup", c, 0.0, (0.2, 0.2, 0.2))
        r.update(item_id=iid)
        items.append(r)
    (P / "inventory.json").write_text(json.dumps(items))
    (P / "item_masks" / "big").mkdir(parents=True)
    (P / "item_masks" / "tiny").mkdir()
    m = np.zeros((80, 100), np.uint8)
    m[30:50, 40:60] = 255
    Image.fromarray(m).save(P / "item_masks" / "big" / "000000.png")
    t = np.zeros((80, 100), np.uint8)
    t[10:20, 70:85] = 255
    Image.fromarray(t).save(P / "item_masks" / "tiny" / "000000.png")
    (P / "item_masks" / "index.json").write_text(json.dumps([
        {"item_id": "big", "frame": 0, "status": "ok", "mask": "big/000000.png", "mask_px": 400},
        {"item_id": "tiny", "frame": 0, "status": "ok", "mask": "tiny/000000.png", "mask_px": 150},
        {"item_id": "away", "frame": 0, "status": "no_view"}]))
    fake = tmp_path / "fake_backend.py"
    fake.write_text(FAKE)
    calls = tmp_path / "calls.txt"
    monkeypatch.setenv("FAKE_CALLS", str(calls))
    monkeypatch.setitem(gen3d.BACKENDS, "fake", [sys.executable, str(fake)])
    return tmp_path, calls


def _ncalls(calls):
    return sum(int(x) for x in calls.read_text().split()) if calls.exists() else 0


def test_pick_frames_prefers_big_unclipped_sharp():
    item = boxes.record("c", "cup", (0.0, 2.0, 0.0), 0.0, (0.2, 0.2, 0.2))
    hd = {"size_wh": [100, 80], "frames": [
        {"source_frame": 1, "K": K, "c2w": _c2w(-0.95).tolist()},   # 物体偏到右边缘，截断约一半
        {"source_frame": 2, "K": K, "c2w": _c2w(0.0).tolist()},     # 正中
        {"source_frame": 3, "K": K, "c2w": (_c2w(0.0) @ np.diag([1, 1, 1, 1.0])).tolist()}]}
    hd["frames"][2]["c2w"][1][3] = 1.0  # 第 3 帧往前挪 1 m：物体投影更大
    sharp = {1: 1.0, 2: 1.0, 3: 1.0}
    assert gen3d.pick_frames(item, hd, sharp, k=3) == [3, 2, 1]
    assert gen3d.pick_frames(item, hd, {1: 1.0, 2: 1.0, 3: 0.1}, k=1) == [2]  # 太糊的大图让给清楚的


def test_crop_margin():
    img = np.zeros((200, 300, 3), np.uint8)
    mask = np.zeros((200, 300), bool)
    mask[50:100, 100:200] = True
    assert gen3d.crop_rgba(img, mask).shape == (65, 130, 4)


def test_clean_mesh_y_up_to_z_up():
    m = gen3d.clean_mesh(trimesh.creation.box(extents=(1.0, 3.0, 1.0)), up="y")
    ext = m.extents
    assert np.argmax(ext) == 2 and np.isclose(ext.max(), 1.0)
    assert np.isclose(m.bounds[0][2], 0.0) and np.allclose((m.bounds[0][:2] + m.bounds[1][:2]) / 2, 0, atol=1e-9)


def test_clean_mesh_keeps_largest_component():
    a = trimesh.creation.box(extents=(1, 1, 1))
    b = trimesh.creation.box(extents=(0.1, 0.1, 0.1))
    b.apply_translation((5, 0, 0))
    m = gen3d.clean_mesh(trimesh.util.concatenate([a, b]), up="z")
    assert np.allclose(m.extents, [1, 1, 1])


def test_too_small_and_no_view(scene):
    root, calls = scene
    out = gen3d.request("S", ["tiny", "away"], backend="fake", root=root)
    assert [r["status"] for r in out] == ["too_small", "no_view"]
    assert _ncalls(calls) == 0


def test_request_ok_and_cache_hit_skips_backend(scene):
    root, calls = scene
    out = gen3d.request("S", ["big"], backend="fake", n_candidates=2, root=root)
    assert [r["status"] for r in out] == ["ok", "ok"] and _ncalls(calls) == 2
    mesh = trimesh.load(out[0]["mesh_glb"], force="mesh")
    assert np.argmax(mesh.extents) == 2  # 已经转成 Z 朝上
    again = gen3d.request("S", ["big"], backend="fake", n_candidates=2, root=root)
    assert [r["status"] for r in again] == ["ok", "ok"] and _ncalls(calls) == 2


def test_cache_key_stable():
    m = np.zeros((10, 10), bool)
    m[2:5, 2:5] = True
    assert gen3d.cache_key(3, m, "hy3d_shape", 0) == gen3d.cache_key(3, m.copy(), "hy3d_shape", 0)
    assert gen3d.cache_key(3, m, "hy3d_shape", 1) != gen3d.cache_key(3, m, "hy3d_shape", 0)


def test_backend_oom_is_backend_error(scene, monkeypatch):
    root, _ = scene
    monkeypatch.setenv("FAKE_OOM", "1")
    out = gen3d.request("S", ["big"], backend="fake", n_candidates=1, root=root)
    assert out[0]["status"] == "backend_error"


def test_budget_cap(scene):
    root, calls = scene
    (root / "gen" / "S").mkdir(parents=True)
    (root / "gen" / "S" / "budget.json").write_text(json.dumps({"used": 30}))
    out = gen3d.request("S", ["big"], backend="fake", n_candidates=1, root=root)
    assert out[0]["status"] == "budget" and _ncalls(calls) == 0


def test_cache_hit_from_another_run_still_uses_budget(scene):
    # 10-27：同一场景先跑的组生成、后跑的组拿缓存不占预算，A3r/A3v 谁后跑谁占便宜；缓存只省 GPU，预算照扣
    root, calls = scene
    gen3d.request("S", ["big"], backend="fake", n_candidates=2, root=root, budget_name="budget_A3r")
    assert _ncalls(calls) == 2
    (root / "gen" / "S" / "budget_A3v.json").write_text(json.dumps({"used": 29}))
    out = gen3d.request("S", ["big"], backend="fake", n_candidates=2, root=root, budget_name="budget_A3v")
    assert [r["status"] for r in out] == ["ok", "budget"] and out[0]["cached"] and _ncalls(calls) == 2
    assert json.loads((root / "gen" / "S" / "budget_A3v.json").read_text())["used"] == 30


def test_same_run_rerequest_is_free(scene):
    # 同一次运行再要一次已经拿到的候选不重复扣
    root, calls = scene
    gen3d.request("S", ["big"], backend="fake", n_candidates=2, root=root, budget_name="budget_r")
    gen3d.request("S", ["big"], backend="fake", n_candidates=2, root=root, budget_name="budget_r")
    assert json.loads((root / "gen" / "S" / "budget_r.json").read_text())["used"] == 2 and _ncalls(calls) == 2


def test_prepare_sam3d_job(scene):
    root, _ = scene
    P = root / "perception" / "S" / "hd" / "depth"
    P.mkdir()
    np.save(P / "000000.npy", np.full((80, 100), 2.0, np.float32))
    job = gen3d.prepare_sam3d_job("S", ["big", "tiny"], root=root)
    spec = json.loads((job / "inputs.json").read_text())
    assert [s["item_id"] for s in spec] == ["big"]  # tiny 掩码不到 200 像素，不交给 SAM 3D
    pm = np.load(job / "big_pointmap.npy")
    assert pm.shape == (80, 100, 3) and np.allclose(pm[..., 2], 2.0)  # 相机坐标系：z 就是深度
    assert np.isclose(pm[40, 50, 0], 0.0) and np.isclose(pm[40, 60, 0], 0.2)
    assert Image.open(job / "big_rgba.png").size == (100, 80)  # SAM 3D 要整帧，不裁剪


def test_failed_cache_entry_is_regenerated(scene):
    # 上次这个候选生成失败（gen.json 记了 backend_error）：同样的 key 也不能当缓存命中
    root, calls = scene
    gen3d.request("S", ["big"], backend="fake", n_candidates=1, root=root)
    meta = root / "gen" / "S" / "big" / "c0" / "gen.json"
    m = json.loads(meta.read_text())
    meta.write_text(json.dumps(dict(m, status="backend_error")))
    n = _ncalls(calls)
    out = gen3d.request("S", ["big"], backend="fake", n_candidates=1, root=root)
    assert out[0]["status"] == "ok" and _ncalls(calls) == n + 1


def test_hy3d_batch_survives_one_failed_item(tmp_path):
    # Hunyuan 的 marching cubes 失败时返回 [None]：只记这一个 backend_error，后面的照常生成
    import importlib.util
    spec = importlib.util.spec_from_file_location("hy3d_shape", gen3d.PROJ / "scripts" / "gen_backends" / "hy3d_shape.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for k in range(3):
        Image.fromarray(np.full((8, 8, 4), 200, np.uint8)).save(tmp_path / f"{k}.png")
    jobs = [{"rgba": str(tmp_path / f"{k}.png"), "out": str(tmp_path / f"{k}.glb"), "seed": k} for k in range(3)]

    def fake_pipe(image, seed):
        return [None] if seed == 1 else [trimesh.creation.box(extents=(1, 2, 1))]
    res = mod.process(jobs, fake_pipe)
    assert [r["status"] for r in res] == ["ok", "backend_error", "ok"]


def test_concurrent_requests_respect_budget(scene):
    # 两个后台任务同时请求、只剩 1 次额度：只能生成一次（计数在锁里读写）
    import threading
    root, calls = scene
    (root / "gen" / "S").mkdir(parents=True)
    (root / "gen" / "S" / "budget_t.json").write_text(json.dumps({"used": 29}))
    outs = []
    th = [threading.Thread(target=lambda s=s: outs.append(gen3d.request("S", ["big"], backend="fake", n_candidates=1,
                                                                          seed=s, root=root, budget_name="budget_t")))
          for s in (0, 5)]
    [t.start() for t in th]
    [t.join() for t in th]
    assert _ncalls(calls) == 1
    assert sorted(o[0]["status"] for o in outs) == ["budget", "ok"]
