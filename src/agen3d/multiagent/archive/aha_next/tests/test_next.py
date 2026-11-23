import json
import threading
from types import SimpleNamespace
import pytest
from agen3d.multiagent.aha.contracts import Work, Plan, Proposal, Review
from agen3d.multiagent.aha.runtime import Runtime as Base
from agen3d.multiagent.aha_next.runtime import Runtime
from agen3d.multiagent.aha_next.recipes import Recipe, compile_recipe


def recipe(**updates):
    return Recipe.model_validate(dict(parent_revision='r', object_id='table', route='parts',
        reason='source fit', semantic_class='furniture/table', source_ids=['source'],
        parts=[{'center': [0, 0, .5], 'dimensions': [1, 1, 1]}], **updates))


def test_recipe_rejects_stale_scope_and_missing_evidence():
    t = Work(task_id='table', object_ids=['table'], instruction='fit')
    for revision, images in [('stale', {'source': 'path'}), ('r', {})]:
        with pytest.raises(ValueError):
            compile_recipe(recipe(), t, revision, images)
    with pytest.raises(ValueError):
        compile_recipe(recipe(), t.model_copy(update={'object_ids': ['other']}), 'r', {'source': 'p'})


def test_compiler_quotes_identifiers_and_has_one_root():
    r = recipe().model_copy(update={'object_id': "table');raise Exception('injected"})
    p = compile_recipe(r, SimpleNamespace(object_ids=[r.object_id]), 'r', {'source': 'p'})
    compile(p.code, '<test>', 'exec')
    assert p.code.count('tag_root(') == 1
    assert 'child.parent = root' in p.code


@pytest.mark.parametrize('dimensions', [[0, 1, 1], [float('nan'), 1, 1], [31, 1, 1]])
def test_invalid_geometry(dimensions):
    value = recipe().model_dump()
    value['parts'][0]['dimensions'] = dimensions
    with pytest.raises(ValueError):
        Recipe.model_validate(value)


def bare(tmp_path):
    r = Runtime.__new__(Runtime)
    r.output = tmp_path
    r.results = {}
    r.current, r.revision = 'scene', 'r'
    r.capacity = {'selected': {'builds': 2}}
    r.worker_health = {'ready': True, 'disabled': False}
    r.health_lock = threading.Lock()
    r.ledger = SimpleNamespace(event=lambda *a: None)
    return r


def test_completion_order_and_deferred_repairs(tmp_path):
    r = bare(tmp_path)
    merged = threading.Event()
    order = []
    def build(task, *args):
        if task.task_id == 'slow':
            assert merged.wait(3), 'Head-of-line blocking returned'
        return {}
    def merge(task, *args):
        order.append(task.task_id)
        merged.set()
        return {'status': 'candidate_committed'}
    r.build_branch, r.merge_branch = build, merge
    tasks = [Work(task_id=n, object_ids=[n], instruction='fit', parallel_safe=True) for n in ['slow', 'fast']]
    r.schedule(Plan(summary='test', tasks=tasks))
    assert order == ['fast', 'slow']
    assert len(r.results) == 2


def test_failed_dependency_never_runs(tmp_path):
    r = bare(tmp_path)
    r.worker_health['ready'] = False
    calls = []
    def work(task):
        calls.append(task.task_id)
        return {'status': 'blocked_construction'}
    r.work = work
    r.schedule(Plan(summary='test', tasks=[
        Work(task_id='a', object_ids=['a'], instruction='fit'),
        Work(task_id='b', object_ids=['b'], instruction='fit', depends_on=['a'])]))
    assert calls == ['a']
    assert r.results['b']['status'] == 'blocked_dependency'


def test_critic_keeps_focus_and_adds_missing_original(monkeypatch, tmp_path):
    r = bare(tmp_path)
    r.c = SimpleNamespace(source_images={'source_62': 'original.png'})
    request = {'images': {'focus': 'focus.png'}, 'object_views': {'table': ['focus']}}
    def critic(self, task, enriched, strong=False):
        assert enriched['object_views']['table'] == ['focus', 'original:source_62']
        return Review(candidate_revision='r', verdict='repair', severity='routine',
                      observations=['missing casing'], defects=['fit trim'], reviewed_images=['focus'])
    monkeypatch.setattr(Base, 'critic', critic)
    result = r.critic(Work(task_id='t', object_ids=['table'], instruction='fit'), request)
    assert result.severity == 'critical'
    assert request['object_views']['table'] == ['focus']


def test_invalid_recipe_opens_circuit_without_repeating_call(monkeypatch, tmp_path):
    r = bare(tmp_path)
    calls = []
    def call(*args, **kwargs):
        calls.append(1)
        raise ValueError('truncated')
    monkeypatch.setattr(Base, 'call', call)
    for _ in range(2):
        with pytest.raises(ValueError):
            r.call('build', Proposal, {'task': {'object_ids': ['table']}, 'parent_revision': 'r'}, {})
    assert len(calls) == 1
    assert r.worker_health['disabled']


def test_failed_branch_repair_waits_until_successful_sibling_commits(tmp_path):
    r = bare(tmp_path)
    order = []
    def build(task, *args):
        if task.task_id == 'bad':
            raise ValueError('invalid output')
        return {}
    def merge(task, *args):
        order.append('merge:' + task.task_id)
        return {'status': 'candidate_committed'}
    def work(task, feedback, force_strong, start_attempt):
        assert force_strong and start_attempt == 1
        order.append('repair:' + task.task_id)
        return {'status': 'candidate_committed'}
    r.build_branch, r.merge_branch, r.work = build, merge, work
    r.schedule(Plan(summary='test', tasks=[
        Work(task_id=n, object_ids=[n], instruction='fit', parallel_safe=True) for n in ['bad', 'good']]))
    assert order == ['merge:good', 'repair:bad']


def test_canary_runs_before_fanout(tmp_path):
    r = bare(tmp_path)
    r.worker_health['ready'] = False
    calls = []
    def work(task):
        calls.append(task.task_id)
        assert len(calls) == 1
        r.worker_health['ready'] = True
        return {'status': 'candidate_committed'}
    def build(task, *args):
        assert calls == ['a']
        return {}
    r.work, r.build_branch = work, build
    r.merge_branch = lambda *a: {'status': 'candidate_committed'}
    r.schedule(Plan(summary='test', tasks=[
        Work(task_id=n, object_ids=[n], instruction='fit', parallel_safe=True) for n in ['a', 'b', 'c']]))
    assert len(r.results) == 3
