"""Bounded single-task Qwen transport diagnosis; never starts a room job."""
import argparse
import hashlib
import io
import json
import time
import urllib.request
from pathlib import Path

from agen3d.multiagent.aha.contracts import load, Plan, Proposal
from agen3d.multiagent.aha.runtime import Runtime
from agen3d.multiagent.resources import load_env
from agen3d.multiagent.store import save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recorded-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sampling',choices=['legacy','qwen'],required=True)
    parser.add_argument('--seed',type=int,default=3407)
    parser.add_argument('--max-tokens',type=int,default=2500)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--provider')
    parser.add_argument('--format',choices=['schema','json','text'],default='schema')
    parser.add_argument('--bounded',action='store_true',help='Separate code-only control with explicit supervisor geometry; not source-derived accuracy')
    args=parser.parse_args()
    load_env(Path('.env'))
    config=load(args.recorded_run/'config.json')
    config.output=str(args.output.resolve())
    config.worker.max_output_tokens=args.max_tokens
    config.worker.timeout_s=90
    config.worker.response_mode=args.format
    if args.provider:
        config.worker.provider=args.provider
    runtime=Runtime(config)
    runtime.initialize_construction()
    runtime.inventory=json.loads((args.recorded_run/'initial-inspection/inventory.json').read_text())
    runtime.reference=json.loads((args.recorded_run/'reference-summary.json').read_text())
    plan=Plan.model_validate_json((args.recorded_run/'plan.json').read_text())
    task=next(t for t in plan.tasks if t.task_id=='door_cabinet_corner')
    if args.bounded:
        task=task.model_copy(update={'instruction':
            'This is a constrained code-generation control, not an image-fitting evaluation. '
            'Use these supervisor-supplied dimensions exactly: outer door/casing bounds '
            'X=[3.9,4.8], Y=[4.50,4.65], Z=[0,2.4]. Build one semantic root with '
            'at least four mesh parts: leaf, left casing, right casing, top casing. '
            'Casing width .07 m. Maintain exact outer bounds and floor contact at Z=0. '
            'Use bpy, roomkit and tag_root correctly; only the complete assembly gets instance_id '
            'door_cabinet_corner. No other root may change. Do not reinterpret these given bounds.'})
    original=urllib.request.urlopen
    captured={}
    def transport(request,timeout):
        payload=json.loads(request.data)
        if args.sampling=='qwen':
            payload.update(temperature=.7,top_p=.8,top_k=20,presence_penalty=1.5,repetition_penalty=1.,seed=args.seed)
        else:payload['seed']=args.seed
        if args.format=='text':
            payload.pop('response_format',None)
        elif args.format=='json':
            payload['response_format']={'type':'json_object'}
        safe=json.loads(json.dumps(payload))
        for message in safe['messages']:
            for part in message.get('content',[]) if isinstance(message.get('content'),list) else []:
                if part['type']=='image_url':
                    part['image_url']['url']='[sha256:'+hashlib.sha256(part['image_url']['url'].encode()).hexdigest()+']'
        save(runtime.output/'request.json',safe)
        changed=urllib.request.Request(request.full_url,data=json.dumps(payload).encode(),
            headers=dict(request.header_items()),method='POST')
        with original(changed,timeout=timeout) as response:
            raw=response.read()
        body=json.loads(raw)
        save(runtime.output/'response.json',body)
        captured['finish_reason']=body.get('choices',[{}])[0].get('finish_reason')
        captured['provider']=body.get('provider')
        captured['usage']=body.get('usage')
        return io.BytesIO(raw)
    urllib.request.urlopen=transport
    started=time.monotonic()
    result={'sampling':args.sampling,'seed':args.seed,'max_tokens':args.max_tokens,'task':task.task_id,
            'format':args.format,'requested_provider':config.worker.provider,
            'bounded_control':args.bounded,
            'scope':'Single existing failed task; no room job; execution validation is not visual acceptance.'}
    try:
        proposal=runtime.call('diagnostic_build',Proposal,runtime.build_packet(task),config.source_images)
        save(runtime.output/'proposal.json',proposal.model_dump())
        compile(proposal.code,'<proposal>','exec')
        result.update(schema_valid=True,python_compiles=True,route=proposal.route,code_chars=len(proposal.code))
        if args.execute:
            candidate,validation=runtime.construct(task,proposal,runtime.output/'candidate',prepare_evidence=False)
            result.update(blender_valid=validation['ok'],candidate=str(candidate))
            if args.bounded:
                obj=validation['objects']['door_cabinet_corner']
                result['given_bounds_match']=obj['parts']>=4 and all(abs(a-b)<1e-4
                    for key,values in [('min',[3.9,4.50,0]),('max',[4.8,4.65,2.4])]
                    for a,b in zip(obj[key],values))
    except Exception as exc:
        result['error']=f'{type(exc).__name__}: {exc}'[:1800]
    finally:
        urllib.request.urlopen=original
        result.update(captured)
        result['wall_seconds']=time.monotonic()-started
        result['cost']=runtime.ledger.summary()
        save(runtime.output/'diagnosis.json',result)
        runtime._job_lock.close()
    print(json.dumps({k:v for k,v in result.items() if k!='cost'},indent=2))


if __name__=='__main__':main()
