"""Construction boundaries, escalation and honest acceptance without model charges."""
from types import SimpleNamespace

import pytest

from agen3d.multiagent.aha.contracts import Plan, Proposal, Review, Work, Config
from agen3d.multiagent.aha.runtime import Runtime, file_revision, validate_scope
from agen3d.multiagent.aha.isolation import command
from agen3d.multiagent.store import Ledger


def test_prose_cannot_complete_construction():
    with pytest.raises(ValueError):
        Proposal(parent_revision='a', object_ids=['chair'], route='code', reason='done')
    with pytest.raises(ValueError):
        Proposal(parent_revision='a', object_ids=['chair'], route='hunyuan', reason='generated')


def test_stale_or_out_of_scope_rejected():
    task = Work(task_id='chair', object_ids=['chair'], instruction='rebuild')
    proposal = Proposal(parent_revision='old', object_ids=['chair'], route='code', reason='fix', code='pass')
    with pytest.raises(ValueError, match='Stale'):
        validate_scope(proposal, task, 'new')
    proposal.parent_revision = 'new'
    proposal.object_ids = ['wall']
    with pytest.raises(ValueError, match='scope'):
        validate_scope(proposal, task, 'new')


def test_plan_dependencies_and_review_coverage_contract():
    with pytest.raises(ValueError):
        Plan(summary='plan', tasks=[Work(task_id='x', object_ids=['x'], instruction='fix', depends_on=['missing'])])
    with pytest.raises(ValueError):
        Review(candidate_revision='x', verdict='pass', severity='critical',
               observations=['wrong chair'], defects=['missing back'], reviewed_images=['a'])


def test_no_fake_qwen_aha_gate():
    with pytest.raises(ValueError, match='requires Codex'):
        Config(aha_repo='a', blender='b', python='p', source_scene='s', layout_spec='l', output='o',
               source_images={'a': 'a'}, supervisor={'backend': 'codex'},
               worker={'backend': 'mock'}, judge={'backend': 'mock'})


def test_isolation_hides_home_and_clears_credentials(tmp_path):
    cmd = command('/usr/blender/blender', tmp_path, tmp_path, tmp_path/'worker.py', tmp_path/'r.json')
    assert '--clearenv' in cmd and '--unshare-all' in cmd
    assert '/' not in [cmd[i+1] for i, item in enumerate(cmd) if item == '--ro-bind']
    assert '/aha/src' in cmd


def runtime_stub(tmp_path):
    r = Runtime.__new__(Runtime)
    r.c = SimpleNamespace(max_takeovers=3, source_images={}, masks={}, hunyuan=None)
    r.output = tmp_path
    r.current = tmp_path / 'parent.blend'
    r.current.write_bytes(b'parent')
    r.revision = file_revision(r.current)
    r.catalog, r.evidence, r.results = {}, {}, {}
    r.inventory = {}
    r.reference = None
    r.takeovers, r.sequence = 0, 0
    r.ledger = Ledger(tmp_path/'ledger.sqlite', 5)
    return r


def test_critical_task_goes_directly_to_supervisor(tmp_path):
    r = runtime_stub(tmp_path)
    roles = []
    def call(role, schema, packet, images, strong=False):
        roles.append((role, strong))
        return Proposal(parent_revision=r.revision, object_ids=['wall'], route='code', reason='rebuild', code='pass')
    r.call = call
    candidate = tmp_path/'candidate.blend'
    candidate.write_bytes(b'new')
    def construct(task, proposal, folder):
        folder.mkdir(parents=True)
        (folder/'validation.json').write_text('{"objects":{}}')
        return candidate, {}
    r.construct = construct
    r.critic = lambda *args, **kwargs: Review(candidate_revision='x', verdict='pass', severity='routine',
                                            observations=['fixed'], defects=[], reviewed_images=['x'])
    result = r.work(Work(task_id='wall', object_ids=['wall'], instruction='rebuild', severity='critical'))
    assert roles == [('strong_build', True)]
    assert r.takeovers == 0
    assert result['strong_takeover'] and not result['final_accepted']
    assert r.current == candidate


def test_failed_repairs_preserve_parent_and_escalate(tmp_path):
    r = runtime_stub(tmp_path)
    original = r.current
    roles = []
    def call(role, schema, packet, images, strong=False):
        roles.append(strong)
        return Proposal(parent_revision=r.revision, object_ids=['chair'], route='code', reason='fix', code='pass')
    r.call = call
    def fail(*args):
        raise ValueError('No geometry/tool receipt')
    r.construct = fail
    result = r.work(Work(task_id='chair', object_ids=['chair'], instruction='fix'))
    assert result['status'] == 'blocked_construction'
    assert roles == [False, False, True]
    assert r.current == original and original.read_bytes() == b'parent'


def test_unknown_cost_remains_reserved(tmp_path):
    ledger = Ledger(tmp_path/'ledger.sqlite', 2)
    key = ledger.reserve('takeover', .5, .5)
    ledger.settle(key, None, {})
    assert ledger.summary()['accounted_usd'] == .5
    assert ledger.summary()['unknown_or_pending_calls'] == 1


def test_critic_receives_candidate_class_and_overlay_legend(tmp_path):
    r = runtime_stub(tmp_path)
    def call(role, schema, packet, images, strong=False):
        assert packet['candidate_object']['class'] == 'architecture/floor'
        assert 'not candidate RGB renders' in packet['image_legend']
        assert 'backgrounds are not evidence' in packet['image_legend']
        assert packet['object_id'] == 'floor'
        return Review(candidate_revision='r', verdict='repair', severity='routine',
                      observations=['extent mismatch'], defects=['wrong extent'], reviewed_images=['top'])
    r.call = call
    result = r.critic(Work(task_id='floor',object_ids=['floor'],instruction='Build floor'),
        {'candidate_revision':'r','object_views':{'floor':['top']},'images':{'top':'source.png'},
         'candidate_objects':{'floor':{'class':'architecture/floor'}}})
    assert result.verdict == 'repair'


def test_planned_critical_work_does_not_exhaust_takeover_limit(tmp_path):
    r = runtime_stub(tmp_path)
    r.takeovers = r.c.max_takeovers
    calls = []
    def call(*args, **kwargs):
        calls.append(True)
        raise ValueError('fixture failure')
    r.call = call
    result = r.work(Work(task_id='shell', object_ids=['wall'], instruction='build', severity='critical'))
    assert len(calls) == 3
    assert r.takeovers == r.c.max_takeovers
    assert result['reason'] != 'Strong takeover limit'


def test_invalid_python_rejected_before_blender(tmp_path):
    import pytest
    r = runtime_stub(tmp_path)
    task = Work(task_id='wall', object_ids=['wall'], instruction='build')
    proposal = Proposal(parent_revision=r.revision, object_ids=['wall'], route='code',
                        reason='fixture', code='x = 1\n    x = 2')
    folder = tmp_path/'bad-candidate'
    with pytest.raises(IndentationError):
        r.construct(task, proposal, folder)
    assert not folder.exists()
