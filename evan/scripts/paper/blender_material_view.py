"""材质版场景从指定的视频机位渲染一张（blender -b scene.blend --python blender_material_view.py -- spec.json）。只读，不保存 .blend。

spec：{"views": [{"name", "c2w"（OpenCV 相机到世界）, "K", "size_wh"}], "out_dir", 可选 "samples"、"overview": true}
overview：和 blender_paper_render.py 同一个斜上方机位的整体图（藏掉天花板和靠近相机的墙），存 overview.png。
可选 "overview_dir"（相机在房间哪一侧，默认 [0.55, -0.75]）、"overview_hide"（靠相机多近的墙藏掉，占房间对角线的比例，默认 0.2）、"overview_scale"（相机拉远的倍数，默认 1）。
材质、灯光、世界光和色彩管理都用材质版场景里 agent 设好的，这里只换相机和分辨率；Cycles 的采样数封顶并开降噪，免得一张图渲很久。
"""
import json
import sys

import bpy
from mathutils import Matrix

spec = json.load(open(sys.argv[sys.argv.index("--") + 1]))
scene = bpy.context.scene
print("engine", scene.render.engine)
if scene.render.engine == "CYCLES":
    scene.cycles.samples = min(scene.cycles.samples, spec.get("samples", 160))
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                scene.cycles.device = "GPU"
                break
    except Exception as e:
        print("gpu setup failed", e)
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.resolution_percentage = 100
scene.frame_set(scene.frame_start)
cam_data = bpy.data.cameras.new("paper_cam")
cam = bpy.data.objects.new("paper_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
flip = Matrix(((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1)))  # OpenCV 相机 → Blender 相机
for v in spec["views"]:
    W, H = v["size_wh"]
    K = v["K"]
    scene.render.resolution_x, scene.render.resolution_y = int(W), int(H)
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36.0
    cam_data.lens = K[0][0] * 36.0 / W
    cam_data.shift_x = (W / 2 - K[0][2]) / W
    cam_data.shift_y = (K[1][2] - H / 2) / W
    cam_data.clip_start, cam_data.clip_end = 0.05, 100.0
    cam.matrix_world = Matrix(v["c2w"]) @ flip
    scene.render.filepath = f"{spec['out_dir']}/{v['name']}.png"
    bpy.ops.render.render(write_still=True)
if spec.get("overview"):
    from mathutils import Vector
    STRUCT = {"architecture", "structure", "floor", "ceiling", "wall", "exterior"}

    def owner(o):
        root = o
        while root is not None:
            if root.get("instance_id"):
                return str(root["instance_id"]), str(root.get("semantic_class", ""))
            root = root.parent
        return "unassigned:" + o.name, ""

    info = {}
    for o in [o for o in scene.objects if o.type == "MESH"]:
        gid, cls = owner(o)
        seg = (cls or gid).split("/", 1)[0].split(":", 1)[-1].strip().lower()
        name = (o.name + " " + cls + " " + gid).lower()
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        info[o.name] = (lo, hi, seg in STRUCT or gid.split("/", 1)[0].split(":", 1)[-1].strip().lower() in STRUCT, name)
    floor = [n for n, (lo, hi, st, name) in info.items() if st and "floor" in name and "ceiling" not in name]
    basis = floor or [n for n, (lo, hi, st, name) in info.items() if not st] or list(info)
    lo = Vector((min(info[n][0].x for n in basis), min(info[n][0].y for n in basis), 0.0))
    hi = Vector((max(info[n][1].x for n in basis), max(info[n][1].y for n in basis), 0.0))
    room_top = max(h.z for (_, h, _, _) in info.values())
    c = (lo + hi) / 2
    c.z = 0.6
    r = max((hi - lo).length, 2.0)
    dx, dy = spec.get("overview_dir", [0.55, -0.75])
    direction = Vector((dx, dy, 0.0)).normalized()
    far = r * spec.get("overview_scale", 1.0)
    eye = c + direction * 0.85 * far + Vector((0, 0, 1.15 * far))
    for n, (blo, bhi, st, name) in info.items():
        ctr = (blo + bhi) / 2
        tall_thin = (bhi.z - blo.z) > 1.2 and min(bhi.x - blo.x, bhi.y - blo.y) < 0.35
        ceiling_like = "ceiling" in name or "roof" in name or (bhi.z > room_top - 0.05 and (bhi.z - blo.z) < 0.15)
        scene.objects[n].hide_render = ceiling_like or (st and tall_thin and (ctr - c).dot(direction) > spec.get("overview_hide", 0.2) * r)
    scene.render.film_transparent = True
    cam_data.shift_x = cam_data.shift_y = 0.0
    cam_data.sensor_fit = "AUTO"
    cam_data.lens = 32
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1200
    cam.location = eye
    cam.rotation_euler = (c - eye).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{spec['out_dir']}/overview.png"
    bpy.ops.render.render(write_still=True)
print("rendered", len(spec["views"]))
