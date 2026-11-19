"""Fixed isolated Blender bootstrap: empty authored scene plus native cameras."""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


def main():
    data = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text())
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    width, height = data['processed_size_wh']
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    for row in data['frames']:
        name = f"source_{row['source_frame']:06d}"
        camera = bpy.data.cameras.new(name)
        obj = bpy.data.objects.new(name, camera)
        scene.collection.objects.link(obj)
        obj.matrix_world = Matrix(row['c2w']) @ Matrix.Diagonal((1, -1, -1, 1))
        k = row['intrinsics']
        camera.sensor_fit = 'HORIZONTAL'
        camera.sensor_width = 36
        camera.lens = k[0][0] * 36 / width
        ratio = k[0][0] / k[1][1]
        camera.shift_x = (width / 2 - k[0][2]) / width
        camera.shift_y = (k[1][2] - height / 2) * ratio / width
        obj['source_frame'] = row['source_frame']
        obj['source_intrinsics'] = json.dumps(k)
        obj['pixel_aspect_ratio'] = ratio
        if scene.camera is None:
            scene.camera = obj
            scene.render.pixel_aspect_x = max(1., 1. / ratio)
            scene.render.pixel_aspect_y = max(1., ratio)
    bpy.ops.wm.save_as_mainfile(filepath='/work/seed.blend')


if __name__ == '__main__':
    main()
