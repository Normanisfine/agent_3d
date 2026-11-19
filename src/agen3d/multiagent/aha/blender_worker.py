"""Trusted bootstrap and validator, run INSIDE the construction sandbox."""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, '/aha/src')
from aha3d.blender import roomkit
sys.modules.setdefault('roomkit', roomkit)
from aha3d.blender.semantics import roots, descendants, tag_root
from aha3d.blender.variants import place_asset


def material_state(material):
    if material is None:
        return None
    result = {'name': material.name, 'color': list(material.diffuse_color),
              'roughness': material.roughness, 'metallic': material.metallic}
    if material.use_nodes:
        result['nodes'] = []
        for node in material.node_tree.nodes:
            values = {}
            for socket in node.inputs:
                if hasattr(socket, 'default_value'):
                    value = socket.default_value
                    if isinstance(value, (bool, int, float, str)):
                        values[socket.identifier] = value
                    elif hasattr(value, '__len__'):
                        values[socket.identifier] = list(value)
            row = {'name': node.name, 'type': node.bl_idname, 'values': values}
            image = getattr(node, 'image', None)
            if image:
                row['image'] = image.name
                if image.packed_file:
                    row['packed_sha256'] = hashlib.sha256(image.packed_file.data).hexdigest()
            result['nodes'].append(row)
        result['links'] = sorted((link.from_node.name, link.from_socket.identifier,
                                  link.to_node.name, link.to_socket.identifier)
                                 for link in material.node_tree.links)
    return result


def inventory():
    bpy.context.view_layer.update()
    result = {}
    for root in roots():
        if root['instance_id'] in result:
            raise ValueError('Duplicate semantic root: ' + root['instance_id'])
        parts = [o for o in [root, *descendants(root)] if o.type == 'MESH']
        points = [o.matrix_world @ v.co for o in parts for v in o.data.vertices]
        if not points or not all(math.isfinite(x) for p in points for x in p):
            raise ValueError('Empty/nonfinite semantic geometry: ' + root['instance_id'])
        lo = [min(p[i] for p in points) for i in range(3)]
        hi = [max(p[i] for p in points) for i in range(3)]
        if max(hi[i] - lo[i] for i in range(3)) > 10000:
            raise ValueError('Implausibly large geometry')
        signature = hashlib.sha256(json.dumps([
            {'name': o.name, 'matrix': [list(r) for r in o.matrix_world],
             'vertices': [list(v.co) for v in o.data.vertices],
             'faces': [list(p.vertices) for p in o.data.polygons],
             'hidden': [o.hide_render, o.hide_viewport],
             'materials': [material_state(m) for m in o.data.materials]}
            for o in parts], sort_keys=True).encode()).hexdigest()
        result[root['instance_id']] = {'class': root.get('semantic_class'),
            'parts': len(parts), 'min': lo, 'max': hi, 'signature': signature}
    return result


def cameras():
    return {o.name: {'matrix': [list(r) for r in o.matrix_world], 'lens': o.data.lens,
                     'type': o.data.type, 'ortho_scale': o.data.ortho_scale}
            for o in bpy.context.scene.objects if o.type == 'CAMERA'}


def remove(identity):
    for root in roots():
        if root['instance_id'] == identity:
            for obj in reversed([root, *descendants(root)]):
                bpy.data.objects.remove(obj, do_unlink=True)


def merge_objects(ids):
    """Append only assigned semantic hierarchies; never replace the canonical scene."""
    for identity in ids:
        remove(identity)
    with bpy.data.libraries.load('/work/candidate.blend', link=False) as (source, target):
        target.objects = list(source.objects)
    loaded = [obj for obj in target.objects if obj is not None]
    selected_roots = [obj for obj in loaded if obj.get('instance_id') in ids]
    if len(selected_roots) != len(ids) or {obj.get('instance_id') for obj in selected_roots} != set(ids):
        raise ValueError('Merge requires exactly one root per assigned object')
    keep = set(selected_roots)
    for root in selected_roots:
        keep.update(descendants(root))
    if any(obj.get('instance_id') and obj.get('instance_id') not in ids for obj in keep):
        raise ValueError('Parallel merge contains an unassigned nested semantic root')
    for obj in keep:
        if obj.parent is not None and obj.parent not in keep:
            raise ValueError('Parallel objects cannot depend on external parent transforms')
        local_modifiers = {'BEVEL', 'WEIGHTED_NORMAL', 'SUBSURF', 'TRIANGULATE', 'SOLIDIFY', 'DECIMATE'}
        if obj.constraints or obj.animation_data or any(m.type not in local_modifiers for m in obj.modifiers):
            raise ValueError('Parallel merge requires object-local geometry without external dependencies')
        for material in getattr(obj.data, 'materials', []):
            if material and material.use_nodes:
                for node in material.node_tree.nodes:
                    reference = getattr(node, 'object', None)
                    if reference is not None and reference not in keep:
                        raise ValueError('Material refers to an external object')
        if obj.type == 'CAMERA':
            raise ValueError('Parallel merge cannot import cameras')
        bpy.context.scene.collection.objects.link(obj)
    for obj in loaded:
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)


