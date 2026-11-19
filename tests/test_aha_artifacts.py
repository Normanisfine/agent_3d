"""Failure output must preserve useful geometry without bypassing acceptance."""
import json
from types import SimpleNamespace

from agen3d.multiagent.aha.artifacts import record_candidate, export_output, safe_export
from agen3d.multiagent.aha.runtime import digest
from agen3d.multiagent.store import save


def runtime(tmp_path):
    scene = tmp_path / 'seed.blend'
    scene.write_bytes(b'canonical')
    return SimpleNamespace(output=tmp_path, current=scene, revision=digest(scene))


def candidate(r, name='first', parent=None):
    folder = r.output / 'candidates' / name
    folder.mkdir(parents=True)
    scene = folder / 'scene.blend'
    scene.write_bytes(name.encode())
    save(folder / 'validation.json', {'ok': True})
    record_candidate(folder, scene, parent or r.revision,
                     SimpleNamespace(task_id=name, object_ids=[name]))
    return scene


def test_rejected_candidate_exported_without_commit(tmp_path):
    r = runtime(tmp_path)
    scene = candidate(r)
    save(scene.parent / 'local-review.json', {'candidate_revision': digest(scene),
         'verdict': 'repair', 'defects': ['Window too tall']})
    result = export_output(r)
    assert result['local_review']['verdict'] == 'repair'
    assert result['delivery_accepted'] is False
    assert (tmp_path / 'final_scene.blend').read_bytes() == b'first'
    assert r.current.read_bytes() == b'canonical'


def test_no_visual_receipt_still_exports_verified_geometry(tmp_path):
    r = runtime(tmp_path)
    candidate(r)
    result = export_output(r)
    assert result['selection'] == 'latest_verified_extension'
    assert result['local_review'] is None


def test_stale_or_tampered_candidates_do_not_replace_canonical(tmp_path):
    r = runtime(tmp_path)
    candidate(r, 'stale', 'old-revision')
    scene = candidate(r, 'tampered')
    scene.write_bytes(b'changed')
    result = export_output(r)
    assert result['selection'] == 'canonical_fallback'
    assert len(result['excluded_candidates']) == 1
    assert (tmp_path / 'final_scene.blend').read_bytes() == b'canonical'


def test_failed_build_and_unmerged_branch_not_selected(tmp_path):
    r = runtime(tmp_path)
    folder = tmp_path / 'candidates' / 'failed'
    folder.mkdir(parents=True)
    (folder / 'scene.blend').write_bytes(b'invalid')
    branch = tmp_path / 'parallel' / 'wave-0001' / 'desk' / 'candidate'
    branch.mkdir(parents=True)
    (branch / 'scene.blend').write_bytes(b'branch')
    assert export_output(r)['selection'] == 'canonical_fallback'


def test_preparation_failure_and_changed_current_reported(tmp_path):
    r = runtime(tmp_path)
    r.current.write_bytes(b'changed')
    assert safe_export(r)['status'] == 'export_failed'
    r.current = None
    assert safe_export(r)['status'] == 'unavailable'
    assert json.loads((tmp_path / 'output.json').read_text())['scene'] is None
