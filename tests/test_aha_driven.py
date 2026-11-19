"""Controller safety/persistence tests: no GPU or paid model calls."""
import json
from pathlib import Path

import pytest

from agen3d.multiagent.aha.contracts import Config, Proposal, Review, Work
from agen3d.multiagent.aha.runtime import digest, validate_scope
from agen3d.multiagent.aha_driven.session import Session
from agen3d.multiagent.store import save


@pytest.fixture
def session(tmp_path):
    repo = tmp_path / 'aha'
    save(repo / 'assets/index.json', {'entries': []})
    scene = tmp_path / 'seed.blend'
    scene.write_bytes(b'seed')
    image = tmp_path / 'source.png'
    image.write_bytes(b'fixture')
    config = Config(aha_repo=str(repo), blender='blender', python='python',
                    source_scene=str(scene), layout_spec=str(tmp_path/'layout.json'),
                    source_images={'source': str(image)}, output=str(tmp_path/'job'),
                    supervisor={'backend': 'codex'}, worker={'backend': 'mock'},
                    judge={'backend': 'codex'})
    s = Session(config)
    import time
    s.created_at = time.time()
    s.active_seconds = 0.
    s.candidates = {}
    s.ready = True
    s.input_binding = {str(image): digest(image)}
    s.initialize_construction()
    def construct(task, proposal, folder):
        validate_scope(proposal, task, s.revision)
        folder.mkdir(parents=True)
        candidate = folder / 'scene.blend'
        candidate.write_bytes(folder.name.encode())
        save(folder/'validation.json', {'ok': True, 'objects': {}})
        return candidate, {'candidate_revision': digest(candidate),
                           'images': {'focus': str(image)},
                           'object_views': {'desk': ['focus']}}
    s.construct = construct
    yield s
    if not s._job_lock.closed:
        s.close()


def build(s):
    task = Work(task_id='desk', object_ids=['desk'], instruction='Build desk')
    proposal = Proposal(parent_revision=s.revision, object_ids=['desk'],
                        route='code', reason='fixture', code='pass')
    return s.build(task, proposal)['candidate_id']


def review(s, identity, verdict='pass', images=None):
    return Review(candidate_revision=s.candidates[identity]['revision'], verdict=verdict,
                  severity='routine', observations=['Inspected focus'],
                  defects=[] if verdict == 'pass' else ['Wrong extent'],
                  reviewed_images=['focus'] if images is None else images)


def test_explicit_commit_and_persistence(session):
    s = session
    original = s.current
    identity = build(s)
    assert s.current == original
    with pytest.raises(ValueError, match='passing review'):
        s.commit(identity)
    s.review(identity, review(s, identity))
    assert s.current == original
    s.commit(identity)
    selected = s.current
    assert selected != original
    assert json.loads((s.output/'handoff.json').read_text())['layout_status'] == 'unreviewed'
    s.close()
    resumed = Session.open(s.output)
    try:
        assert resumed.current == selected
        assert resumed.results['desk']['status'] == 'candidate_committed'
        assert resumed.summary()['external_supervisor_usage'] is None
    finally:
        resumed.close()


def test_rejected_review_does_not_mutate_scene(session):
    identity = build(session)
    original = session.current
    session.review(identity, review(session, identity, 'repair'))
    with pytest.raises(ValueError, match='passing review'):
        session.commit(identity)
    assert session.current == original


def test_close_exports_rejected_candidate_and_preserves_commit_gate(session):
    from agen3d.multiagent.aha.artifacts import record_candidate
    identity = build(session)
    row = session.candidates[identity]
    record_candidate(Path(row['folder']), Path(row['scene']), row['parent'],
                     Work.model_validate(row['task']))
    session.review(identity, review(session, identity, 'repair'))
    original = session.current
    session.close()
    report = json.loads((session.output / 'report.json').read_text())
    assert report['scene'] == str(original)
    assert report['output']['source_scene'] == row['scene']
    assert report['output']['local_review']['verdict'] == 'repair'
    assert report['output']['delivery_accepted'] is False
    resumed = Session.open(session.output)
    try:
        assert resumed.current == original
        with pytest.raises(ValueError, match='passing review'):
            resumed.commit(identity)
    finally:
        resumed.close()


