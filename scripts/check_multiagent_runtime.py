"""Check configured worker imports and optional CUDA execution before paid calls."""
import argparse
import json
import subprocess

from agen3d.multiagent.pipeline.config import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("--cuda", action="store_true")
    args = parser.parse_args()
    config = load(args.config)
    failed = False
    for name, service in config.services.items():
        imports = {
            "pi3x": "from pi3.models.pi3x import Pi3X; from pi3.utils.basic import load_multimodal_data; from safetensors.torch import load_file",
            "sam3": "from sam3.model_builder import build_sam3_image_model; from sam3.model.sam3_image_processor import Sam3Processor",
        }[name]
        script = (
            "import sys, json; sys.path.insert(0, sys.argv[1]); import numpy, torch; "
            + imports + "; "
            + ("assert torch.cuda.is_available(), 'CUDA unavailable'; "
               "x=torch.ones((16,16),device='cuda'); y=x@x; torch.cuda.synchronize(); "
               if args.cuda else "")
            + "print(json.dumps({'python': sys.executable, 'prefix': sys.prefix, "
              "'numpy': numpy.__version__, 'torch': torch.__version__}))"
        )
        result = subprocess.run([service.python, "-c", script, service.repo],
                                capture_output=True, text=True, timeout=120)
        failed |= result.returncode != 0
        print(json.dumps({"service": name, "ok": result.returncode == 0,
                          "cuda_tested": args.cuda, "stdout": result.stdout,
                          "stderr": result.stderr}, indent=2))
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
