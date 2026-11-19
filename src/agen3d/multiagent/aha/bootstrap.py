"""Build construction inputs from native AHA output, without importing reference geometry."""
import hashlib
import json
from pathlib import Path

import numpy as np

from ..store import save
from .isolation import execute


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def bootstrap(config, reference, output, video):
    reference, output = Path(reference), Path(output)
    report = json.loads((reference / 'reference_build.json').read_text())
    cameras_path = Path(report['cameras'])
    cameras = json.loads(cameras_path.read_text())
    layers = Path(report['mesh'])
    bundle = Path(report['bundle'])
    views_path = Path(report['source_views'])
    views = json.loads(views_path.read_text())
    selected = views['source_frame_indices']
    if len(selected) < 3:
        raise ValueError('Construction requires at least three native source views')
    with np.load(layers, allow_pickle=False) as ref:
        valid = ref['geometry_valid'].astype(bool) & (ref['layer'] == 0)
        points = ref['vertices'][valid]
        points = points[np.isfinite(points).all(axis=1)]
        if not len(points):
            raise ValueError('No valid static reference geometry')
        lo, hi = points.min(axis=0), points.max(axis=0)
    margin = np.maximum((hi - lo) * .05, .25)
    crop = np.column_stack([lo - margin, hi + margin]).tolist()
    center = (lo + hi) / 2
    scale = float(max(hi - lo + 2 * margin) * 1.1)
    inspection = {'model_to_world': np.eye(4).tolist(),
        'model_transform_reason': 'Empty authored scene initialized directly in the AHA reference world basis; '
                                  'predicted scale, not calibrated ground truth.',
        'source_frames': selected, 'resolution': 700, 'views': {}}
    for name, direction in [('top', [0, 0, 1]), ('front', [0, -1, 0]), ('side', [1, 0, 0])]:
        inspection['views'][name] = {'location': (center + np.array(direction) * scale * 2).tolist(),
            'target': center.tolist(), 'ortho_scale': scale, 'crop_xyz_m': crop}
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'inspection.json', inspection)
    save(output / 'request.json', cameras)
    execute(config, output, Path(__file__).with_name('seed_worker.py'), output / 'request.json')
    if not (output / 'seed.blend').is_file():
        raise RuntimeError('Seed builder did not save a scene')
    spec = {'reference': str(layers), 'cameras': str(cameras_path),
        'inputs': str(bundle / 'inputs.npz'), 'inputs_metadata': str(bundle / 'inputs.json'),
        'reference_manifest': str(layers.with_name('manifest.json')),
        'config': str(output / 'inspection.json'), 'source_video': str(video)}
    save(output / 'layout_spec.json', spec)
    return handoff(reference, output)


def handoff(reference, output, *, restore=False):
    reference, output = Path(reference), Path(output)
    if restore:
        saved = json.loads((output / 'reference-binding.json').read_text())
        if any(digest(p) != h for p, h in saved['hashes'].items()):
            raise ValueError('Prepared inputs changed since the previous review attempt')
    spec = json.loads((output / 'layout_spec.json').read_text())
    report = json.loads((reference / 'reference_build.json').read_text())
    views_path = Path(report['source_views'])
    selected = json.loads(views_path.read_text())['source_frame_indices']
    sources, images = {}, {}
    for frame in selected:
        name = f'source_{frame:06d}'
        sources[name] = str(views_path.parent / (name + '_source.png'))
        for suffix in ('source', 'reference', 'overlay'):
            images[name + '_' + suffix] = str(views_path.parent / (name + '_' + suffix + '.png'))
    alignment = json.loads(Path(report['alignment']).read_text()) if report.get('alignment') else {}
    for i, path in enumerate(sorted((reference / 'alignment').glob('*_support.png'))):
        images[f'alignment_{i:03d}'] = str(path)
    # Bind every numerical input and review image, not merely a model's declaration.
    binding = {str(p): digest(p) for p in [*spec.values(), *images.values(),
               output / 'seed.blend', output / 'layout_spec.json', views_path,
               reference / 'reference_build.json',
               *([report['alignment']] if report.get('alignment') else [])]}
    revision = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    if not restore:
        save(output / 'reference-binding.json', {'revision': revision, 'hashes': binding})
    return {'source_scene': str(output / 'seed.blend'), 'layout_spec': str(output / 'layout_spec.json'),
            'source_images': sources, 'review_images': images, 'revision': revision,
            'alignment': alignment, 'binding': binding}