def test_review_coverage_and_evidence_binding(session):
    identity = build(session)
    with pytest.raises(ValueError, match='Unknown'):
        session.review(identity, review(session, identity, images=['wrong']))
    session.review(identity, review(session, identity))
    Path(session.c.source_images['source']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='evidence changed'):
        session.commit(identity)


def test_stale_parallel_candidate_rejected(session):
    first, second = build(session), build(session)
    session.review(first, review(session, first))
    session.review(second, review(session, second))
    session.commit(first)
    with pytest.raises(ValueError, match='stale parent'):
        session.commit(second)


def test_modified_validation_rejected(session):
    identity = build(session)
    session.review(identity, review(session, identity))
    Path(session.candidates[identity]['folder'], 'validation.json').write_text('{}')
    with pytest.raises(ValueError, match='evidence changed'):
        session.commit(identity)


def test_failed_build_is_not_retried(session):
    calls = []
    def fail(*args):
        calls.append(1)
        raise RuntimeError('Build failed')
    session.construct = fail
    with pytest.raises(RuntimeError, match='Build failed'):
        build(session)
    assert len(calls) == 1 and not session.candidates


def test_dependency_and_context_scope(session):
    task = Work(task_id='desk', object_ids=['desk'], instruction='Build', depends_on=['floor'])
    with pytest.raises(ValueError, match='dependency'):
        session.packet(task, ['source'], [])
    task.depends_on = []
    packet = json.loads(session.packet(task, ['source'], []).read_text())
    assert list(packet['images']) == ['source']
    assert packet['catalog'] == []
    assert 'prior_tasks' not in packet


def test_session_lock_and_changed_input(session):
    with pytest.raises(BlockingIOError):
        Session.open(session.output)
    session.close()
    Path(session.c.source_images['source']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='Bound input changed'):
        Session.open(session.output)


@pytest.mark.parametrize('verdict,status', [('accepted', 'layout_validated'),
                                           ('rejected', 'needs_repair'),
                                           ('invalid_review', 'blocked_review')])
def test_final_gate_does_not_claim_delivery(session, verdict, status):
    actions = []
    def bridge(action, scene, folder):
        actions.append(action)
        return {'verdict': verdict}
    session.bridge = bridge
    result = session.final_review()
    assert actions == ['prepare', 'review']
    assert result['layout_status'] == status
    assert not result['delivery_accepted']
    assert session.summary()['status'] == status
    assert session.ledger.summary()['unknown_or_pending_calls'] == 1


def test_commit_invalidates_final_acceptance(session):
    session.bridge = lambda *args: {'verdict': 'accepted'}
    session.final_review()
    identity = build(session)
    session.review(identity, review(session, identity))
    session.commit(identity)
    assert session.summary()['status'] == 'unreviewed'


def test_changed_review_receipt_cannot_commit(session):
    identity = build(session)
    session.review(identity, review(session, identity))
    Path(session.candidates[identity]['folder'], 'local-review.json').write_text('{}')
    with pytest.raises(ValueError, match='unchanged passing review'):
        session.commit(identity)


def test_concurrent_canonical_change_blocks_commit(session):
    identity = build(session)
    session.review(identity, review(session, identity))
    session.current.write_bytes(b'unregistered writer')
    with pytest.raises(ValueError, match='Canonical scene changed'):
        session.commit(identity)


def parallel_plan():
    from agen3d.multiagent.aha.contracts import Plan
    return Plan(summary='Independent fixtures', tasks=[
        Work(task_id=oid, object_ids=[oid], instruction='Build', parallel_safe=True)
        for oid in ('desk', 'chair')])


