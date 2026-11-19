import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/f'{name}.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


p=module('profile_original')
split=module('identity_ablation').split_groups


def test_union_handles_overlap_and_nested_intervals():
    assert p.union_seconds([(2,5),(0,3),(1,2),(7,8)])==6
    assert p.union_seconds([])==0
    with pytest.raises(ValueError):p.union_seconds([(2,1)])


def test_classifier_does_not_count_log_reads_as_execution():
    assert p.classify('tail -5 capture/layout_review_v5.log')=='other_tools_and_bookkeeping'
    assert p.classify('bash tools/indoor acceptance review-images REQUEST --out NEW')=='other_tools_and_bookkeeping'
    assert p.classify('bash tools/indoor acceptance review-images runs/a/request.json')=='external_review'
    assert p.classify('blender --python scenes/ai2thor_floorplan209/build_scene.py')=='authored_build_and_stills'


def test_usage_records_not_cumulative_counts_and_intervals_conserve_time(tmp_path):
    rows=[]
    def add(ts,kind,payload):rows.append({'timestamp':f'2026-01-01T00:00:{ts:02d}Z','type':kind,'payload':payload})
    ms=int(p.stamp('2026-01-01T00:00:00Z')*1000)
    add(5,'event_msg',{'type':'item_completed','started_at_ms':ms,'completed_at_ms':ms+5000,
        'item':{'id':'a','type':'CommandExecution','command':['bash','echo a'],'exit_code':0}})
    add(7,'event_msg',{'type':'item_completed','started_at_ms':ms+3000,'completed_at_ms':ms+7000,
        'item':{'id':'b','type':'ContextCompaction'}})
    usage={'response_id':'r','usage':{'input_tokens':10,'cached_input_tokens':4,'output_tokens':2}}
    add(6,'token_usage_record',usage);add(6,'token_usage_record',usage)
    add(7,'event_msg',{'type':'token_count','info':{'total_token_usage':{'input_tokens':999}}})
    path=tmp_path/'session';path.write_text('\n'.join(json.dumps(r) for r in rows))
    result=p.profile(path,'2026-01-01T00:00:00Z','2026-01-01T00:00:10Z')
    assert result['usage_including_compaction']['input_tokens']==10
    assert result['response_usage_count']==1
    assert result['wall_partition_seconds']=={'command_only':3,'compaction_only':2,
        'command_and_compaction':2,'outside_recorded_commands_and_compaction':3}


def test_identity_split_has_no_gt_and_preserves_inputs():
    names=['side tabletop / side_tables','side table leg / side_tables',
           'side tabletop.001 / side_tables','side table leg.004 / side_tables','small sofa pillow / sofa']
    groups=[{'id':'side_tables','semantic_class':'furniture/side_tables'} for _ in range(4)]
    groups.append({'id':'sofa','semantic_class':'furniture/sofa'})
    centers=np.array([[0,0,1],[.1,0,.5],[4,0,1],[4.1,0,.5],[2,0,.4]])
    result,changes=split(names,groups,centers)
    assert result[0]['id']==result[1]['id']=='side_table_0'
    assert result[2]['id']==result[3]['id']=='side_table_1'
    assert result[4]['id']=='sofa_pillow'
    assert groups[0]['id']=='side_tables' and groups[4]['id']=='sofa'
    assert len(changes)==5


def test_observed_profile_and_ablation_consistency():
    r=json.loads((ROOT/'results/original-profile-20261116-v2/profile.json').read_text())
    assert sum(r['wall_partition_seconds'].values())==pytest.approx(r['observed_wall_seconds'])
    historical=json.loads((ROOT/'evidence/original_cost_summary.json').read_text())['main_agent_usage']
    extra=r['usage_timestamped_during_compaction']
    for k in ['input_tokens','cached_input_tokens','output_tokens']:
        assert r['usage_including_compaction'][k]==historical[k]+extra[k]
    a=json.loads((ROOT/'results/identity-ablation-20261116/identity-ablation.json').read_text())
    for v in a['results'].values():
        for criterion in ['I','D']:
            assert sum(v['overall'][f'{outcome}_{criterion}'] for outcome in ['correct','misplaced','missed'])==34
    assert a['geometry_edited'] is False
