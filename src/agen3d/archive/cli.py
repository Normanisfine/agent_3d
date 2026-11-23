"""Explicit offline commands. No model, simulator or Blender is launched implicitly."""
import argparse
import json
from pathlib import Path

from .io import digest, read_model, write_new
from agen3d.archive.scene import SceneState


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare-rgb")
    p.add_argument("selection", type=Path)
    p.add_argument("output", type=Path)
    p = commands.add_parser("verify")
    p.add_argument("scene", type=Path)
    p.add_argument("output", type=Path)
    p = commands.add_parser("repair")
    p.add_argument("scene", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--max-steps", type=int, default=3)
    p.add_argument("--max-translation", type=float, default=.1)
    p = commands.add_parser("export-labels")
    p.add_argument("dataset", choices=("ai2thor", "ca1m"))
    p.add_argument("manifest", type=Path)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--alignment-id", required=True)
    p = commands.add_parser("evaluate")
    p.add_argument("scene", type=Path)
    p.add_argument("labels", type=Path)
    p.add_argument("manifest", type=Path)
    p.add_argument("output", type=Path)
    p = commands.add_parser("plan-reference")
    from .aha import DEFAULT_AHA_REPO
    p.add_argument("--repo", type=Path, default=DEFAULT_AHA_REPO,
                   help="AHa-3D checkout (default: project external/aha-3d)")
    for name in ("video", "output", "python", "checkpoint", "mesh-python"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--frames", type=int, default=32)
    p = commands.add_parser("plan")
    p.add_argument("config", type=Path)
    args = parser.parse_args()
    if args.command == "prepare-rgb":
        from .datasets import prepare_rgb
        prepare_rgb(args.selection, args.output)
    elif args.command in {"verify", "repair"}:
        from .verification import Verifier, repair
        scene = read_model(args.scene, SceneState)
        verifier = Verifier()
        if args.command == "verify":
            write_new(args.output, [i.model_dump() for i in verifier.check(scene)])
        else:
            args.output.mkdir(parents=True, exist_ok=False)
            fixed, trace, unresolved = repair(scene, verifier, args.max_steps, args.max_translation)
            write_new(args.output / "before.json", scene)
            write_new(args.output / "scene_state.json", fixed)
            write_new(args.output / "repair_trace.json", trace)
            write_new(args.output / "unresolved.json", [i.model_dump() for i in unresolved])
    elif args.command == "export-labels":
        from .label_export import ai2thor_labels, ca1m_labels
        adapter = ai2thor_labels if args.dataset == "ai2thor" else ca1m_labels
        write_new(args.output, adapter(args.manifest, args.source, args.alignment_id))
    elif args.command == "evaluate":
        from .evaluation import evaluate, load_gt
        from agen3d.archive.scene import InputManifest
        manifest = read_model(args.manifest, InputManifest)
        gt = load_gt(args.labels)
        if (manifest.scene_id, manifest.dataset, manifest.split) != (gt.scene_id, gt.dataset, gt.split):
            raise ValueError("Evaluation manifest identity mismatch")
        write_new(args.output, evaluate(read_model(args.scene, SceneState), gt, digest(args.manifest)))
    elif args.command == "plan-reference":
        from .aha import reference_command
        print(json.dumps(reference_command(args.repo, args.video, args.output, args.python,
                                           args.checkpoint, args.mesh_python, args.frames), indent=2))
    else:
        config = json.loads(args.config.read_text())
        print(json.dumps({"status": "planned_only", "config": config,
                          "next": "Freeze inputs; author/review AHa recipe; export aligned scene state",
                          "blocked": "No automatic RGB-to-authored-scene integration is claimed"}, indent=2))


if __name__ == "__main__":
    main()
