"""Collect review coverage and historical cheap-model diagnostics without model calls."""
import argparse
import hashlib
import json
from pathlib import Path


def collect(original_run, probes):
    reviews=[]
    for version in (5,8):
        folder=original_run/f'authored_v{version}'
        request_path=folder/'layout_request.json'
        review_path=folder/'layout_review_raw.json'
        request=json.loads(request_path.read_text()); review=json.loads(review_path.read_text())
        observed={view for row in review['observations'] for view in row.get('views',[])}
        required=set(request['images'])
        reviews.append({'version':version,'request':str(request_path),'review':str(review_path),
                        'request_sha256':hashlib.sha256(request_path.read_bytes()).hexdigest(),
                        'required_image_count':len(required),'declared_reviewed_count':len(review['reviewed_views']),
                        'observation_entries':len(review['observations']),
                        'images_not_referenced_by_observations':sorted(required-observed),
                        'verdict':review['verdict'],
                        'findings':[{'id':f['id'],'severity':f['severity'],'affected_ids':f['affected_ids']}
                                    for f in review.get('findings',[])]})
    trials=[]
    for path in sorted(probes.glob('*/diagnosis.json')):
        d=json.loads(path.read_text())
        trials.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            **{k:d.get(k) for k in ['task','format','sampling','bounded_control','schema_valid','python_compiles',
                                  'blender_valid','given_bounds_match','finish_reason','wall_seconds']},
            'error_summary':d.get('error','').splitlines()[0] if d.get('error') else None,
            'visual_quality_validated':None})
    return {'reviews':reviews,'cheap_model_trials':trials,
            'limitations':['Archived sequential debugging trials change prompts/transports; not a controlled model comparison.',
                           'An image mentioned in observations is not necessarily adequately reviewed.',
                           'Schema/execution validity does not prove source fidelity. Missing verdicts remain unknown.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original-run',type=Path,required=True)
    p.add_argument('--probes',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    value=collect(a.original_run.resolve(),a.probes.resolve())
    with a.output.open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps({'reviews':[{k:v for k,v in r.items() if k not in ['findings','images_not_referenced_by_observations']}
                                  | {'uncovered_image_count':len(r['images_not_referenced_by_observations'])}
                                 for r in value['reviews']], 'archived_trials':len(value['cheap_model_trials'])},indent=2))


if __name__=='__main__':main()
