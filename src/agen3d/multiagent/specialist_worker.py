"""Standalone subprocess entrypoint: run inside each specialist's isolated environment."""
import json
import sys
from pathlib import Path


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    repo, output = Path(request["repo"]).resolve(), Path(request["output"]).resolve()
    sys.path.insert(0, str(repo))
    backend = request["service"]
    if backend == "pi3x":
        import numpy as np
        import torch
        from PIL import Image
        from pi3.models.pi3x import Pi3X
        from pi3.utils.basic import load_multimodal_data
        from pi3.utils.geometry import recover_intrinsic_from_rays_d
        from safetensors.torch import load_file
        frame_dir = output / "frames"
        frame_dir.mkdir()
        for index, path in enumerate(request["images"]):
            Image.open(path).convert("RGB").save(frame_dir / f"{index:04d}.png")
        images, conditions = load_multimodal_data(str(frame_dir),
            conditions={"intrinsics": None, "poses": None, "depths": None},
            interval=1, device="cuda")
        model = Pi3X(use_multimodal=False).eval().cuda()
        loaded = model.load_state_dict(load_file(request["checkpoint"]), strict=False)
        if loaded.missing_keys:
            raise RuntimeError(f"Pi3X missing weights: {loaded.missing_keys}")
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            prediction = model(imgs=images, **conditions)
            intrinsics = recover_intrinsic_from_rays_d(
                torch.nn.functional.normalize(prediction["local_points"], dim=-1),
                force_center_principal_point=True)
        values = {k: v.detach().float().cpu().numpy() for k, v in prediction.items()
                  if isinstance(v, torch.Tensor)}
        values["intrinsics"] = intrinsics.detach().float().cpu().numpy()
        np.savez_compressed(output / "geometry.npz", **values)
        result = {"geometry": str(output / "geometry.npz"),
                  "frame_order": request["images"], "image_shape": list(images.shape),
                  "coordinate_frame": "Pi3X camera/world convention; not canonical Z-up",
                  "scale": "predicted_metric", "status": "reference_only",
                  "unused_checkpoint_keys": loaded.unexpected_keys}
    elif backend in {"sam3", "sam3_batch"}:
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor
        from PIL import Image
        import torch
        model = build_sam3_image_model(checkpoint_path=request["checkpoint"], load_from_HF=False)
        processor = Sam3Processor(model)
        if backend == "sam3_batch":
            detections = []
            # Encode each image once; reuse its features for the category prompts.
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                for frame in request["frames"]:
                    state = processor.set_image(Image.open(frame["path"]).convert("RGB"))
                    for item in request["categories"]:
                        processor.reset_all_prompts(state)
                        prediction = processor.set_text_prompt(state=state, prompt=item["prompt"])
                        masks = prediction["masks"].detach().cpu().numpy()
                        scores = prediction["scores"].detach().cpu().tolist()
                        for mask, score in zip(masks, scores):
                            pixels = (mask.squeeze() > 0).astype("uint8") * 255
                            if score < .45 or (pixels > 0).sum() < 32:
                                continue
                            path = output / f"mask-{len(detections):05d}.png"
                            Image.fromarray(pixels).save(path)
                            detections.append({"frame_index": frame["index"], "category": item["category"],
                                               "path": str(path), "score": score})
            (output / "masks.json").write_text(json.dumps({"detections": detections}, indent=2))
            (output / "result.json").write_text(json.dumps({"masks_manifest": str(output / "masks.json"),
                                                            "detections": len(detections)}))
            return
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            state = processor.set_image(Image.open(request["image"]).convert("RGB"))
            state = processor.set_text_prompt(state=state, prompt=request["prompt"])
        masks = state["masks"].detach().cpu().numpy()
        paths = []
        for i, mask in enumerate(masks):
            path = output / f"mask-{i:03d}.png"
            Image.fromarray((mask.squeeze() > 0).astype("uint8") * 255).save(path)
            paths.append(str(path))
        result = {"masks": paths, "scores": state["scores"].detach().cpu().tolist(),
                  "status": "predicted_masks"}
    elif backend == "hunyuan":
        sys.path.insert(0, str(repo / "hy3dshape"))
        from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
        import torch
        pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            request["checkpoint"])
        mesh = pipeline(image=request["image"],
                        generator=torch.Generator().manual_seed(request["seed"]))[0]
        mesh.export(str(output / "mesh.glb"))
        result = {"mesh": str(output / "mesh.glb"), "status": "unfitted_candidate"}
    elif backend == "sam3d":
        sys.path.insert(0, str(repo / "notebook"))
        from inference import Inference, load_image
        import numpy as np
        from PIL import Image
        config = request["checkpoint"]
        inference = Inference(config, compile=False)
        image = load_image(request["image"])
        mask = np.asarray(Image.open(request["mask"]).convert("L")) > 127
        candidate = inference(image, mask, seed=request["seed"])
        artifacts = {}
        if candidate.get("glb") is not None:
            candidate["glb"].export(str(output / "mesh.glb"))
            artifacts["mesh"] = str(output / "mesh.glb")
        if candidate.get("gs") is not None:
            candidate["gs"].save_ply(str(output / "splat.ply"))
            artifacts["splat"] = str(output / "splat.ply")
        if not artifacts:
            raise RuntimeError("SAM 3D returned no supported export; inspect pinned API")
        for key in ("rotation", "translation", "scale"):
            value = candidate.get(key)
            if value is not None:
                artifacts[key] = value.detach().cpu().tolist() if hasattr(value, "detach") else value
        result = {**artifacts, "status": "unfitted_candidate"}
    elif backend == "hispatial":
        from hispatial.inference import MoGeProcessor, HiSpatialPredictor
        from moge.model.v2 import MoGeModel
        from PIL import Image
        image = Image.open(request["image"]).convert("RGB")
        # Construct the documented processor with a pinned local MoGe model.
        import torch
        processor = MoGeProcessor.__new__(MoGeProcessor)
        processor.device = torch.device("cuda")
        processor.img_size = 448
        processor.model = MoGeModel.from_pretrained(request["moge"]).to(processor.device)
        predictor = HiSpatialPredictor(model_load_path=request["checkpoint"])
        answer = predictor.query(image=image, prompt=request["question"],
                                 xyz_values=processor.apply_transform(image))
        result = {"answer": answer, "geometry_source": "MoGe", "status": "advisory"}
    else:
        raise ValueError(f"Unsupported service {backend}")
    (output / "result.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
