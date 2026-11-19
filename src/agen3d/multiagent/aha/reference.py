"""Invoke AHA's native reference preparation without translating legacy hull caches."""
from pathlib import Path
import json
import os
from ..models import ModelRegistry
from ..process import run_process
from ..store import save

PROJECT = Path(__file__).resolve().parents[4]


def environment(aha):
    # AHA's semantic subprocess imports SAM3 directly; runtime.json is provenance,
    # not a Python path loader. Use absolute paths because AHA changes cwd.
    return dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                PYTHONPATH=os.pathsep.join(map(str, [PROJECT / 'external/sam3',
                                                   Path(aha).resolve(), PROJECT / 'src'])))


def source_video(source):
    """Use RGB evidence only; never inspect simulator ground truth."""
    path = Path(source).resolve()
    if path.is_dir():
        candidates = [path / 'reference/original_camera_rgb.mp4', path / 'original_camera_rgb.mp4']
        path = next((p for p in candidates if p.is_file()), path)
    if not path.is_file():
        raise ValueError('Input must be a video or dataset/reference directory containing original_camera_rgb.mp4')
    return path


def prepare(output, *, video=None, bundle=None, timeout=3600, aha_repo=None, python=None,
            num_frames=32, pixel_limit=255000):
    if bool(video) == bool(bundle):
        raise ValueError('Supply exactly one source video or complete AHA bundle')
    out = Path(output).resolve()
    if out.exists():
        raise ValueError('Reference output must be new')
    aha = Path(aha_repo) if aha_repo else PROJECT / 'external/aha-3d'
    python = python or PROJECT / '.venv/bin/python'
    pi3x_python = PROJECT / '.venvs/pi3x-clean/bin/python'
    sam_python = PROJECT / '.venvs/sam3-clean/bin/python'
    registry = ModelRegistry()
    # AHA reference meshing needs Open3D in this interpreter. Probe before inference.
    from .doctor import probe
    check = probe([str(python), '-c', 'import open3d, numpy, scipy'])
    if not check['ok']:
        raise RuntimeError('AHA reference meshing runtime unavailable: ' + check.get('stderr', check.get('error', '')))
    command = [str(python), '-m', 'tools.layout_inspection.build_reference',
               '--out', str(out), '--pi3x-python', str(pi3x_python),
               '--upstream', str(PROJECT/'external/pi3'), '--semantic-python', str(sam_python),
               '--mesh-python', str(python), '--num-frames', str(num_frames),
               '--pixel-limit', str(pixel_limit)]
    sam_checkpoint = registry.resolve('model:sam3')
    if video:
        command += ['--video', str(Path(video).resolve()), '--checkpoint', str(registry.resolve('model:pi3x'))]
    else:
        command += ['--bundle', str(Path(bundle).resolve())]
    log = out.with_name(out.name + '.reference.log')
    out.parent.mkdir(parents=True, exist_ok=True)
    runtime = out.with_name(out.name + '.sam3-runtime')
    (runtime / 'checkpoints').mkdir(parents=True, exist_ok=False)
    (runtime / 'checkpoints/sam3.pt').symlink_to(sam_checkpoint)
    (runtime / 'runtime.json').write_text(json.dumps({'repo': str(PROJECT/'external/sam3'),
        'python': str(sam_python), 'checkpoint': str(sam_checkpoint),
        'revision': registry.specs['sam3']['revision']}))
    command += ['--semantic-runtime', str(runtime)]
    env = environment(aha)
    import fcntl
    # Same lease as construction generation; fail before launching concurrent GPU work.
    with log.open('x') as stream:
        with (out.parent / '.agen3d-gpu.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = run_process(command, cwd=aha, timeout=timeout, stdout=stream, stderr=stream, env=env)
    report = {'ok': result.returncode == 0, 'output': str(out), 'log': str(log),
              'scope': 'AHA reference evidence only; editable scene/layout spec still required'}
    save(out.with_name(out.name + '.reference-report.json'), report)
    return report
