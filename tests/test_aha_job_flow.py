"""Whole scheduler control flow with deterministic model/renderer doubles; no quality claims."""
import json
from types import SimpleNamespace

import pytest

from agen3d.multiagent.aha.contracts import Config
from agen3d.multiagent.aha.runtime import Runtime
from agen3d.multiagent.aha import doctor, runtime as runtime_module


class Decisions:
    def complete(self, spec, system, packet, images, output):
        title = packet['schema']['title']
        if title == 'Plan':
            value = {'summary':'fixture','tasks':[{'task_id':'floor','object_ids':['floor'],'instruction':'build'}]}
        elif title == 'Proposal':
            value = {'parent_revision':packet['parent_revision'],'object_ids':packet['task']['object_ids'],
                     'route':'code','reason':'fixture','code':'pass'}
        else:
            value = {'candidate_revision':packet['candidate_revision'],'verdict':'pass','severity':'routine',
                     'observations':['fixture'],'defects':[], 'reviewed_images':packet['image_order']}
        return SimpleNamespace(text=json.dumps(value), actual_usd=.01, usage={'fixture':True})


def job(monkeypatch, tmp_path, verdicts):
    (tmp_path/'assets').mkdir()
    (tmp_path/'assets/index.json').write_text('{"entries":[]}')
    scene = tmp_path/'seed.blend'
    scene.write_bytes(b'seed')
    layout = tmp_path/'layout.json'
    layout.write_text('{}')
    image = tmp_path/'source.png'
    image.write_bytes(b'image')
    c = Config(aha_repo=str(tmp_path), blender='blender', python='python',
        source_scene=str(scene),layout_spec=str(layout),source_images={'source':str(image)},
        output=str(tmp_path/'job'),worker={'backend':'mock'},supervisor={'backend':'codex'},
        judge={'backend':'codex'})
    r = Runtime(c, provider=Decisions())
    monkeypatch.setattr(doctor,'check',lambda *a,**k:{'required_ready':True})
    monkeypatch.setattr(runtime_module,'reference_summary',lambda spec:{})
    r.inspect = lambda: None
    final = iter(verdicts)
    def bridge(action, scene, folder):
        r.sequence += 1
        if action == 'review':
            return {'verdict':next(final),'visual_review':{'findings':['fixture']}}
        if action == 'prepare':
            folder.mkdir(parents=True)
        return {}
    r.bridge = bridge
    def construct(task, proposal, folder):
        folder.mkdir(parents=True)
        candidate = folder/'scene.blend'
        candidate.write_bytes(task.task_id.encode())
        (folder/'validation.json').write_text('{"objects":{"floor":{}}}')
        return candidate, {'candidate_revision':'evidence', 'images':{'source':str(image)},
                           'object_views':{'floor':['source']}}
    r.construct = construct
    return r


@pytest.mark.parametrize('verdicts,status,takeovers', [
    (['accepted'],'layout_validated',0),
    (['rejected','accepted'],'layout_validated',1),
    (['rejected','rejected'],'needs_repair',1),
])
def test_complete_scheduler_and_final_takeover(monkeypatch,tmp_path,verdicts,status,takeovers):
    r = job(monkeypatch,tmp_path,verdicts)
    result = r.run()
    assert result['status'] == status, result
    assert result['takeovers'] == takeovers
    assert result['delivery_accepted'] is False
    assert result['output']['status'] == 'candidate_exported'
    assert result['output']['delivery_accepted'] is False
    assert (r.output / 'final_scene.blend').read_bytes() == r.current.read_bytes()
    assert all(row['state'] != 'reserved' for row in result['cost']['charges'])
    handoff = json.loads((r.output/'handoff.json').read_text())
    assert handoff['layout_status'] == status and not handoff['delivery_accepted']
    if takeovers:
        assert 'final_repair' in json.loads((r.output/'tasks.json').read_text())


