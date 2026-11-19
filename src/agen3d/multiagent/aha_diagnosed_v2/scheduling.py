"""Semantic success dependencies are separate from execution ordering barriers."""
from ..aha.contracts import Plan, Work


def lower_plan(instance_plan):
    tasks=[];scopes={}
    for task in instance_plan.tasks:
        scopes[task.task_id]={'create_object_ids':list(task.object_ids),
                              'edit_object_ids':list(task.edit_object_ids),'edit_reason':task.edit_reason}
        value=task.model_dump(exclude={'edit_object_ids','edit_reason'})
        value['object_ids']=task.object_ids+task.edit_object_ids
        tasks.append(Work.model_validate(value))
    return Plan(summary=instance_plan.summary,tasks=tasks),scopes


def dependency_plan(plan):
    tasks=[];edges=[];ordering={}
    for task in plan.tasks:
        hard=set(task.depends_on);soft=set()
        writes,reads=set(task.object_ids),set(task.reads_object_ids)
        for earlier in tasks:
            prior_writes,prior_reads=set(earlier.object_ids),set(earlier.reads_object_ids)
            if prior_writes & (reads|writes):
                if earlier.task_id not in hard:
                    hard.add(earlier.task_id)
                    edges.append({'from':earlier.task_id,'to':task.task_id,
                                  'kind':'requires_success','reason':'read/write conflict'})
            if (not task.parallel_safe or not earlier.parallel_safe or writes & prior_reads):
                soft.add(earlier.task_id)
        soft-=hard
        for dep in sorted(soft):
            edges.append({'from':dep,'to':task.task_id,'kind':'order_only',
                          'reason':'exclusive execution or write-after-read ordering'})
        ordering[task.task_id]=soft
        tasks.append(task.model_copy(update={'depends_on':[t.task_id for t in tasks if t.task_id in hard]}))
    return Plan(summary=plan.summary,tasks=tasks),edges,ordering


def ready_tasks(plan,results,count,ordering):
    ready=[]
    for task in plan.tasks:
        if task.task_id in results:continue
        if not all(dep in results and results[dep]['status']=='candidate_committed' for dep in task.depends_on):continue
        if not ordering.get(task.task_id,set()) <= set(results):continue
        if not task.parallel_safe:
            # Never put an exclusive task in a parallel wave, even if a malformed
            # external ordering map omitted an edge.
            return ready or [task]
        ready.append(task)
        if len(ready)>=count:break
    return ready
