"""Concurrency correctness: dependency barriers, bounded calls, accounting and rollback."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from agen3d.multiagent.aha.contracts import Parallelism, Plan, Work, Review
from agen3d.multiagent.aha.scheduling import dependency_plan, ready_tasks, limits, HostMeter
from agen3d.multiagent.aha.runtime import Runtime
from agen3d.multiagent.store import Ledger, BudgetExceeded


def task(name, deps=(), reads=(), objects=None, parallel=True):
    return Work(task_id=name, object_ids=objects or [name], instruction='build',
                depends_on=list(deps), reads_object_ids=list(reads), parallel_safe=parallel)


def test_dependencies_parallel_frontier_and_read_write_conflicts():
    plan = Plan(summary='fixture', tasks=[task('shell', parallel=False), task('table', ['shell']),
        task('lamp', ['shell']), task('props', reads=['table']),
        task('paint_table', objects=['table']), task('lighting', parallel=False)])
    planned, added = dependency_plan(plan)
    results = {'shell': {'status': 'candidate_committed'}}
    assert [t.task_id for t in ready_tasks(planned, results, 4)] == ['table', 'lamp']
    assert 'table' in planned.tasks[3].depends_on
    assert {'table','props'} <= set(planned.tasks[4].depends_on)
    assert set(planned.tasks[-1].depends_on) == {t.task_id for t in planned.tasks[:-1]}
    assert added


def test_capacity_honors_load_memory_and_user_limits():
    policy = Parallelism(max_builds=8, max_model_calls=3)
    snap = {'effective_cpus': 64, 'load_1m': 0, 'available_memory_gib': 12}
    assert limits(snap, policy) == {'builds': 2, 'model_calls': 3, 'gpu_jobs': 1}
    snap['load_1m'] = 80
    assert limits(snap, policy)['builds'] == 1
    assert limits(snap, Parallelism(enabled=False))['model_calls'] == 1


def test_host_meter_does_not_double_bill_overlap(monkeypatch):
    from agen3d.multiagent.aha import scheduling
    now = [0.]
    monkeypatch.setattr(scheduling.time, 'monotonic', lambda: now[0])
    meter = HostMeter()
    meter.start('a')
    now[0] = 2
    meter.start('b')
    now[0] = 6
    a = meter.finish('a')
    now[0] = 8
    b = meter.finish('b')
    assert a == b == 4 and a + b == 8


def test_parallel_ledger_reservations_cannot_overspend(tmp_path):
    ledger = Ledger(tmp_path/'ledger.sqlite', .09)
    barrier = threading.Barrier(8)
    def reserve(_):
        barrier.wait(timeout=5)
        try:
            ledger.reserve('call', .03)
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(8))) == 3
    assert ledger.summary()['accounted_usd'] == pytest.approx(.09)


def test_object_reviews_overlap_and_keep_every_image(tmp_path):
    r = Runtime.__new__(Runtime)
    r.capacity = {'selected': {'model_calls': 2}}
    barrier = threading.Barrier(2)
    def call(role, schema, packet, images, strong=False):
        barrier.wait(timeout=5)
        return Review(candidate_revision='r', verdict='pass', severity='routine',
                      observations=[packet['object_id']], defects=[], reviewed_images=list(images))
    r.call = call
    review = r.critic(task('pair', objects=['a','b']),
                     {'candidate_revision':'r', 'images':{'a':'a.png','b':'b.png'},
                      'object_views':{'a':['a'],'b':['b']}})
    assert review.reviewed_images == ['a','b']
    assert review.observations == ['a','b']


def test_schedule_builds_same_snapshot_commits_serially_and_blocks_dependents(tmp_path):
    r = Runtime.__new__(Runtime)
    r.output, r.current, r.revision = tmp_path, 'seed', 'rev'
    r.results = {}
    r.capacity = {'selected': {'builds': 2}}
    r.ledger = Ledger(tmp_path/'ledger.sqlite', 5)
    barrier = threading.Barrier(2)
    built, merged = [], []
    def build(task, wave, parent, revision):
        assert parent == 'seed' and revision == 'rev'
        built.append(task.task_id)
        barrier.wait(timeout=5)
        return task.task_id
    def merge(task, branch, wave):
        merged.append((task.task_id,r.current))
        r.current = task.task_id
        return {'status':'candidate_committed'}
    r.build_branch, r.merge_branch = build, merge
    r.work = lambda t: {'status':'blocked_construction'}
    plan = Plan(summary='fixture',tasks=[task('a'),task('b'),task('c',['a','b']),task('d',['c'])])
    r.schedule(plan)
    assert set(built) == {'a','b'}
    assert merged == [('a','seed'),('b','a')]
    assert r.results['d']['status'] == 'blocked_dependency'
    assert json.loads((tmp_path/'dependency-plan.json').read_text())['build_limit'] == 2


def test_failed_merge_uses_serial_repair_without_committing_branch(tmp_path):
    r = Runtime.__new__(Runtime)
    r.output, r.current, r.revision = tmp_path, 'seed', 'rev'
    r.results = {}
    r.capacity = {'selected': {'builds': 2}}
    r.ledger = Ledger(tmp_path/'ledger.sqlite', 5)
    r.build_branch = lambda *args: {}
    def merge(*args):
        raise ValueError('bad merge')
    r.merge_branch = merge
    repaired = []
    def repair(t, feedback=None, start_attempt=0):
        assert start_attempt == 1
        assert r.current == 'seed'
        repaired.append(t.task_id)
        return {'status':'blocked_construction'}
    r.work = repair
    r.schedule(Plan(summary='fixture',tasks=[task('a'),task('b')]))
    assert repaired == ['a','b']
    assert r.current == 'seed'


def test_model_transport_is_globally_bounded(tmp_path):
    import time
    from agen3d.multiagent.aha.contracts import Config, Proposal
    lock = threading.Lock()
    active, peak = [0], [0]
    class Provider:
        def complete(self, spec, system, packet, images, workdir):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(.03)
            with lock:
                active[0] -= 1
            return SimpleNamespace(text=json.dumps({'parent_revision':'r','object_ids':['a'],
                'route':'code','reason':'fixture','code':'pass'}), actual_usd=.01, usage={})
    config = Config(aha_repo='a',blender='b',python='p',source_scene='s',layout_spec='l',
                    source_images={'x':'unused'},output=str(tmp_path/'job'),
                    supervisor={'backend':'codex'},worker={'backend':'mock'},judge={'backend':'codex'})
    r = Runtime(config,provider=Provider())
    r._model_slots=threading.BoundedSemaphore(2)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(r.call,'build',Proposal,{}, {}) for _ in range(6)]
        assert all(f.result().route=='code' for f in futures)
    assert peak[0]==2
    assert len(r.ledger.summary()['charges'])==6
    r._job_lock.close()


def test_tampered_parallel_candidate_rejected_before_merge(tmp_path):
    from agen3d.multiagent.aha.contracts import Proposal
    r=Runtime.__new__(Runtime)
    scene=tmp_path/'candidate.blend';scene.write_bytes(b'changed')
    proposal=Proposal(parent_revision='r',object_ids=['a'],route='code',reason='fixture',code='pass')
    with pytest.raises(ValueError,match='changed before merge'):
        r.merge_branch(task('a'),{'proposal':proposal,'parent':'r','scene':scene,'scene_revision':'old'},1)


def test_proposal_schema_requires_code_and_length_is_charged(tmp_path):
    from agen3d.multiagent.aha.contracts import Config,Proposal
    class Provider:
        def complete(self,spec,system,packet,images,workdir):
            assert 'code' in packet['schema']['required']
            assert 'reviewed_images' not in packet['evidence_response_rule']
            return SimpleNamespace(text='{"code":',actual_usd=.02,
                                   usage={'finish_reason':'length','output_tokens':100})
    config=Config(aha_repo='a',blender='b',python='p',source_scene='s',layout_spec='l',
        source_images={'s':'unused'},output=str(tmp_path/'job'),supervisor={'backend':'codex'},
        worker={'backend':'mock'},judge={'backend':'codex'})
    r=Runtime(config,provider=Provider())
    with pytest.raises(ValueError,match='truncated'):
        r.call('build',Proposal,{}, {})
    assert r.ledger.summary()['accounted_usd']==.02
    assert len(list((r.output/'calls').glob('*.json')))==1
    r._job_lock.close()
