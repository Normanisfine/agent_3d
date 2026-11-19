"""Executable capability probes; existence is never reported as inference success."""
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..models import ModelRegistry
from ..process import run_process
from . import isolation

PROJECT = Path(__file__).resolve().parents[4]
IMPORTS = {
    'pi3x': ('pi3', 'pi3x-clean', 'from pi3.models.pi3x import Pi3X'),
    'sam3': ('sam3', 'sam3-clean', 'from sam3.model_builder import build_sam3_image_model'),
    'hunyuan-shape': ('hunyuan3d-2.1', 'hunyuan', 'from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline'),
    'sam3d': ('sam-3d-objects', 'sam3d', 'from inference import Inference'),
    'hispatial': ('hispatial', 'hispatial', 'from hispatial.inference import HiSpatialPredictor'),
}


def probe(command, timeout=120, **kwargs):
    try:
        p = run_process(command, timeout=timeout, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, **kwargs)
        return {'ok': p.returncode == 0, 'exit_code': p.returncode,
                'stdout': p.stdout[-2500:], 'stderr': p.stderr[-2500:]}
    except Exception as exc:
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}


def check(config=None, cuda=False, full_hashes=False):
    project = PROJECT
    aha = Path(config.aha_repo) if config else project / 'external/aha-3d'
    blender = Path(config.blender) if config else project.parent / 'tools/blender/blender-4.5.14-linux-x64/blender'
    python = config.python if config else str(project / '.venv/bin/python')
    checks = []
    for name, command in [('blender', [str(blender), '--background', '--factory-startup', '--disable-autoexec',
                                      '--python-exit-code', '1', '--python-expr',
                                      'import bpy; print("BLENDER_OK", bpy.app.version_string)']),
                          ('codex_cli', ['codex', '--version']), ('claude_cli', ['claude', '--version'])]:
        checks.append({'component': name, 'level': 'execution', **probe(command)})
    script = ('import sys; sys.path.insert(0, sys.argv[1]); '
              'from aha3d.workflow import layout_gate, object_review, acceptance; '
              'from aha3d.pipeline import runner; print("AHA_IMPORT_OK")')
    checks.append({'component': 'aha_python', 'level': 'import',
                   **probe([python, '-c', script, str(aha / 'src')])})
    checks.append({'component': 'aha_reference_meshing', 'level': 'import',
                   **probe([python, '-c', 'import open3d, numpy, scipy; print("MESH_RUNTIME_OK")'])})
    with tempfile.TemporaryDirectory(prefix='agen3d-isolation-') as tmp:
        folder = Path(tmp)
        script = folder / 'probe.py'
        script.write_text('import os, pathlib, socket\n'
                          'assert not pathlib.Path("/home/mj/.codex").exists()\n'
                          'assert "OPENROUTER_API_KEY" not in os.environ\n'
                          'pathlib.Path("/work/receipt").write_text("ok")\n')
        cmd = isolation.command(str(blender), str(aha), folder, script, folder / 'unused.json')
        result = probe(cmd)
        result['ok'] = result['ok'] and (folder / 'receipt').exists()
        checks.append({'component': 'generated_code_isolation', 'level': 'execution', **result})
    registry = ModelRegistry()
    for name, (repo, runtime, imports) in IMPORTS.items():
        interpreter = project / '.venvs' / runtime / 'bin/python'
        repository = project / 'external' / repo
        if name == 'hunyuan-shape' and config and config.hunyuan:
            interpreter, repository = Path(config.hunyuan.python), Path(config.hunyuan.repo)
        paths = [repository, repository / 'hy3dshape', repository / 'notebook']
        script = ('import sys; sys.path[:0]=sys.argv[1:]; import torch; ' + imports + '; '
                  + ('assert torch.cuda.is_available(), "CUDA unavailable"; '
                     'x=torch.ones((16,16),device="cuda"); y=x@x; torch.cuda.synchronize(); '
                     if cuda else '') + 'print("IMPORT_OK", torch.__version__)')
        result = probe([str(interpreter), '-c', script, *map(str, paths)])
        checks.append({'component': name, 'level': 'cuda_tensor_and_import' if cuda else 'import',
                       'repo': str(repository), 'python': str(interpreter), **result})
        verification = registry.verify(name, full=full_hashes)
        checks.append({'component': name + '_checkpoint', 'level': verification['verification'],
                       'ok': verification['ok'], 'failures': verification['failures']})
    if cuda:
        checks.append({'component': 'gpu', 'level': 'driver',
                       **probe(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'])})
    if config:
        if config.preparation:
            from .reference import source_video, environment
            checks.append({'component': 'preparation_sam3_import', 'level': 'subprocess_import',
                **probe([str(project / '.venvs/sam3-clean/bin/python'), '-c',
                    'import tools.layout_inspection.semantic; '
                    'from sam3.model_builder import build_sam3_image_model; '
                    'print("AHA_SAM3_IMPORT_OK")'], cwd=aha, env=environment(aha))})
            try:
                source = source_video(config.preparation.input)
                checks.append({'component': 'preparation_input', 'level': 'exists', 'ok': True, 'path': str(source)})
            except ValueError as exc:
                checks.append({'component': 'preparation_input', 'level': 'exists', 'ok': False, 'error': str(exc)})
        else:
            for name in ('source_scene', 'layout_spec'):
                checks.append({'component': name, 'level': 'exists', 'ok': Path(getattr(config, name)).is_file()})
        for key, path in {**config.source_images, **config.masks}.items():
            checks.append({'component': 'evidence:' + key, 'level': 'exists', 'ok': Path(path).is_file()})
        checks.append({'component': 'worker_credentials', 'level': 'presence_only',
                       'ok': bool(os.environ.get(config.worker.api_key_env))})
    required = {'blender', 'aha_python', 'generated_code_isolation', 'codex_cli'}
    if config:
        required |= {'worker_credentials'}
        required |= ({'preparation_input', 'preparation_sam3_import', 'aha_reference_meshing', 'pi3x', 'pi3x_checkpoint',
                      'sam3', 'sam3_checkpoint'} if config.preparation else {'source_scene', 'layout_spec'})
        required |= {'evidence:' + k for k in {**config.source_images, **config.masks}}
        if config.supervisor.backend == 'claude':
            required.add('claude_cli')
        if config.hunyuan:
            required |= {'hunyuan-shape', 'hunyuan-shape_checkpoint'}
    return {'architecture': 'aha', 'checked_at': datetime.now(timezone.utc).isoformat(),
            'required_ready': all(c['ok'] for c in checks if c['component'] in required),
            'all_tools_ready': all(c['ok'] for c in checks), 'checks': checks,
            'not_tested': ['hosted model authentication/inference', 'model checkpoint inference',
                           'source-specific AHA layout acceptance', 'end-to-end reconstruction quality'],
            'note': 'Optional specialists are reported separately; no models downloaded or paid calls made.'}
