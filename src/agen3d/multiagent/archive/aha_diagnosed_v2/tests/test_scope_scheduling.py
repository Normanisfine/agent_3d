import pytest
from agen3d.multiagent.aha.contracts import Plan, Work
from agen3d.multiagent.aha_diagnosed_v2.contracts import ScopedWork
from agen3d.multiagent.aha_diagnosed_v2.scheduling import dependency_plan, ready_tasks
from agen3d.multiagent.aha_diagnosed_v2.runtime import Runtime, WriteScopeError


def task(name, **kw):
    return Work(task_id=name, object_ids=[name], instruction='Build object', **kw)


def test_failed_exclusive_only_blocks_semantic_consumers():
    p, edges, order=dependency_plan(Plan(summary='test',tasks=[
        task('wall',parallel_safe=False),task('rug',parallel_safe=True),
        task('window',parallel_safe=True,reads_object_ids=['wall'])]))
    results={'wall':{'status':'blocked_scope'}}
    assert [t.task_id for t in ready_tasks(p,results,4,order)]==['rug']
    assert p.tasks[2].depends_on==['wall']
    assert p.tasks[1].depends_on==[]
    assert any(e['kind']=='order_only' for e in edges)


def test_exclusive_never_mixed():
    p,_,order=dependency_plan(Plan(summary='test',tasks=[task('rug',parallel_safe=True),task('wall')]))
    assert [t.task_id for t in ready_tasks(p,{},4,order)]==['rug']
    assert [t.task_id for t in ready_tasks(p,{'rug':{'status':'blocked_review'}},4,order)]==['wall']


def test_write_after_read_only_needs_completion():
    p,_,order=dependency_plan(Plan(summary='test',tasks=[
        task('rug',parallel_safe=True,reads_object_ids=['wall']),task('wall',parallel_safe=True)]))
    assert p.tasks[1].depends_on==[]
    assert order['wall']=={'rug'}


def test_edit_requires_reason_and_disjoint_targets():
    with pytest.raises(ValueError):
        ScopedWork(task_id='cut',object_ids=['window'],instruction='Cut',edit_object_ids=['wall'])
    with pytest.raises(ValueError):
        ScopedWork(task_id='cut',object_ids=['wall'],instruction='Cut',edit_object_ids=['wall'],edit_reason='Cut opening')


def test_scope_failure_does_not_retry():
    r=object.__new__(Runtime)
    r.build_packet=lambda *args:{}
    r.c=type('Config',(),{'source_images':{}})()
    from pathlib import Path
    r.output=Path('/tmp/unused-scope-test');r.sequence=0
    calls=[]
    def call(*args,**kw):calls.append(1);return None
    r.call=call
    def construct(*args):raise WriteScopeError('Unauthorized wall edit')
    r.construct=construct
    result=r.work(task('window'))
    assert result['status']=='blocked_scope'
    assert len(calls)==1
