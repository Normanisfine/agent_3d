"""Offline Hunyuan shape inference and GLB round-trip; not a quality benchmark.

Run with .venvs/hunyuan/bin/python on a CUDA-enabled host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--steps', type=int, default=10)
    parser.add_argument('--resolution', type=int, default=128)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'external/hunyuan3d-2.1/hy3dshape')]
    from agen3d.multiagent.models import ModelRegistry
    import numpy as np
    import torch
    import trimesh
    from PIL import Image
    from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline

    registry = ModelRegistry()
    checkpoint = registry.resolve('model:hunyuan-shape')
    image = ROOT / 'external/hunyuan3d-2.1/assets/example_images/004.png'
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(str(checkpoint))
    mesh = pipeline(image=Image.open(image).convert('RGBA'),
                    num_inference_steps=args.steps, octree_resolution=args.resolution,
                    generator=torch.Generator().manual_seed(42))[0]
    assert mesh is not None and len(mesh.faces) > 0
    target = args.output / 'mesh.glb'
    mesh.export(target)
    reopened = trimesh.load(target, force='mesh')
    assert len(reopened.faces) > 0 and np.isfinite(reopened.vertices).all()
    torch.cuda.synchronize()
    report = {
        'ok': True, 'scope': 'reduced-resolution inference and GLB round-trip only',
        'checkpoint': registry.verify('hunyuan-shape'), 'input': str(image),
        'input_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
        'steps': args.steps, 'resolution': args.resolution, 'seed': 42,
        'torch': torch.__version__, 'gpu': torch.cuda.get_device_name(),
        'peak_cuda_bytes': torch.cuda.max_memory_allocated(),
        'elapsed_seconds': time.monotonic() - started,
        'vertices': len(reopened.vertices), 'faces': len(reopened.faces),
        'mesh': str(target.resolve()), 'offline': True,
    }
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
