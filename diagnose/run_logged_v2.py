"""Launch one explicitly configured aha_diagnosed_v2 run and retain its final status."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record',type=Path)
    args=parser.parse_args()
    record=json.loads(args.record.read_text())
    if record['status']!='planned':parser.error('Only a planned experiment can be launched')
    root=Path(__file__).resolve().parents[1]
    output=Path(record['output_directory'])
    if output.exists():parser.error('Run output already exists')
    record.update(status='running',started_at_utc=utc(),launcher_pid=os.getpid())
    args.record.write_text(json.dumps(record,indent=2)+'\n')
    with (root/'log/journal.md').open('a') as stream:
        stream.write(f"\n\n## {record['started_at_utc']} — Live diagnosed run started\n\n"
                     f"User requested one run: `{record['experiment_id']}`. Strong construction/review; cheap triage disabled. "
                     f"Fresh output: `{output}`. Existing budget exemptions retained.\n")
    try:
        with Path(record['log_path']).open('x') as log:
            result=subprocess.run([sys.executable,'-u','-m','agen3d.multiagent.aha_diagnosed_v2.cli',
                record['config_snapshot'],'--output',str(output),'--env-file',str(root/'.env'),'--cuda'],
                cwd=root,stdout=log,stderr=subprocess.STDOUT,check=False)
        record['exit_code']=result.returncode
        report=json.loads((output/'report.json').read_text()) if (output/'report.json').exists() else {}
        record.update(status='completed' if result.returncode==0 and report.get('status')=='layout_validated' else 'failed',
                      result_status=report.get('status','process_failed'),error=report.get('error'),
                      report_path=str(output/'report.json'),cost_summary=report.get('cost'),
                      canonical_scene=report.get('scene'),delivery_accepted=report.get('delivery_accepted',False))
    except BaseException as exc:
        record.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        record['finished_at_utc']=utc()
        args.record.write_text(json.dumps(record,indent=2)+'\n')
        with (root/'log/journal.md').open('a') as stream:
            stream.write(f"\nRun `{record['experiment_id']}` finished at {record['finished_at_utc']}: "
                         f"{record['status']} / {record.get('result_status','process_failed')}. "
                         f"See `{output}/report.json` and `{record['log_path']}`. "
                         "Layout validation is separate from full delivery acceptance; unknown costs remain unknown.\n")
    print(json.dumps({k:record.get(k) for k in ('experiment_id','status','result_status','error','report_path')},indent=2))
    raise SystemExit(record.get('exit_code',1))


if __name__=='__main__':main()
