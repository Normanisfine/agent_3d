"""Live Qwen/Codex negative-control reviews of an existing offline audit fixture.

Sends the audit's source/render images to configured providers. At most two Qwen
calls (one correction retry) and one Codex call; separate ledger, no room job run.
"""
import argparse
import json
import time
from pathlib import Path

from agen3d.multiagent.aha.contracts import load, Work
from agen3d.multiagent.aha.runtime import Runtime
from agen3d.multiagent.resources import load_env
from agen3d.multiagent.store import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--final-only', action='store_true', help='Run only the native Codex final gate')
    args = parser.parse_args()
    audit = args.audit.resolve()
    if args.env_file:
        load_env(args.env_file)
    previous = json.loads((audit/'audit-report.json').read_text())
    if not previous['ok'] or previous.get('hosted_calls') != 0:
        raise ValueError('Requires a completed offline audit')
    c = load(audit/'config.json').model_copy(update={'output':str(args.output.resolve())})
    r = Runtime(c)
    report = {'scope':'Live review of intentionally incomplete floor fixture; not a room result',
              'ok':False, 'delivery_accepted':False}
    try:
        packet = json.loads((audit/'bridge/0002-prepare.result.json').read_text())
        task = Work(task_id='audit_floor',object_ids=['audit_floor'],instruction='Review floor fixture')
        if not args.final_only:
            packet['candidate_objects'] = json.loads((audit/'candidate/validation.json').read_text())['objects']
            review = r.critic(task, packet)
            save(r.output/'local-review.json',review.model_dump())
            report['qwen_verdict'] = review.verdict
        key = r.ledger.reserve('negative_control_final_judge',c.judge.call_reservation_usd)
        started = time.monotonic()
        try:
            final = r.bridge('review',Path(previous['scene']),audit/'candidate/evidence')
            report['final_verdict'] = final['verdict']
            if final['verdict'] == 'invalid_review':
                raise ValueError('Invalid final review: ' + final['error'])
            if final['verdict'] != 'rejected':
                raise ValueError('Negative control failed: final reviewer accepted a floor-only room')
        finally:
            r.ledger.settle(key,None,{'wall_seconds':time.monotonic()-started,
                                     'scope':'native negative-control final review'})
        report['ok'] = True
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        report.update(cost=r.ledger.summary(),wall_seconds=time.monotonic()-r.started)
        save(r.output/'audit-report.json',report)
        r._job_lock.close()
        print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
