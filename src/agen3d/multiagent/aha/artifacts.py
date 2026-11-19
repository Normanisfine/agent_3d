"""Diagnostic exports are independent of visual acceptance and canonical commits."""
import json
import shutil
import time
from pathlib import Path

from ..store import save


def record_candidate(folder, scene, parent, task):
    from .runtime import digest
    save(folder / 'artifact.json', {
        'scene': str(scene), 'revision': digest(scene), 'parent_revision': parent,
        'task_id': task.task_id, 'object_ids': task.object_ids,
        'validation_sha256': digest(folder / 'validation.json'),
        'verified_at_ns': time.time_ns(),
    })


def export_output(runtime):
    """Prefer a verified extension of current; never splice unreviewed branches."""
    from .runtime import digest
    current = Path(runtime.current) if runtime.current else None
    if current is None or not current.is_file():
        receipt = {'status': 'unavailable', 'scene': None, 'delivery_accepted': False,
                   'reason': 'No usable scene was produced; inspect the run failure.'}
        save(runtime.output / 'output.json', receipt)
        return receipt
    if digest(current) != runtime.revision:
        raise ValueError('Canonical scene changed before diagnostic export')
    eligible = []
    excluded = []
    # Only serial candidates and explicitly merged branches can replace current.
    for marker in (runtime.output / 'candidates').glob('*/artifact.json'):
        try:
            row = json.loads(marker.read_text())
            scene = Path(row['scene'])
            validation_path = marker.parent / 'validation.json'
            if row['parent_revision'] != runtime.revision:
                continue
            if (digest(scene) != row['revision'] or
                    digest(validation_path) != row['validation_sha256'] or
                    not json.loads(validation_path.read_text()).get('ok')):
                raise ValueError('Candidate or validation changed')
            eligible.append(row)
        except (OSError, ValueError, KeyError) as exc:
            excluded.append({'artifact': str(marker), 'error': str(exc)})
    chosen = max(eligible, key=lambda row: row['verified_at_ns']) if eligible else None
    source = Path(chosen['scene']) if chosen else current
    revision = chosen['revision'] if chosen else runtime.revision
    target = runtime.output / 'final_scene.blend'
    temporary = runtime.output / '.final_scene.blend.tmp'
    shutil.copy2(source, temporary)
    if digest(temporary) != revision:
        temporary.unlink(missing_ok=True)
        raise ValueError('Scene changed during diagnostic export')
    temporary.replace(target)
    review_path = source.parent / 'local-review.json'
    review = json.loads(review_path.read_text()) if review_path.exists() else None
    if review and review.get('candidate_revision') != revision:
        review = None
    receipt = {
        'status': 'candidate_exported', 'scene': str(target), 'revision': revision,
        'source_scene': str(source), 'canonical_scene': str(current),
        'canonical_revision': runtime.revision,
        'selection': 'latest_verified_extension' if chosen else 'canonical_fallback',
        'task_id': chosen['task_id'] if chosen else None,
        'local_review': review, 'delivery_accepted': False,
        'excluded_candidates': excluded,
        'limitations': [
            'Diagnostic candidate, possibly incomplete or rejected; filename does not imply acceptance.',
            'Latest verified extension is a deterministic fallback, not a quality ranking.',
            'Unmerged parallel branches are retained separately and are not combined into this scene.',
            'Byte copy preserves authored cameras; no camera animation, asset packing or final video is added. '
            'External resources retain their original paths; use source_scene if relative resources are unresolved.',
        ],
    }
    save(runtime.output / 'output.json', receipt)
    return receipt


def safe_export(runtime):
    """An export failure must not discard the original run report or session state."""
    try:
        return export_output(runtime)
    except Exception as exc:
        receipt = {'status': 'export_failed', 'scene': None, 'delivery_accepted': False,
                   'error': f'{type(exc).__name__}: {exc}'}
        save(runtime.output / 'output.json', receipt)
        return receipt
