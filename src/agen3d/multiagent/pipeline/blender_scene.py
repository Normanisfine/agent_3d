"""Blender-side editable asset assembly plus matched-camera RGB and instance renders.

Imported RoomKit collections retain their native materials and hierarchy. Observed
point hulls are explicit fallback objects, never presented as retrieved assets.
"""
import json
import sys
from pathlib import Path


def main():
    import bpy
    from mathutils import Matrix, Vector

    request = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
    output = Path(request["output"])
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(Path(request["aha_repo"]) / "src"))
    from aha3d.blender.roomkit import place_asset

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 8
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = False
    scene.render.dither_intensity = 0
    scene.world = bpy.data.worlds.new("NeutralWorld")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.75, .75, .75, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .8
    records = json.loads(Path(request["scene"]).read_text())["objects"]
    assets = json.loads(Path(request["assets"]).read_text())
    objects, results = {}, {}
    for number, record in enumerate(records):
        oid, box = record["object_id"], record["box"]
        spec = assets[oid]
        before = set(bpy.data.objects)
        asset_error = None
        root = None
        if spec.get("asset_id"):
            try:
                root = place_asset(spec["asset_id"], instance_id=oid, project_root=Path(request["aha_repo"]))
                bpy.context.view_layer.update()
                meshes = [o for o in set(bpy.data.objects)-before if o.type == "MESH"]
                pts = [o.matrix_world @ Vector(corner) for o in meshes for corner in o.bound_box]
                if not pts:
                    raise ValueError("Imported asset has no mesh bounds")
                lo = Vector([min(p[i] for p in pts) for i in range(3)])
                hi = Vector([max(p[i] for p in pts) for i in range(3)])
                extent = hi - lo
                if min(extent) <= 0:
                    raise ValueError("Degenerate imported asset")
                desired = Matrix.Translation(Vector(box["center"])) @ Matrix(box["rotation"]).to_4x4()
                desired @= Matrix.Diagonal((*[box["extent"][i] / extent[i] for i in range(3)], 1))
                desired @= Matrix.Translation(-(hi + lo) / 2)
                root.matrix_world = desired @ root.matrix_world
            except Exception as exc:
                asset_error = f"{type(exc).__name__}: {exc}"
                for obj in set(bpy.data.objects)-before:
                    bpy.data.objects.remove(obj, do_unlink=True)
                root = None
        if root is None:
            geometry = json.loads(Path(spec["mesh"]).read_text())
            mesh = bpy.data.meshes.new(oid)
            mesh.from_pydata(geometry["vertices"], [], geometry["faces"])
            mesh.update()
            root = bpy.data.objects.new(oid, mesh)
            scene.collection.objects.link(root)
            root.matrix_world = Matrix.Translation(Vector(box["center"])) @ Matrix(box["rotation"]).to_4x4()
            # Hull coordinates were authored at the initial fit. Scale candidate edits
            # against that fit so changing extents actually changes rendered geometry.
            initial = spec.get("initial_extent", box["extent"])
            root.matrix_world @= Matrix.Diagonal((*[box["extent"][i]/initial[i] for i in range(3)], 1))
            material = bpy.data.materials.new(oid + "_color")
            material.diffuse_color = (*[v/255 for v in spec["color"]], 1)
            root.data.materials.append(material)
            meshes = [root]
        root["agen3d_id"] = oid
        root["agen3d_category"] = record["category"] or "unknown"
        root["representation"] = "roomkit_asset" if spec.get("asset_id") and not asset_error else "observed_point_hull"
        objects[oid] = meshes
        results[oid] = {"representation": root["representation"], "asset_id": spec.get("asset_id"),
                        "asset_error": asset_error, "parts": len(meshes)}
    if records:
        # Structural floor is a separate, non-evaluated contextual plane.
        xy = [record["box"]["center"][:2] for record in records]
        lo = [min(p[i] for p in xy)-2 for i in range(2)]
        hi = [max(p[i] for p in xy)+2 for i in range(2)]
        bpy.ops.mesh.primitive_plane_add(size=1, location=((lo[0]+hi[0])/2, (lo[1]+hi[1])/2, 0))
        floor = bpy.context.object
        floor.name = "predicted_floor_context"
        floor.scale = (hi[0]-lo[0], hi[1]-lo[1], 1)
        floor.hide_render = False
    cameras = json.loads(Path(request["cameras"]).read_text())
    width, height = cameras["width"], cameras["height"]
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    camera_objects = []
    for index in request["view_indices"]:
        data = bpy.data.cameras.new(f"camera_{index}")
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        k = cameras["intrinsics"][index]
        data.sensor_fit = "HORIZONTAL"
        data.sensor_width = 36
        data.lens = k[0][0] * 36 / width
        # OpenCV looks +Z with Y down; Blender looks -Z with Y up.
        obj.matrix_world = Matrix(cameras["camera_to_world"][index]) @ Matrix.Diagonal((1,-1,-1,1))
        camera_objects.append((index, obj, k))
    scene.camera = camera_objects[0][1]
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "scene.blend"))

    def camera_settings(obj, k):
        scene.camera = obj
        scene.render.pixel_aspect_x = 1
        scene.render.pixel_aspect_y = k[0][0] / k[1][1]
        obj.data.shift_x = (width/2 - k[0][2]) / width
        obj.data.shift_y = (k[1][2] - height/2) * scene.render.pixel_aspect_y / width

    for index, obj, k in camera_objects:
        camera_settings(obj, k)
        scene.render.filepath = str(output / f"rgb_{index:03d}.png")
        bpy.ops.render.render(write_still=True)
    # One emission-color instance pass per view supports occlusion-aware mask checks.
    scene.cycles.samples = 1
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0
    for obj in scene.objects:
        if obj.type == "MESH" and obj not in {m for meshes in objects.values() for m in meshes}:
            obj.hide_render = True
    palette = {}
    for number, (oid, meshes) in enumerate(objects.items(), 1):
        rgb = ((number * 67) % 251 + 1, (number * 131) % 251 + 1, (number * 193) % 251 + 1)
        palette[oid] = rgb
        linear = [v/255/12.92 if v/255 <= .04045 else ((v/255+.055)/1.055)**2.4 for v in rgb]
        material = bpy.data.materials.new(oid + "_instance")
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs[0].default_value = (*linear, 1)
        output_node = nodes.new("ShaderNodeOutputMaterial")
        material.node_tree.links.new(emission.outputs[0], output_node.inputs[0])
        for obj in meshes:
            obj.data = obj.data.copy()
            obj.data.materials.clear()
            obj.data.materials.append(material)
            for polygon in obj.data.polygons:
                polygon.material_index = 0
    for index, obj, k in camera_objects:
        camera_settings(obj, k)
        scene.render.filepath = str(output / f"instances_{index:03d}.png")
        bpy.ops.render.render(write_still=True)
    (output / "manifest.json").write_text(json.dumps({"objects": results, "palette": palette,
        "views": request["view_indices"], "blend": str(output / "scene.blend")}, indent=2))


if __name__ == "__main__":
    main()
