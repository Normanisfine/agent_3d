"""Recover reconstruction-only usage; exclude later VoMP/Isaac turns."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True,help='New output directory; source logs are read-only')
args=parser.parse_args()
HERE=args.output.resolve()
if HERE.exists():
 parser.error('Output must be a new directory')
HERE.mkdir(parents=True)
session=Path('/home/mj/.codex/sessions/2026/10/22/rollout-2026-10-22T19-36-13-01a165f8-e5e3-7be2-87f4-0d5892de3331.jsonl')
cutoff='2026-10-23T00:52:17.416Z'  # next user turn: "where is the obj?"
start='2026-10-22T23:36:15.819Z'
last=None; events=[]
for line in session.open():
 e=json.loads(line);p=e.get('payload',{});ts=e.get('timestamp','')
 if ts>=cutoff:break
 if p.get('type')=='token_count' and p.get('info'):
  last={'timestamp':ts,**p['info']['total_token_usage']}
  events.append({'timestamp':ts,'total_token_usage':p['info']['total_token_usage']})
assert last
reviews=[]
source=Path('/home/mj/dl_project/repos/aha-3d/runs/ai2thor_floorplan209/capture')
for name in ['layout_review_v5.log','preview_review_v5.log','layout_review_v8.log','reviewer_connection_probe.log']:
 text=(source/name).read_text();m=re.search(r'^tokens used\s*\n([\d,]+)',text,re.M)
 reviews.append({'log':str(source/name),'reported_tokens_used':int(m[1].replace(',','')) if m else None,
                 'model':re.search(r'^model: (.+)$',text,re.M)[1]})
usage={k:v for k,v in last.items() if k!='timestamp'}
usage['uncached_input_tokens']=usage['input_tokens']-usage['cached_input_tokens']
result={'status':'recovered_token_usage_not_billing','model':'gpt-6-astra','session_source':str(session),
 'scope':'Original FloorPlan209 reconstruction turn through handoff; excludes later VoMP and Isaac work',
 'start_utc':start,'last_usage_utc':last['timestamp'],
 'observed_wall_seconds':(datetime.fromisoformat(last['timestamp'].replace('Z','+00:00'))-datetime.fromisoformat(start.replace('Z','+00:00'))).total_seconds(),
 'main_agent_usage':usage,'separate_reviewer_log_counters':reviews,
 'actual_cost_usd':None,'api_equivalent_usd':None,'gpu_seconds':None,
 'limitations':['Cached input is a subset of input; reasoning is a subset of output: do not add twice.',
 'Reviewer text counters lack input/cache/output breakdown; not added to main-session totals.',
 'Automatic approval-review overhead excluded from method-agent usage.',
 'Observed wall interval includes capture, tools, inference, rendering and waiting; not GPU active time.',
 'No invoice, historical pricing or subscription quota attribution established.']}
(HERE/'usage_events.json').write_text(json.dumps(events,indent=2)+'\n')
(HERE/'cost_summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
