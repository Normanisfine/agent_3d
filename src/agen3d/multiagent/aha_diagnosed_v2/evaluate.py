"""Offline integration: real isolated Blender, fixture model judgments, no quality claim."""
import argparse
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

from ..aha.contracts import load
from ..aha.runtime import digest
from ..store import save
from .contracts import Instance,InstancePlan,ScopedWork as Work
from .runtime import Runtime


class FixtureProvider:
    def complete(self,spec,system,packet,images,workdir):
        if 'task' in packet:
            oid=packet['task']['object_ids'][0]
            index=int(oid.rsplit('_',1)[1])
            result={'parent_revision':packet['parent_revision'],'object_ids':[oid],'route':'code',
                'reason':'Offline integration fixture; not source-derived geometry',
                'code':f'roomkit.box({oid!r}, ({index*2},0,.5), (1,1,1), semantic_class="furniture/fixture", instance_id={oid!r})'}
        else:
            result={'candidate_revision':packet['candidate_revision'],'verdict':'pass','severity':'routine',
                'observations':['Fixture-only review; visual fidelity is not tested'], 'defects':[],
                'reviewed_images':packet['image_order'],
                'image_observations':[{'image_id':i,'observation':'Fixture-only supplied image; no visual assessment performed'}
                                      for i in packet['image_order']]}
        return SimpleNamespace(text=json.dumps(result),actual_usd=0.,usage={'fixture':True})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('config',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=3,choices=range(1,9))
    a=p.parse_args();config=load(a.config)
    if config.preparation:p.error('Requires prepared-input configuration')
    if a.output.exists():p.error('Output must be new')
    config.output=str(a.output.resolve())
    runtime=Runtime(config,provider=FixtureProvider())
    start=time.monotonic()
    try:
        runtime.capacity={'selected':{'builds':a.workers,'model_calls':a.workers,'gpu_jobs':1}}
        runtime._model_slots=threading.BoundedSemaphore(a.workers)
        runtime.initialize_construction();runtime.inspect()
        original=dict(runtime.inventory['objects'])
        source_id,source_path=next(iter(config.source_images.items()))
        # The fixture reuses source PNGs as mock focus images. These are NOT real
        # candidate focus renders. Exact receipt binding is exercised, not vision.
        def bridge(action,scene,folder):
            runtime.sequence+=1
            objects=runtime.inventory['objects']
            known={*objects,*(f'fixture_{i}' for i in range(4))}
            return {'candidate_revision':digest(scene),'images':{'fixture_focus':source_path},
                    'object_views':{oid:['fixture_focus'] for oid in known}}
        runtime.bridge=bridge
        instances=[Instance(instance_id=oid,semantic_class='structure/fixture-preserved',
            description='Existing fixture baseline object',kind='structure',disposition='preserve',
            source_image_ids=[source_id]) for oid in original]
        for i in range(4):
            instances.append(Instance(instance_id=f'fixture_{i}',semantic_class='furniture/fixture',
                description='Independent integration cube',disposition='build',source_image_ids=[source_id]))
        plan=InstancePlan(summary='Offline integration',scope_statement='Four fixture cubes, preserve seed',
            instances=instances,tasks=[Work(task_id=f'fixture_{i}',object_ids=[f'fixture_{i}'],
                instruction='Build integration cube',parallel_safe=True) for i in range(4)])
        save(runtime.output/'instance-plan.json',plan.model_dump())
        runtime.schedule(plan)
        assert all(r['status']=='candidate_committed' for r in runtime.results.values()),runtime.results
        assert all(runtime.inventory['objects'][oid]==value for oid,value in original.items())
        assert all(f'fixture_{i}' in runtime.inventory['objects'] for i in range(4))
        with runtime.ledger.connect() as db:
            fallbacks=db.execute("SELECT COUNT(*) FROM events WHERE kind='parallel_fallback'").fetchone()[0]
        assert fallbacks==0
        receipts=list((runtime.output/'covered-reviews').glob('*.json'))
        assert len(receipts)==4
        for path in receipts:
            review=json.loads(path.read_text())['review']
            assert set(review['reviewed_images'])=={r['image_id'] for r in review['image_observations']}
        result={'ok':True,'workers':a.workers,'committed':len(runtime.results),'fallbacks':fallbacks,
                'bound_review_receipts':len(receipts),'old_objects_preserved':True,
                'scene':str(runtime.current),'wall_seconds':time.monotonic()-start,
                'hosted_calls':0,'visual_review':'fixture responses with mock focus evidence',
                'delivery_accepted':False,'room_quality_validated':False,'ledger':runtime.ledger.summary()}
        save(runtime.output/'evaluation.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='ledger'},indent=2))
    finally:runtime._job_lock.close()


if __name__=='__main__':main()
