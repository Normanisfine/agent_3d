"""Real offline integration: build/reopen an AHA object and reject a scope violation."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from agen3d.multiagent.aha.isolation import execute
from agen3d.multiagent.aha.runtime import HERE
from agen3d.multiagent.process import run_process
from agen3d.multiagent.store import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    c = SimpleNamespace(aha_repo=str(root/'external/aha-3d'),
        blender=str(root.parent/'tools/blender/blender-4.5.14-linux-x64/blender'), timeout_s=120)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out/'input.blend'
    code = 'import bpy; bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False); bpy.ops.wm.save_as_mainfile(filepath=' + repr(str(source)) + ')'
    with (out/'seed.log').open('w') as log:
        result = run_process([c.blender, '-b', '--factory-startup', '--python-exit-code', '1',
                              '--python-expr', code], timeout=120, stdout=log, stderr=log)
    result.check_returncode()
    proposal = {'route': 'code', 'object_ids': ['table']}
    save(out/'request.json', {'proposal': proposal})
    (out/'build.py').write_text('roomkit.box("tabletop", (0,0,0.75), (1.2,0.6,0.08), '
                              'semantic_class="furniture/table", instance_id="table")\n')
    execute(c, out, HERE/'blender_worker.py', out/'request.json')
    save(out/'verify.json', {'proposal': proposal, 'verify_only': True})
    execute(c, out, HERE/'blender_worker.py', out/'verify.json')
    validation = json.loads((out/'validation.json').read_text())
    assert validation['ok'] and validation['changed_ids'] == ['table']
    good = out/'good.blend'
    import shutil
    shutil.copy2(out/'scene.blend', good)
    # Exercise a real catalog collection through the same importer/normalizer.
    catalog = json.loads((root/'external/aha-3d/assets/index.json').read_text())['entries']
    asset = next(e['id'] for e in catalog if e.get('kind') == 'collection' and e.get('status') == 'registered')
    imported = {'route': 'asset', 'object_ids': ['table'], 'asset_id': asset,
                'dimensions': [1., 1., 1.], 'location': [0., 0., 0.], 'rotation_z': 0.}
    save(out/'asset.json', {'proposal': imported})
    execute(c, out, HERE/'blender_worker.py', out/'asset.json')
    save(out/'asset-verify.json', {'proposal': imported, 'verify_only': True})
    execute(c, out, HERE/'blender_worker.py', out/'asset-verify.json')
    # Generated-mesh conversion is tested with a known GLB, independently of Hunyuan inference.
    export_code = 'import bpy; bpy.ops.wm.open_mainfile(filepath=' + repr(str(good)) + '); bpy.ops.export_scene.gltf(filepath=' + repr(str(out/'mesh.glb')) + ',export_format="GLB")'
    with (out/'export.log').open('w') as log:
        result = run_process([c.blender, '-b', '--factory-startup', '--disable-autoexec',
            '--python-exit-code', '1', '--python-expr', export_code], timeout=120, stdout=log, stderr=log)
    result.check_returncode()
    imported.update(route='hunyuan', semantic_class='furniture/table')
    save(out/'mesh.json', {'proposal': imported})
    execute(c, out, HERE/'blender_worker.py', out/'mesh.json')
    save(out/'mesh-verify.json', {'proposal': imported, 'verify_only': True})
    execute(c, out, HERE/'blender_worker.py', out/'mesh-verify.json')
    # Actual runtime must reject out-of-scope geometry, not just validate JSON.
    (out/'build.py').write_text('roomkit.box("wrong", (0,0,1), (1,1,1), '
                              'semantic_class="furniture/chair", instance_id="other")\n')
    try:
        execute(c, out, HERE/'blender_worker.py', out/'request.json')
    except RuntimeError:
        rejection = True
    else:
        rejection = False
    assert rejection
    save(out/'smoke.json', {'build_and_reopen': True, 'catalog_import': asset,
                           'generated_glb_conversion': True, 'hunyuan_inference_tested': False,
                           'out_of_scope_rejected': rejection,
                           'quality_claim': 'Tool contract only, not reconstruction fidelity'})
    print(json.dumps({'ok': True, 'report': str(out/'smoke.json')}))


if __name__ == '__main__':
    main()
