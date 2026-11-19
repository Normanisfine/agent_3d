import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest

from agen3d.multiagent.aha.contracts import Work, Review
from agen3d.multiagent.contracts import ModelSpec
from agen3d.multiagent.aha_diagnosed.contracts import Instance,InstancePlan,CoveredReview,validate_plan
from agen3d.multiagent.aha_diagnosed.evidence import packets,review_key
from agen3d.multiagent.aha_diagnosed.runtime import Runtime


def instance(oid,**kw):
    return Instance(instance_id=oid,semantic_class='furniture/table',description='One observed table',
                    disposition='build',source_image_ids=['source'],**kw)


def task(oid,**kw):
    return Work(task_id=oid,object_ids=[oid],instruction='Build observed object',parallel_safe=True,**kw)


def plan():
    return InstancePlan(summary='Two instances',scope_statement='Two separate tables',
        instances=[instance('a'),instance('b')],tasks=[task('a'),task('b')])


def test_manifest_does_not_allow_unassigned_instances_or_unknown_evidence():
    p=plan()
    with pytest.raises(ValueError):
        InstancePlan.model_validate({**p.model_dump(),'tasks':[task('a').model_dump()]})
    with pytest.raises(ValueError):validate_plan(p,{}, {'objects':{}})
    with pytest.raises(ValueError):validate_plan(p,{'source':'file'}, {'objects':{'unaccounted':{}}})
    assert all(t.severity=='critical' for t in validate_plan(p,{'source':'f'},{'objects':{}}).tasks)


def test_support_reads_are_added_and_future_support_is_rejected():
    p=plan()
    p.instances[1].support_id='a'
    out=validate_plan(p,{'source':'f'},{'objects':{}})
    assert out.tasks[1].reads_object_ids==['a']
    with pytest.raises(ValueError):
        validate_plan(p.model_copy(update={'tasks':list(reversed(p.tasks))}),{'source':'f'},{'objects':{}})


def test_exclusions_are_explicit_and_preserve_requires_existing():
    with pytest.raises(ValueError):instance('a').model_copy(update={'disposition':'exclude'}).__class__.model_validate(
        {**instance('a').model_dump(),'disposition':'exclude'})
    p=plan();p.instances.append(instance('c').model_copy(update={'disposition':'preserve'}))
    with pytest.raises(ValueError):validate_plan(p,{'source':'f'},{'objects':{}})


def fixture(tmp_path,count=12):
    images={}
    for n in range(count):
        path=tmp_path/f'{n}.png';path.write_bytes(f'image-{n}'.encode());images[f'focus{n}']=str(path)
    src=tmp_path/'source.png';src.write_bytes(b'source')
    request={'candidate_revision':'r','images':images,'object_views':{'a':list(images)}}
    return request,{'source':str(src)}


def test_shards_cover_all_images_with_shared_anchors(tmp_path):
    req,source=fixture(tmp_path)
    chunks=packets(task('a'),req,{'a':instance('a')},source,5)
    assert max(len(c['images']) for c in chunks)<=5
    assert set.union(*(set(c['images']) for c in chunks))==set(req['images'])|{'original:source'}
    assert all({'focus0','original:source'}<=set(c['images']) for c in chunks)


def test_missing_focus_and_source_fail_preflight(tmp_path):
    req,source=fixture(tmp_path,1)
    req['object_views']['a'].append('missing')
    with pytest.raises(ValueError):packets(task('a'),req,{'a':instance('a')},source)


def covered(packet,images,verdict='pass'):
    return CoveredReview(candidate_revision=packet['candidate_revision'],verdict=verdict,
        severity='routine',observations=['Object contour matches source'],
        defects=[] if verdict=='pass' else ['Object exceeds source contour'],reviewed_images=list(images),
        image_observations=[{'image_id':i,'observation':'Object contour visible in this view'} for i in images])


def test_declared_image_list_is_not_sufficient():
    data=covered({'candidate_revision':'r'},{'a':'p','b':'p'}).model_dump()
    data['image_observations']=data['image_observations'][:1]
    with pytest.raises(ValueError):CoveredReview.model_validate(data)
    data['image_observations']*=2
    with pytest.raises(ValueError):CoveredReview.model_validate(data)


