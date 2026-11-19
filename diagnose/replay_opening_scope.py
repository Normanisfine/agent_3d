"""Replay failed opening programs in isolation; no models and no visual acceptance.

First reproduce strict rejection. Then grant only the two shell writes explicitly
requested by the saved task prose, retaining all other scope and camera checks.
Original proposal bytes and original four construction globals remain unchanged.
"""
import argparse
import json
from pathlib import Path
import shutil
import time

from agen3d.multiagent.aha.contracts import load
from agen3d.multiagent.aha.isolation import execute
import agen3d.multiagent.aha_diagnosed_v2 as variant
from agen3d.multiagent.aha.runtime import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    config=load(args.run/'config.json')
    worker=Path(variant.__file__).with_name('blender_worker.py')
    results=[]
    for source in sorted((args.run/'candidates').glob('fit_openings-*')):
        original=json.loads((source/'request.json').read_text())
        for corrected in (False,True):
            folder=args.output/(source.name+('-corrected' if corrected else '-original'))
            folder.mkdir()
            shutil.copy2(source/'input.blend',folder/'input.blend')
            shutil.copy2(source/'build.py',folder/'build.py')
            request=json.loads(json.dumps(original))
            if corrected:
                request['create_object_ids']=list(original['proposal']['object_ids'])
                request['edit_object_ids']=['room_walls','wall_wainscoting']
                request['proposal']['object_ids']+=request['edit_object_ids']
            (folder/'request.json').write_text(json.dumps(request,indent=2))
            before=time.monotonic();error=None
            try:
                execute(config,folder,worker,folder/'request.json')
                (folder/'verify.json').write_text(json.dumps({**request,'verify_only':True}))
                execute(config,folder,worker,folder/'verify.json')
            except Exception as exc:error=str(exc)
            diff=json.loads((folder/'scope-diff.json').read_text()) if (folder/'scope-diff.json').exists() else None
            row={'attempt':source.name,'corrected_scope':corrected,'ok':error is None,
                 'error':error,'seconds':time.monotonic()-before,
                 'build_code_unchanged':digest(source/'build.py')==digest(folder/'build.py'),
                 'changed_ids':diff['changed_ids'] if diff else None,
                 'unauthorized_changed_ids':diff['unauthorized_changed_ids'] if diff else None,
                 'folder':str(folder.resolve()),'visual_quality_validated':False}
            results.append(row)
            (args.output/'replay.json').write_text(json.dumps({'results':results,'hosted_calls':0,
                'scope_change':'Explicit writes for room_walls and wall_wainscoting; not a relaxed validator.'},indent=2))
            print(json.dumps({k:v for k,v in row.items() if k!='error'}),flush=True)
    if len(results)!=6 or not all((r['ok']==r['corrected_scope']) for r in results):
        raise SystemExit('Replay did not demonstrate all three original failures and corrected passes')


if __name__=='__main__':main()
