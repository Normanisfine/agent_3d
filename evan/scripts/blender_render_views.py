"""在 Blender 里给一个最终场景出对比渲染（blender -b scene.blend --python blender_render_views.py -- spec.json）。

spec：{"views": [{"name", "c2w"（OpenCV 相机到世界）, "K", "size_wh"}], "out_dir", "scale", 可选 "colors": {零件名: 线性 RGB}}。
给了 colors 就按它上色（颜色取自视频，见 smallobj.colorize），表里没有的零件用浅灰；否则按大小上色。
Workbench 引擎：按物体大小上色（XS 红、S 橙、M 蓝、L 绿，墙地面浅灰），带阴影、腔体明暗和轮廓线，32 倍抗锯齿；
另出一张整体图：只框房间内部，藏掉天花板和靠近相机的墙。只读场景，不改 .blend。
"""
import json
import sys

import bpy
from mathutils import Matrix, Vector

spec = json.load(open(sys.argv[sys.argv.index("--") + 1]))
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
disp = scene.display
disp.render_aa = "32"
sh = disp.shading
sh.light, sh.color_type = "STUDIO", "OBJECT"
sh.show_shadows, sh.shadow_intensity = True, 0.35
sh.show_cavity, sh.cavity_type = True, "BOTH"
sh.show_object_outline = True
sh.background_type = "VIEWPORT"
sh.background_color = (0.96, 0.96, 0.95)
scene.render.film_transparent = False
scene.view_settings.view_transform = "Standard"

STRUCT = {"architecture", "structure", "floor", "ceiling", "wall", "exterior"}
COLORS = {"XS": (0.90, 0.30, 0.27, 1), "S": (0.96, 0.62, 0.20, 1), "M": (0.27, 0.53, 0.82, 1),
          "L": (0.36, 0.66, 0.42, 1), "wall": (0.86, 0.85, 0.83, 1), "floor": (0.70, 0.69, 0.67, 1)}
UNCOLORED = (0.55, 0.55, 0.55, 1)  # 上色模式下视频里取不到颜色的零件


def first_segment(o):
    for key in ("semantic_class", "instance_id"):
        v = str(o.get(key, "")).split("/", 1)[0].split(":", 1)[-1].strip().lower()
        if v:
            return v
    return o.name.split("/", 1)[0].split(".", 1)[0].strip().lower()


def world_bounds(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


meshes = [o for o in scene.objects if o.type == "MESH"]
info = {}
for o in meshes:
    lo, hi = world_bounds(o)
    seg = first_segment(o)
    name = (o.name + " " + str(o.get("semantic_class", ""))).lower()
    structural = seg in STRUCT or "wall" in name or "ceiling" in name or "floor" in name
    longest = max(hi - lo)
    if spec.get("colors") is not None:
        o.color = (*spec["colors"][o.name], 1) if o.name in spec["colors"] else UNCOLORED
    elif structural:
        o.color = COLORS["floor"] if ("floor" in name and "ceiling" not in name) else COLORS["wall"]
    else:
        o.color = COLORS["XS" if longest < 0.2 else "S" if longest < 0.5 else "M" if longest < 1.5 else "L"]
    info[o.name] = (lo, hi, structural, name)

cam_data = bpy.data.cameras.new("cmp_cam")
cam = bpy.data.objects.new("cmp_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
flip = Matrix(((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1)))  # OpenCV 相机 → Blender 相机
s = spec.get("scale", 0.75)
for v in spec["views"]:
    W, H = v["size_wh"]
    K = v["K"]
    scene.render.resolution_x, scene.render.resolution_y = int(W * s), int(H * s)
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36.0
    cam_data.lens = K[0][0] * 36.0 / W
    cam_data.shift_x = (W / 2 - K[0][2]) / W
    cam_data.shift_y = (K[1][2] - H / 2) / W
    cam_data.clip_start, cam_data.clip_end = 0.05, 100.0
    cam.matrix_world = Matrix(v["c2w"]) @ flip
    scene.render.filepath = f"{spec['out_dir']}/{v['name']}.png"
    bpy.ops.render.render(write_still=True)

# 整体图：用地面（没有地面就用非结构物体）定房间范围，从斜上方 50° 看向中心
floor = [n for n, (lo, hi, st, name) in info.items() if st and "floor" in name and "ceiling" not in name]
basis = floor or [n for n, (lo, hi, st, name) in info.items() if not st] or list(info)
lo = Vector((min(info[n][0].x for n in basis), min(info[n][0].y for n in basis), 0.0))
hi = Vector((max(info[n][1].x for n in basis), max(info[n][1].y for n in basis), 0.0))
room_top = max(h.z for (_, h, _, _) in info.values())
c = (lo + hi) / 2
c.z = 0.6
r = max((hi - lo).length, 2.0)
direction = Vector((0.55, -0.75, 0.0)).normalized()
eye = c + direction * 0.85 * r + Vector((0, 0, 1.15 * r))
for n, (blo, bhi, st, name) in info.items():
    o = scene.objects[n]
    ctr = (blo + bhi) / 2
    tall_thin = (bhi.z - blo.z) > 1.2 and min(bhi.x - blo.x, bhi.y - blo.y) < 0.35
    ceiling_like = "ceiling" in name or "roof" in name or (bhi.z > room_top - 0.05 and (bhi.z - blo.z) < 0.15)
    near_wall = st and tall_thin and (ctr - c).dot(direction) > 0.2 * r  # 靠近相机一侧的墙
    o.hide_render = ceiling_like or near_wall
if not floor:  # P0 这类没有房间壳的场景：垫一块地面，方便看清物体高度
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(c.x, c.y, 0.0))
    plane = bpy.context.active_object
    plane.scale = ((hi - lo).x + 1.0, (hi - lo).y + 1.0, 1.0)
    plane.color = COLORS["floor"]
cam_data.shift_x = cam_data.shift_y = 0.0
cam_data.sensor_fit = "AUTO"
cam_data.lens = 30
scene.render.resolution_x, scene.render.resolution_y = 1400, 1050
cam.location = eye
cam.rotation_euler = (c - eye).to_track_quat("-Z", "Y").to_euler()
scene.render.filepath = f"{spec['out_dir']}/overview.png"
bpy.ops.render.render(write_still=True)
print("rendered", len(spec["views"]) + 1)
