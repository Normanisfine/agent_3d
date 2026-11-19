"""Offline serial/parallel comparison with real isolated Blender and deterministic proposals.

Visual review is stubbed: this verifies scheduling/merge correctness, not room fidelity.
No model API requests are sent. An explicit synthetic provider delay models waiting.
"""
import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace

from agen3d.multiagent.aha.contracts import load, Plan, Work, Review
from agen3d.multiagent.aha.runtime import Runtime
from agen3d.multiagent.store import save


class FixtureProvider:
    def __init__(self, delay):
        self.delay = delay

    def complete(self, spec, system, packet, images, workdir):
        time.sleep(self.delay)
        oid = packet['task']['object_ids'][0]
        index = int(oid.rsplit('_',1)[1])
        value = {'parent_revision': packet['parent_revision'], 'object_ids': [oid], 'route': 'code',
                 'reason': 'offline merge fixture', 'code':
                 f'roomkit.box({oid!r}, ({index*2},0,.5), (1,1,1), semantic_class="furniture/fixture", instance_id={oid!r})'}
        return SimpleNamespace(text=json.dumps(value), actual_usd=0., usage={'fixture':True})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',type=Path,help='Prepared construction config (not raw preparation)')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    parser.add_argument('--provider-delay',type=float,default=1.)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    base=load(args.config)
    assert base.preparation is None
    tasks=[Work(task_id=f'fixture_{i}',object_ids=[f'fixture_{i}'],instruction='Build fixture cube',parallel_safe=True)
           for i in range(4)]
    records=[]
    for width in (1,args.workers):
        config=base.model_copy(deep=True,update={'output':str(args.output/f'workers-{width}'), 'hunyuan':None})
        runtime=Runtime(config,provider=FixtureProvider(args.provider_delay))
        runtime.capacity={'selected':{'builds':width,'model_calls':width,'gpu_jobs':1}}
        import threading
        runtime._model_slots=threading.BoundedSemaphore(width)
        runtime.initialize_construction()
        runtime.inspect()
        original_objects=runtime.inventory['objects']
        def bridge(action,scene,folder):
            runtime.sequence+=1
            return {'candidate_revision':'fixture','images':{},'object_views':{}}
        runtime.bridge=bridge
        runtime.critic=lambda *a,**k:Review(candidate_revision='fixture',verdict='pass',severity='routine',
                                          observations=['Offline transport fixture; visual fidelity not tested'],
                                          defects=[],reviewed_images=['fixture'])
        started=time.monotonic()
        runtime.schedule(Plan(summary='Four independent geometry fixtures',tasks=tasks))
        elapsed=time.monotonic()-started
        assert all(v['status']=='candidate_committed' for v in runtime.results.values()),runtime.results
        assert all(runtime.inventory['objects'][oid]==value for oid,value in original_objects.items())
        assert all(t.object_ids[0] in runtime.inventory['objects'] for t in tasks)
        with runtime.ledger.connect() as db:
            fallbacks=db.execute("SELECT COUNT(*) FROM events WHERE kind='parallel_fallback'").fetchone()[0]
        assert fallbacks==0,'Parallel path silently fell back to serial'
        records.append({'workers':width,'wall_seconds':elapsed,'scene':str(runtime.current),
                        'committed':len(runtime.results),'fallbacks':fallbacks,
                        'scope_and_camera_validation':'real isolated Blender',
                        'model_calls':runtime.ledger.summary()['categories'].get('paid_api',{}).get('calls',0)})
        runtime._job_lock.close()
    result={'runs':records,'speedup':records[0]['wall_seconds']/records[1]['wall_seconds'],
            'synthetic_provider_delay_s':args.provider_delay,
            'limitations':'Offline fixture, stubbed visual review. Not an end-to-end quality or real API latency benchmark.'}
    save(args.output/'evaluation.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