def wave_fixture(session, monkeypatch, fail=None):
    import threading
    session.capacity = {'machine': {'fixture': True}, 'selected': {'builds': 2, 'model_calls': 2}}
    barrier = threading.Barrier(2)
    original = session.current
    def branch(task, wave, parent, revision):
        assert parent == original and revision == digest(original)
        barrier.wait(timeout=5)
        if task.task_id == fail:
            raise ValueError('fixture failure')
        scene = session.output / f'{task.task_id}-branch.blend'
        scene.write_bytes(task.task_id.encode())
        proposal = Proposal(parent_revision=revision, object_ids=task.object_ids,
                            route='code', reason='fixture', code='pass')
        return {'scene': scene, 'scene_sha256': digest(scene), 'parent': revision,
                'proposal': proposal, 'strong': False, 'validation': {'objects': {task.task_id: {}}}}
    session.build_branch = branch
    from agen3d.multiagent.aha_driven import parallel
    def execute(config, folder, script, request):
        data = json.loads(request.read_text())
        if data.get('merge_only'):
            (folder/'scene.blend').write_bytes((folder/'input.blend').read_bytes() +
                                               (folder/'candidate.blend').read_bytes())
        save(folder/'validation.json', {'ok': True, 'objects': {}})
    monkeypatch.setattr(parallel, 'execute', execute)
    def bridge(action, scene, folder):
        return {'candidate_revision': digest(scene), 'images': {'focus': session.c.source_images['source']},
                'object_views': {'desk': ['focus'], 'chair': ['focus']}}
    session.bridge = bridge
    return session.build_wave(parallel_plan())


def test_wave_overlaps_without_commit_and_persists(session, monkeypatch):
    result = wave_fixture(session, monkeypatch)
    assert set(result['results']) == {'desk', 'chair'}
    assert all(r['status'] == 'built' for r in result['results'].values())
    assert not session.results and not session.candidates
    session.close()
    resumed = Session.open(session.output)
    try:
        assert set(resumed.branches) == {'1-desk', '1-chair'}
        assert resumed.capacity['selected']['builds'] == 2
    finally:
        resumed.close()


def test_wave_scoped_merge_review_commit_preserves_both(session, monkeypatch):
    wave_fixture(session, monkeypatch)
    for branch in ('1-desk', '1-chair'):
        parent = session.current
        identity = session.merge(branch)['candidate_id']
        assert session.current == parent
        with pytest.raises(ValueError, match='passing review'):
            session.commit(identity)
        session.review(identity, review(session, identity))
        session.commit(identity)
    assert session.current.read_bytes() == b'seeddeskchair'
    assert all(b['status'] == 'committed' for b in session.branches.values())
    with pytest.raises(ValueError, match='already committed'):
        session.merge('1-desk')


def test_failed_branch_is_preserved_without_retry_or_auto_commit(session, monkeypatch):
    result = wave_fixture(session, monkeypatch, fail='desk')
    assert result['results']['desk']['status'] == 'failed'
    assert result['results']['chair']['status'] == 'built'
    assert not session.results


def test_unrelated_commit_invalidates_pending_wave(session, monkeypatch):
    wave_fixture(session, monkeypatch)
    identity = build(session)
    session.review(identity, review(session, identity))
    session.commit(identity)
    with pytest.raises(ValueError, match='Unrelated scene changes'):
        session.merge('1-chair')


def test_branch_tampering_rejected(session, monkeypatch):
    wave_fixture(session, monkeypatch)
    Path(session.branches['1-desk']['scene']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='branch changed'):
        session.merge('1-desk')


def test_wave_read_dependencies_and_exclusive_tasks(session):
    from agen3d.multiagent.aha.contracts import Plan
    session.capacity = {'machine': {}, 'selected': {'builds': 4, 'model_calls': 2}}
    called = []
    def fail(task, *args):
        called.append(task.task_id)
        raise ValueError('no actual build')
    session.build_branch = fail
    plan = parallel_plan()
    plan.tasks[1].reads_object_ids = ['desk']
    result = session.build_wave(plan)
    assert called == ['desk'] and set(result['results']) == {'desk'}
    plan.tasks[0].parallel_safe = False
    with pytest.raises(ValueError, match='Exclusive tasks'):
        session.build_wave(plan)


def test_packet_shares_builder_contract_without_duplicate_cameras(session):
    session.inventory={'objects':{'floor':{'class':'architecture/floor'}},
                       'cameras':{'duplicate_camera':{'matrix':'large'}}}
    session.reference={'source_cameras':[{'source_frame':0}]}
    task=Work(task_id='desk',object_ids=['desk'],instruction='Build',parallel_safe=True)
    packet=json.loads(session.packet(task,['source'],[]).read_text())
    assert packet['current_inventory']=={'objects':session.inventory['objects']}
    assert packet['reference_geometry']['source_cameras']==[{'source_frame':0}]
    assert 'do not import roomkit' in packet['instruction']
    assert 'parallel_safe' in packet['parallel_contract']
    assert packet['schema']['title']=='Proposal'
    assert 'prior_tasks' not in packet
