"""论文定性对比图的渲染（blender -b scene.blend --python blender_paper_render.py -- spec.json）。只读场景，不保存 .blend。

spec：{"views": [{"name", "c2w"（OpenCV 相机到世界）, "K", "size_wh"}], "out_dir", "scale", "samples",
       "roles": {实例 id: "correct" | "misplaced" | "extra"}, 可选 "overview": true, "overview_dir": [x, y]}
所有运行用同一套灯光和材质（Cycles）：墙、地面、家具是中性色，只有 50 cm 以下的实例按结果上色
（roles 由 scripts/paper/qualitative.py 用评测代码算好：建对、配上但摆错、没有对应的标注）。
结构件不挡光，天光能照进房间；整体图藏掉天花板和靠近相机的墙。
"""
import json
import sys

import bpy
from mathutils import Matrix, Vector

spec = json.load(open(sys.argv[sys.argv.index("--") + 1]))
scene = bpy.context.scene
STRUCT = {"architecture", "structure", "floor", "ceiling", "wall", "exterior"}
# 线性 RGB。结果三色取自图表用的同一套色（蓝 #2a78d6、橙 #eb6834、青绿 #1baf7a）
PALETTE = {"wall": (0.72, 0.70, 0.66), "floor": (0.42, 0.36, 0.29), "neutral": (0.33, 0.35, 0.39),
           "correct": (0.023, 0.188, 0.672), "misplaced": (0.831, 0.138, 0.034), "extra": (0.011, 0.429, 0.195)}


def material(name, rgb):
    m = bpy.data.materials.new("paper_" + name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = 0.65
    return m


MATS = {k: material(k, v) for k, v in PALETTE.items()}

# 集合实例拆成真实物体，才能逐实例换材质（只在内存里，不保存）
empties = [o for o in scene.objects if o.instance_type == "COLLECTION" and o.instance_collection]
if empties:
    bpy.ops.object.select_all(action="DESELECT")
    for o in empties:
        o.select_set(True)
    bpy.context.view_layer.objects.active = empties[0]
    bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)


def owner(o):
    """和 AHa-3D export_model.object_group 同一规则：最近的带 instance_id 的祖先。"""
    root = o
    while root is not None:
        if root.get("instance_id"):
            return str(root["instance_id"]), str(root.get("semantic_class", ""))
        root = root.parent
    return "unassigned:" + o.name, ""


def world_bounds(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


roles = spec.get("roles", {})
info = {}
for o in [o for o in scene.objects if o.type == "MESH"]:
    gid, cls = owner(o)
    seg = (cls or gid).split("/", 1)[0].split(":", 1)[-1].strip().lower()
    name = (o.name + " " + cls + " " + gid).lower()
    structural = seg in STRUCT or gid.split("/", 1)[0].split(":", 1)[-1].strip().lower() in STRUCT
    if structural:
        key = "floor" if ("floor" in name and "ceiling" not in name) else "wall"
        # 结构件不挡光：阴影、漫反射和高光光线都穿过去，房间里外受光一致（只关阴影的话，封闭房间里会暗一半）
        o.visible_shadow = o.visible_diffuse = o.visible_glossy = False
    else:
        key = roles.get(gid, "neutral")
    if o.data.users > 1:
        o.data = o.data.copy()
    o.data.materials.clear()
    o.data.materials.append(MATS[key])
    lo, hi = world_bounds(o)
    info[o.name] = (lo, hi, structural, name)

for o in scene.objects:  # 场景自带的灯不用，统一打光
    if o.type == "LIGHT":
        o.hide_render = True
world = bpy.data.worlds.new("paper_world")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = spec.get("world", 0.8)
scene.world = world
sun_data = bpy.data.lights.new("paper_sun", "SUN")
sun_data.energy, sun_data.angle = spec.get("sun", 1.0), 0.35
sun = bpy.data.objects.new("paper_sun", sun_data)
scene.collection.objects.link(sun)
sun.rotation_euler = (0.65, 0.0, 0.6)

scene.render.engine = "CYCLES"
scene.cycles.samples = spec.get("samples", 96)
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                scene.cycles.device = "GPU"
                break
        except Exception:
            continue
except Exception:
    pass
print("cycles device", scene.cycles.device)
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"

cam_data = bpy.data.cameras.new("paper_cam")
cam = bpy.data.objects.new("paper_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
flip = Matrix(((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1)))  # OpenCV 相机 → Blender 相机
s = spec.get("scale", 1.0)
for v in spec["views"]:
    W, H = v["size_wh"]
    K = v["K"]
    scene.render.resolution_x, scene.render.resolution_y = int(W * s), int(H * s)
    scene.render.resolution_percentage = 100
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
    # 整体图：用地面定房间范围，从斜上方看向中心；藏掉天花板和靠近相机一侧的墙
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
    eye = c + direction * 0.85 * r + Vector((0, 0, 1.15 * r))
    for n, (blo, bhi, st, name) in info.items():
        o = scene.objects[n]
        ctr = (blo + bhi) / 2
        tall_thin = (bhi.z - blo.z) > 1.2 and min(bhi.x - blo.x, bhi.y - blo.y) < 0.35
        ceiling_like = "ceiling" in name or "roof" in name or (bhi.z > room_top - 0.05 and (bhi.z - blo.z) < 0.15)
        near_wall = st and tall_thin and (ctr - c).dot(direction) > 0.2 * r
        o.hide_render = ceiling_like or near_wall
    scene.render.film_transparent = True
    cam_data.shift_x = cam_data.shift_y = 0.0
    cam_data.sensor_fit = "AUTO"
    cam_data.lens = 32
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1200
    cam.location = eye
    cam.rotation_euler = (c - eye).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{spec['out_dir']}/overview.png"
    bpy.ops.render.render(write_still=True)
print("rendered", len(spec["views"]) + int(bool(spec.get("overview"))))
