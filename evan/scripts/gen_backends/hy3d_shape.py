"""Hunyuan3D-2mini 只生成形状（在 .runtime/hy3d/venv 里运行）。

用法：python hy3d_shape.py --rgba in.png --out mesh.glb --seed 0
      python hy3d_shape.py --batch jobs.json      （jobs 是 [{rgba, out, seed}]，模型只加载一次）
每个物体打印一行 JSON（status、seconds、peak_gb、out）。任何一个物体失败（显存不够、marching cubes 失败返回 None 等）
只记这一个 backend_error，后面的照常生成；单个模式下有失败就退出码 3。
输出的 GLB 是 Hunyuan 的规范空间（glTF 约定 Y 朝上、单位任意），朝向和尺度由 gen3d.clean_mesh 和 place_mesh 处理。
"""
import argparse
import json
import sys
import time


def process(jobs, pipe_call, peak_gb=lambda: None, on_error=lambda: None):
    """逐个生成。pipe_call(image, seed) 返回 [mesh 或 None]。返回每个物体的结果 dict（也逐行打印）。"""
    from PIL import Image
    out = []
    for j in jobs:
        t1 = time.time()
        try:
            image = Image.open(j["rgba"]).convert("RGBA")
            mesh = pipe_call(image, int(j.get("seed", 0)))[0]
            if mesh is None:
                raise RuntimeError("生成器没返回网格（marching cubes 失败）")
            mesh.export(j["out"])
            r = {"out": j["out"], "status": "ok", "seconds": round(time.time() - t1, 1), "peak_gb": peak_gb()}
        except Exception as e:  # noqa: BLE001 — 单个物体失败不拖垮整批
            on_error()
            kind = "CUDA OOM" if "OutOfMemory" in type(e).__name__ else type(e).__name__
            r = {"out": j["out"], "status": "backend_error", "error": f"{kind}: {e}"[:300], "seconds": round(time.time() - t1, 1)}
        print(json.dumps(r), flush=True)
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rgba")
    ap.add_argument("--out")
    ap.add_argument("--batch")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default="tencent/Hunyuan3D-2mini")
    ap.add_argument("--subfolder", default="hunyuan3d-dit-v2-mini")
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--octree", type=int, default=256)
    args = ap.parse_args()
    import torch
    jobs = json.load(open(args.batch)) if args.batch else [{"rgba": args.rgba, "out": args.out, "seed": args.seed}]
    t0 = time.time()
    try:
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
        pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(args.model, subfolder=args.subfolder,
                                                                use_safetensors=True, device="cuda")
    except Exception as e:  # noqa: BLE001 — 模型加载失败：每个物体都记 backend_error
        for j in jobs:
            print(json.dumps({"out": j["out"], "status": "backend_error", "error": f"load: {e}"[:300]}), flush=True)
        sys.exit(3)
    print(json.dumps({"event": "loaded", "seconds": round(time.time() - t0, 1)}), flush=True)
    res = process(jobs, lambda image, seed: pipe(image=image, num_inference_steps=args.steps, octree_resolution=args.octree,
                                                 generator=torch.manual_seed(seed), output_type="trimesh"),
                  peak_gb=lambda: round(torch.cuda.max_memory_allocated() / 2**30, 2), on_error=torch.cuda.empty_cache)
    if not args.batch and any(r["status"] != "ok" for r in res):
        sys.exit(3)


if __name__ == "__main__":
    main()
