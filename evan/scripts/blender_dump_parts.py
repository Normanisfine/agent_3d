"""把场景里每个网格零件的世界坐标三角形和它的根节点写出来（blender -b scene.blend --python blender_dump_parts.py -- out.npz）。

根节点：往上找最高一层带 instance_id 的祖先（AHa-3D 的语义根），找不到就用最顶层的祖先。只读场景。
输出：names、roots（每个零件一项）、offsets（零件 i 的三角形是 tris[offsets[i]:offsets[i+1]]）、tris (T, 3, 3)。
"""
import sys

import bpy
import numpy as np

out = sys.argv[sys.argv.index("--") + 1]
deps = bpy.context.evaluated_depsgraph_get()
names, roots, chunks = [], [], []
for o in bpy.context.scene.objects:
    if o.type != "MESH" or o.hide_render:
        continue
    root, p = o, o
    tagged = o if "instance_id" in o.keys() else None
    while p.parent is not None:
        p = p.parent
        root = p
        if "instance_id" in p.keys():
            tagged = p
    root = tagged or root
    ev = o.evaluated_get(deps)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    if n:
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        tri = np.empty(n * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", tri)
        M = np.array(o.matrix_world)
        w = co @ M[:3, :3].T + M[:3, 3]
        chunks.append(w[tri.reshape(-1, 3)])
        names.append(o.name)
        roots.append(root.name)
    ev.to_mesh_clear()
offsets = np.cumsum([0] + [len(c) for c in chunks])
np.savez_compressed(out, names=np.array(names), roots=np.array(roots), offsets=offsets,
                    tris=np.concatenate(chunks) if chunks else np.zeros((0, 3, 3)))
print("dumped", len(names))