def test_final_bridge_failure_still_settles_cost_and_saves_failure(monkeypatch,tmp_path):
    r = job(monkeypatch,tmp_path,[])
    bridge = r.bridge
    def fail(action,*args):
        if action=='review':
            raise TimeoutError('final review timed out')
        return bridge(action,*args)
    r.bridge = fail
    result = r.run()
    assert result['status']=='blocked_construction'
    assert 'timed out' in result['error']
    final = next(c for c in result['cost']['charges'] if c['label']=='final_judge')
    assert final['state']=='unknown'
    assert not (r.output/'handoff.json').exists()


def test_invalid_final_review_does_not_trigger_geometry_takeover(monkeypatch,tmp_path):
    r=job(monkeypatch,tmp_path,[])
    bridge=r.bridge
    def invalid(action,*args):
        if action=='review':
            return {'verdict':'invalid_review','error':'missing image observations'}
        return bridge(action,*args)
    r.bridge=invalid
    result=r.run()
    assert result['status']=='blocked_review'
    assert result['takeovers']==0
    assert result['results']['floor']['status']=='candidate_committed'
    assert not (r.output/'handoff.json').exists()


def test_codex_and_compute_do_not_consume_api_budget(monkeypatch, tmp_path):
    r = job(monkeypatch, tmp_path, ['accepted'])
    r.c.budget_usd = r.ledger.budget = .1
    r.c.compute_reservation_usd = 100
    result = r.run()
    assert result['status'] == 'layout_validated', result
    charges = result['cost']['charges']
    assert next(c for c in charges if c['label'] == 'plan')['budget_exempt']
    assert next(c for c in charges if c['label'] == 'final_judge')['budget_exempt']
    assert not next(c for c in charges if c['label'] == 'build')['budget_exempt']
    assert result['cost']['accounted_usd'] == pytest.approx(.02)
    groups = result['cost']['categories']
    assert groups['local_compute']['calls'] == 1  # capacity calibration
    assert groups['codex_cli']['calls'] == 2
    assert groups['paid_api']['accounted_usd'] == pytest.approx(.02)
    assert groups['codex_cli']['accounted_usd'] == 0
    assert groups['local_compute']['accounted_usd'] == 0


def test_exempt_unknown_calls_preserve_usage_even_after_budget_exhaustion(tmp_path):
    from agen3d.multiagent.store import Ledger, BudgetExceeded
    ledger = Ledger(tmp_path/'cost.sqlite', .03)
    paid = ledger.reserve('openrouter', .03)
    ledger.settle(paid, None, {})
    cli = ledger.reserve('codex', 100, 100, budget_exempt=True)
    ledger.settle(cli, None, {'usage': {'input_tokens': 123}})
    assert ledger.summary()['accounted_usd'] == .03
    assert ledger.summary()['charges'][1]['detail']['usage']['input_tokens'] == 123
    with pytest.raises(BudgetExceeded):
        ledger.reserve('openrouter', .01)
    assert Ledger(ledger.path, .03).summary()['budget_exempt_calls'] == 1


def test_blocked_construction_still_exports_verified_candidate(monkeypatch, tmp_path):
    from agen3d.multiagent.aha.artifacts import record_candidate
    from agen3d.multiagent.aha.contracts import Review
    from agen3d.multiagent.aha.runtime import file_revision
    r = job(monkeypatch, tmp_path, [])
    original_construct = r.construct
    def construct(task, proposal, folder):
        candidate, request = original_construct(task, proposal, folder)
        (folder / 'validation.json').write_text('{"ok":true,"objects":{"floor":{}}}')
        record_candidate(folder, candidate, r.revision, task)
        request['candidate_revision'] = file_revision(candidate)
        return candidate, request
    r.construct = construct
    r.critic = lambda task, request, **kw: Review(
        candidate_revision=request['candidate_revision'], verdict='repair',
        severity='routine', observations=['Inspected'], defects=['Wrong height'],
        reviewed_images=['source'])
    result = r.run()
    assert result['status'] == 'blocked_construction'
    assert r.current.read_bytes() == b'seed'
    assert (r.output / 'final_scene.blend').read_bytes() == b'floor'
    assert result['output']['local_review']['defects'] == ['Wrong height']
    assert result['output']['delivery_accepted'] is False
