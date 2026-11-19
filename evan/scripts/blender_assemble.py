"""在 Blender 里把 P0 的结果拼成 .blend（blender -b --factory-startup --python blender_assemble.py -- spec.json）。

接受的生成网格：导入 GLB（Blender 会把 glTF 的 Y 朝上转成 Z 朝上；我们的 GLB 顶点本来就是 Z 朝上，
所以 matrix_world 右乘 C_inv 抵消这一步），其余物体放长方体。每个对象的名字是清单 ID，
自定义属性 instance_id / semantic_class 和 AHa-3D 的导出脚本一致，方便用同一套 export_blend 导出核对。
"""
import json
import math
import sys

import bpy
from mathutils import Matrix

spec = json.load(open(sys.argv[sys.argv.index("--") + 1]))
bpy.ops.wm.read_factory_settings(use_empty=True)
C_inv = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
for o in spec["objects"]:
    oid = o["object_id"]
    if oid in spec["meshes"]:
        m = spec["meshes"][oid]
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=m["mesh_glb"])
        new = [x for x in bpy.data.objects if x not in before and x.type == "MESH"]
        obj = new[0]
        obj.parent = None
        obj.matrix_world = Matrix(m["matrix_world"]) @ C_inv
    else:
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        obj = bpy.context.active_object
        obj.scale = o["size"]
        obj.rotation_euler = (0.0, 0.0, o["yaw"])
        obj.location = o["center"]
    obj.name = oid
    obj["instance_id"] = oid
    obj["semantic_class"] = o["category"]
# 导入 GLB 时可能带进空的父节点，删掉
for x in list(bpy.data.objects):
    if x.type != "MESH":
        bpy.data.objects.remove(x)
bpy.ops.wm.save_as_mainfile(filepath=spec["out"])
print("saved", spec["out"], len(spec["objects"]))
