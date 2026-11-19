"""Blender-side bridge, invoked with blender -b SOURCE.blend -P THIS_FILE -- ...

Explicit candidate output only. This bridge does not certify source-image fidelity.
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    import bpy
    from mathutils import Matrix, Vector

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["export", "apply", "render"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--proposals", type=Path)
    parser.add_argument("--scene-id", default="blender_scene")
    parser.add_argument("--alignment-id", default="blender-world-unverified")
    parser.add_argument("--frame", type=int, default=1)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.output.exists():
        raise FileExistsError("Bridge never overwrites an existing artifact")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    objects = {}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        stable_id = str(obj.get("agen3d_id", obj.name))
        if stable_id in objects:
            raise ValueError(f"Duplicate object ID {stable_id}")
        objects[stable_id] = obj
    units = bpy.context.scene.unit_settings.scale_length
    if abs(units - 1.0) > 1e-6:
        raise ValueError("Bridge currently requires one Blender unit = one metre")

    def box_of(obj):
        matrix = obj.matrix_world
        rotation = matrix.to_quaternion().to_matrix()
        # Reject shear/reflection rather than silently producing invalid oriented boxes.
        linear = matrix.to_3x3()
        if linear.determinant() <= 0:
            raise ValueError(f"Reflected/singular object {obj.name}; normalize it before export")
        axes = [linear.col[i].normalized() for i in range(3)]
        if max(abs(axes[i].dot(axes[j])) for i in range(3) for j in range(i)) > 1e-5:
            raise ValueError(f"Sheared object {obj.name}")
        local = [Vector(v) for v in obj.bound_box]
        minimum = Vector([min(v[i] for v in local) for i in range(3)])
        maximum = Vector([max(v[i] for v in local) for i in range(3)])
        center = matrix @ ((minimum + maximum) / 2)
        extent = [(maximum[i] - minimum[i]) * linear.col[i].length for i in range(3)]
        if min(extent) <= 0:
            raise ValueError(f"Degenerate object bounds {obj.name}")
        return {"center": list(center), "extent": extent,
                "rotation": [list(row) for row in rotation]}

    if args.action == "export":
        scene = {"schema_version": 1, "scene_id": args.scene_id,
                 "coordinate_frame": "RH_Z_UP_METRES", "scale_mode": "estimated_scale",
                 "alignment_id": args.alignment_id, "objects": []}
        for stable_id, obj in objects.items():
            scene["objects"].append({"object_id": stable_id, "box": box_of(obj),
                                      "category": obj.get("agen3d_category"),
                                      "support_id": obj.get("agen3d_support_id"),
                                      "provenance": ["Blender bound_box; evaluated modifiers not included"]})
        args.output.write_text(json.dumps(scene, indent=2))
    elif args.action == "apply":
        if not args.proposals:
            raise ValueError("--proposals is required")
        proposals = json.loads(args.proposals.read_text())
        seen = set()
        for proposal in proposals:
            stable_id = proposal["object_id"]
            if stable_id in seen:
                raise ValueError("Select only one proposal per object before applying")
            seen.add(stable_id)
            obj = objects[stable_id]
            before = box_of(obj)
            # Applying to a different source scene is rejected, even if IDs match.
            for key in ("center", "extent"):
                if max(abs(a - b) for a, b in zip(before[key], proposal["before"][key])) > 1e-5:
                    raise ValueError(f"Stale proposal for {stable_id}")
            if any(abs(before['rotation'][i][j] - proposal['before']['rotation'][i][j]) > 1e-5
                   for i in range(3) for j in range(3)):
                raise ValueError(f"Stale rotation for {stable_id}")
            after = proposal["after"]
            r = Matrix(after["rotation"])
            if abs(r.determinant() - 1) > 1e-5 or any(
                abs(r.col[i].dot(r.col[j]) - (1 if i == j else 0)) > 1e-5
                for i in range(3) for j in range(3)):
                raise ValueError("Invalid rotation")
            if min(after["extent"]) <= 0:
                raise ValueError("Invalid extents")
            if (Vector(after["center"]) - Vector(before["center"])).length > .100001:
                raise ValueError("Translation exceeds local repair bound")
            if obj.constraints or obj.animation_data or obj.modifiers:
                raise ValueError("Constrained/animated/modified mesh requires a dedicated adapter")
            local = [Vector(v) for v in obj.bound_box]
            lo = Vector([min(v[i] for v in local) for i in range(3)])
            hi = Vector([max(v[i] for v in local) for i in range(3)])
            scale = Vector([after["extent"][i] / (hi[i] - lo[i]) for i in range(3)])
            transform = r.to_4x4() @ Matrix.Diagonal((*scale, 1))
            transform.translation = Vector(after["center"]) - transform.to_3x3() @ ((lo + hi) / 2)
            obj.matrix_world = transform
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    else:
        if not bpy.context.scene.camera:
            raise ValueError("Source .blend must have a configured camera")
        scene = bpy.context.scene
        scene.frame_set(args.frame)
        scene.render.filepath = str(args.output.resolve())
        scene.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
