"""Offline identity-only intervention on the frozen FloorPlan209 mesh export.

Splits existing named components, never edits vertices or uses GT to choose groups.
Exploratory single-scene test, not a new reconstruction or held-out benchmark.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


def split_groups(names, groups, centers):
    out = copy.deepcopy(groups)
    anchors = [i for i,n in enumerate(names) if n.startswith('side tabletop') and groups[i]['id']=='side_tables']
    changes = []
    for i,(name,group) in enumerate(zip(names, groups)):
        label = None
        if group['id']=='side_tables':
            if len(anchors) != 2:
                raise ValueError('Expected two existing tabletop anchors')
            nearest = min(anchors, key=lambda j: float(np.linalg.norm(centers[i]-centers[j])))
            label = (f'side_table_{anchors.index(nearest)}', 'furniture/sidetable')
        elif name.startswith('mirror panel') and group['id']=='decor':
            label = ('mirror', 'furniture/mirror')
        elif name.startswith('sideboard vessel') and group['id']=='decor':
            label = (f'vessel_{i}', 'furniture/vase')
        elif name.startswith('small sofa pillow') and group['id']=='sofa':
            label = ('sofa_pillow', 'furniture/pillow')
        elif name.startswith('coffee lower shelf') and group['id']=='coffee_table':
            label = ('coffee_shelf', 'furniture/shelf')
        if label:
            out[i].update(id=label[0], semantic_class=label[1])
            changes.append({'mesh_index':i,'mesh_name':name,'old_group':group['id'],
                            'new_group':label[0], 'new_category':label[1]})
    return out,changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation',type=Path,required=True)
    parser.add_argument('--ground-truth',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Output directory must be new')
    ev=args.evaluation.resolve()
    sys.path.insert(0,str(ev/'evan'))
    from smallobj import export_blend,score
    model_path=ev/'mesh_export/model.npz'
    model=np.load(model_path)
    meta=json.loads((ev/'mesh_export/model.json').read_text())
    vertices,faces,ids=(model[k] for k in ('vertices','faces','face_object_id'))
    centers=[]
    for i in range(len(meta['object_names'])):
        points=vertices[np.unique(faces[ids==i].ravel())]
        centers.append((points.min(axis=0)+points.max(axis=0))/2)
    groups,changes=split_groups(meta['object_names'],meta['object_groups'],centers)
    # Freeze intervention before loading labels. Camera transform and thresholds
    # are reused unchanged from the previously recorded baseline evaluation.
    predictions={name:export_blend.fit_groups(vertices,faces,ids,g)
                 for name,g in [('baseline',meta['object_groups']),('split_identity',groups)]}
    gt=json.loads(args.ground_truth.read_text())
    th=json.loads((ev/'evan/thresholds.json').read_text())
    old=json.loads((ev/'score_sim3_all_objects.json').read_text())
    a=old['alignment'];tf={'s':a['s'],'R':np.array(a['R']),'t':np.array(a['t'])}
    results={}
    for name,preds in predictions.items():
        result=score.score_predictions(preds,gt,tf,th)
        result['overall']={f'{outcome}_{criterion}':sum(r[criterion]==outcome for r in result['rows'])
                           for criterion in ('I','D') for outcome in ('correct','misplaced','missed')}
        results[name]=result
    if results['baseline']['overall'] != old['overall']:
        raise ValueError('Baseline failed to reproduce; do not interpret ablation')
    changes_by_gt=[]
    for before,after in zip(results['baseline']['rows'],results['split_identity']['rows']):
        assert before['gt_id']==after['gt_id']
        if any(before.get(k)!=after.get(k) for k in ['I','D','pred_id']):
            changes_by_gt.append({'gt_id':before['gt_id'],'category':before['category'],
                                  'before':before,'after':after})
    args.output.mkdir(parents=True)
    report={'kind':'exploratory identity-only ablation','mesh_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),
            'geometry_edited':False,'models_called':False,'grouping_used_ground_truth':False,
            'policy':'Split named mirror, vessels, pillow, shelf; assign side-table parts to nearest existing tabletop center.',
            'limitations':'Handwritten scene-specific grouping; shelf is a benchmark-specific part/instance distinction. Does not establish shape fidelity, complete inventory, or generalization.',
            'thresholds_sha256':hashlib.sha256((ev/'evan/thresholds.json').read_bytes()).hexdigest(),
            'alignment':a,'changes':changes,'changes_by_gt':changes_by_gt,'results':results}
    (args.output/'identity-ablation.json').write_text(json.dumps(report,indent=2)+'\n')
    for name,preds in predictions.items():
        (args.output/f'{name}-predictions.json').write_text(json.dumps(preds,indent=2)+'\n')
    print(json.dumps({k:{'n_pred':v['n_pred'],'overall':v['overall']} for k,v in results.items()},indent=2))


if __name__=='__main__':main()