def main():
    req = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text())
    bpy.ops.wm.open_mainfile(filepath='/work/input.blend', load_ui=False)
    before = inventory()
    before_cameras = cameras()
    if req.get('inspect_only'):
        Path('/work/inventory.json').write_text(json.dumps({'objects': before, 'cameras': before_cameras}))
        return
    proposal = req['proposal']
    ids = proposal['object_ids']
    if req.get('verify_only'):
        bpy.ops.wm.open_mainfile(filepath='/work/scene.blend', load_ui=False)
    elif req.get('merge_only'):
        merge_objects(ids)
    elif proposal['route'] == 'code':
        # This is deliberately real Python, protected by OS isolation, not an AST pseudo-sandbox.
        exec(compile(Path('/work/build.py').read_text(), '/work/build.py', 'exec'),
             {'bpy': bpy, 'roomkit': roomkit, 'tag_root': tag_root,
              'remove_object': remove, 'object_ids': ids, '__name__': '__construction__'})
    else:
        remove(ids[0])
        if proposal['route'] == 'asset':
            root = place_asset(proposal['asset_id'], instance_id=ids[0], project_root='/aha')
        elif proposal['route'] == 'hunyuan':
            bpy.ops.import_scene.gltf(filepath='/work/mesh.glb')
            objects = list(bpy.context.selected_objects)
            root = bpy.data.objects.new(ids[0], None)
            bpy.context.scene.collection.objects.link(root)
            for obj in objects:
                if obj.parent not in objects:
                    matrix = obj.matrix_world.copy()
                    obj.parent = root
                    obj.matrix_world = matrix
            root = tag_root(root, proposal['semantic_class'], ids[0])
        else:
            raise ValueError('Unsupported build route')
        points = [o.matrix_world @ v.co for o in descendants(root)
                  if o.type == 'MESH' for v in o.data.vertices]
        lo = Vector([min(p[i] for p in points) for i in range(3)])
        hi = Vector([max(p[i] for p in points) for i in range(3)])
        extent = hi - lo
        if min(extent) < 1e-6:
            raise ValueError('Degenerate imported bounds')
        # Normalize children around bottom-center before applying scene placement.
        center = Vector(((lo.x + hi.x)/2, (lo.y + hi.y)/2, lo.z))
        for obj in root.children:
            obj.location -= center
        root.scale = [proposal['dimensions'][i]/extent[i] for i in range(3)]
        root.rotation_euler.z = proposal['rotation_z']
        root.location = proposal['location']
    after = inventory()
    if req.get('merge_only'):
        expected = req['expected_objects']
        for identity in ids:
            actual = after[identity]
            if actual['class'] != expected[identity]['class'] or actual['parts'] != expected[identity]['parts']:
                raise ValueError('Merge changed semantic hierarchy')
            if any(abs(a-b) > 1e-5 for key in ('min', 'max')
                   for a, b in zip(actual[key], expected[identity][key])):
                raise ValueError('Merge changed candidate bounds')
    for image in bpy.data.images:
        if image.source == 'FILE' and not image.packed_file and image.filepath and not Path(bpy.path.abspath(image.filepath)).is_file():
            raise ValueError('Missing texture dependency: ' + image.name)
    if cameras() != before_cameras:
        raise ValueError('Construction modified reviewed cameras')
    if not set(ids) <= set(after):
        raise ValueError('Program did not construct every required semantic root')
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    if not changed or not changed <= set(ids):
        raise ValueError('No geometry change or changes outside authorized semantic IDs')
    for identity in ids:
        root = next(o for o in roots() if o['instance_id'] == identity)
        if root.get('representation') == 'observed_point_hull':
            raise ValueError('Target remains an observed-point hull')
    if not req.get('verify_only'):
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath='/work/scene.blend')
    Path('/work/validation.json').write_text(json.dumps({'ok': True, 'changed_ids': sorted(changed),
                                                       'objects': after}, indent=2))


if __name__ == '__main__':
    main()
