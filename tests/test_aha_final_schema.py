"""Complete-image final responses and explicit whole-scene acceptance."""
import copy

import pytest

from agen3d.multiagent.aha.final_schema import schema, normalize, ASPECTS


def fixture():
    request = dict(candidate_revision='r', images={'top:model':'a.png','source:source':'b.png'},
                   object_views={'floor':['top:model','source:source']})
    raw = dict(candidate_revision='r', reviewer='fixture', verdict='rejected',
        per_image_observations={k:dict(aspect='inventory',subjects=['floor'],observation='Floor visible')
                                for k in request['images']},
        aspect_observations={a:dict(subjects=['floor'],views=list(request['images']),observation='Fixture')
                             for a in ASPECTS},
        object_focus_observations={'floor':{k:'Floor contour' for k in request['images']}},
        scene_completeness=dict(complete=False,observation='Only a floor exists',missing_elements=['walls']),
        findings=[dict(id='missing',severity='blocking',affected_ids=['scene'],views=['top:model'],
                       observation='Missing walls',resolution_needed='Build visible room elements')],
        uncertainties=[],unreviewed_areas=[])
    return request,raw


def test_schema_requires_all_delivered_images_and_object_focus_keys():
    req,_ = fixture()
    properties=schema(req)['properties']
    assert set(properties['per_image_observations']['required'])==set(req['images'])
    assert properties['candidate_revision']['enum']==['r']
    assert properties['object_focus_observations']['required']==['floor']


def test_normalization_preserves_reviewer_authored_coverage():
    req,raw=fixture()
    original=copy.deepcopy(raw)
    result=normalize(raw,req)
    assert raw==original
    assert result['verdict']=='rejected'
    assert {v for row in result['observations'] for v in row['views']}==set(req['images'])
    assert set(ASPECTS)<={r['aspect'] for r in result['observations']}
    assert result['findings']==raw['findings']
    assert all(r['observation'] for r in result['observations'])


@pytest.mark.parametrize('change', ['missing_image','missing_focus','wrong_revision','false_accept'])
def test_incomplete_or_stale_response_cannot_pass(change):
    req,raw=fixture()
    if change=='missing_image':
        raw['per_image_observations'].pop('top:model')
    elif change=='missing_focus':
        raw['object_focus_observations']['floor'].pop('top:model')
    elif change=='wrong_revision':
        raw['candidate_revision']='old'
    else:
        raw['verdict']='accepted'
    with pytest.raises(ValueError):
        normalize(raw,req)


def test_transport_passes_structured_schema_and_preserves_raw_response(tmp_path):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    req,raw=fixture()
    fake=tmp_path/'codex'
    fake.write_text('#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\n'
        'args=sys.argv[1:]\nprompt=sys.stdin.read()\n'
        'assert "COMPLETE observed room" in prompt\n'
        'schema=json.loads(Path(args[args.index("--output-schema")+1]).read_text())\n'
        'assert schema["properties"]["per_image_observations"]["required"]==["top:model","source:source"]\n'
        'Path(args[args.index("--output-last-message")+1]).write_text('+repr(json.dumps(raw))+')\n')
    fake.chmod(0o755)
    wrapper=Path(__file__).parents[1]/'src/agen3d/multiagent/aha/codex_gate.py'
    destination=tmp_path/'result.json'
    env=dict(os.environ,PATH=str(tmp_path)+os.pathsep+os.environ['PATH'],
             AGEN3D_JUDGE_AUDIT_DIR=str(tmp_path/'transport'))
    result=subprocess.run([sys.executable,str(wrapper),'exec','--output-last-message',str(destination),'-'],
        input='Request: '+json.dumps(req),text=True,capture_output=True,env=env)
    assert result.returncode==0,result.stderr
    assert json.loads(destination.read_text())['verdict']=='rejected'
    assert json.loads((tmp_path/'transport/raw-response.json').read_text())==raw