def bare(tmp_path,source):
    r=Runtime.__new__(Runtime)
    r._review_lock=threading.Lock();r._review_locks={};r._triaged_tasks=set()
    r._review_cache_root=tmp_path/'cache';r._review_cache_root.mkdir()
    r.c=SimpleNamespace(supervisor=ModelSpec(backend='mock',model='strong'),
                        worker=ModelSpec(backend='mock',model='cheap'),source_images=source)
    r.ledger=SimpleNamespace(event=lambda *a:None)
    r.capacity={'selected':{'model_calls':3}}
    r.instances={'a':instance('a')};r.inventory={'objects':{}}
    r.max_review_images=5;r.cheap_triage=False
    return r


def test_exact_review_cache_deduplicates_concurrent_calls_and_invalidates(tmp_path):
    req,source=fixture(tmp_path,1);r=bare(tmp_path,source)
    calls=[]
    def call(role,schema,packet,images,**kw):
        calls.append(role);return covered(packet,images)
    r.call=call;packet={'candidate_revision':'r','instruction':'fit'};images=source
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:r._covered_call(packet,images,strong=True),range(3)))
    assert len(calls)==1 and all(v.verdict=='pass' for v in results)
    Path=__import__('pathlib').Path
    Path(source['source']).write_bytes(b'changed')
    r._covered_call(packet,images,strong=True)
    r._covered_call({**packet,'candidate_revision':'new'},images,strong=True)
    r._covered_call({**packet,'instruction':'different'},images,strong=True)
    assert len(calls)==4


def test_cheap_pass_never_commits_without_strong_review(tmp_path):
    req,source=fixture(tmp_path,1);r=bare(tmp_path,source);r.cheap_triage=True;calls=[]
    def call(packet,images,*,strong):
        calls.append(strong);return covered(packet,images)
    r._covered_call=call
    assert r.critic(task('a'),req).verdict=='pass'
    assert calls==[False,True]


def test_cheap_rejection_requests_strong_repair_and_is_not_repeated(tmp_path):
    req,source=fixture(tmp_path,1);r=bare(tmp_path,source);r.cheap_triage=True;calls=[]
    def call(packet,images,*,strong):
        calls.append(strong);return covered(packet,images,'pass' if strong else 'repair')
    r._covered_call=call
    assert r.critic(task('a'),req).severity=='critical'
    assert r.critic(task('a'),req).verdict=='pass'
    assert calls==[False,True]


def test_missing_evidence_spends_no_calls(tmp_path):
    req,source=fixture(tmp_path,1);r=bare(tmp_path,source);calls=[]
    r._covered_call=lambda *a,**k:calls.append(1)
    req['object_views']['a']=['absent']
    with pytest.raises(ValueError):r.critic(task('a'),req)
    assert not calls


def test_invalid_review_does_not_rebuild_geometry(tmp_path):
    from agen3d.multiagent.aha_diagnosed.runtime import EvidenceReviewError
    from agen3d.multiagent.aha.contracts import Proposal
    req,source=fixture(tmp_path,1);r=bare(tmp_path,source)
    r.output=tmp_path;r.sequence=0;r.takeovers=0;r.revision='r'
    calls=[]
    r.build_packet=lambda *a:{}
    def call(*a,**k):
        calls.append('build')
        return Proposal(parent_revision='r',object_ids=['a'],route='code',reason='fixture',code='pass')
    r.call=call
    r.construct=lambda *a:(tmp_path/'candidate.blend',req)
    def critic(*a,**k):raise EvidenceReviewError('Missing image observation')
    r.critic=critic
    result=r.work(task('a'))
    assert result['status']=='blocked_review'
    assert result['geometry_retry_performed'] is False
    assert calls==['build']


def test_evidence_generation_failure_is_not_geometry_failure(monkeypatch,tmp_path):
    from agen3d.multiagent.aha_diagnosed.runtime import EvidenceReviewError
    from agen3d.multiagent.aha.runtime import Runtime as Base
    req,source=fixture(tmp_path,1);r=bare(tmp_path,source)
    def fail(*a,**k):raise RuntimeError('Missing television focus view')
    monkeypatch.setattr(Base,'bridge',fail)
    with pytest.raises(EvidenceReviewError,match='preserve geometry'):
        r.bridge('prepare','scene','folder')
    with pytest.raises(RuntimeError):r.bridge('preflight','scene','folder')
