"""Offline native construction/evidence audit on an incomplete floor fixture.

No hosted model calls. This is not a room reconstruction or visual acceptance.
"""
import argparse
import json
import time
from pathlib import Path

from agen3d.multiagent.aha.bootstrap import handoff
from agen3d.multiagent.aha.contracts import load, Proposal, Work
from agen3d.multiagent.aha.runtime import Runtime, reference_summary
from agen3d.multiagent.store import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    h = handoff(args.job.resolve()/'reference', args.job.resolve()/'bootstrap', restore=True)
    c = load(args.config).model_copy(update={
        'preparation': None, 'output': str(args.output.resolve()),
        **{k: h[k] for k in ('source_scene', 'layout_spec', 'source_images')}})
    r = Runtime(c)
    report = {'scope': 'Incomplete floor fixture; offline integration only',
              'delivery_accepted': False, 'hosted_calls': 0, 'ok': False}
    try:
        r.initialize_construction()
        r.bridge('preflight', r.current, r.output/'preflight')
        r.reference = reference_summary(json.loads(Path(c.layout_spec).read_text()))
        r.inspect()
        lo, hi = r.reference['static_reference_quantile_bounds']
        center = [(lo[0]+hi[0])/2, (lo[1]+hi[1])/2, lo[2]-.05]
        dimensions = [hi[0]-lo[0], hi[1]-lo[1], .1]
        task = Work(task_id='audit_floor', object_ids=['audit_floor'],
                    instruction='Inspect this floor-only fixture, not a complete room.')
        proposal = Proposal(parent_revision=r.revision, object_ids=task.object_ids,
            route='code', reason='Deterministic integration fixture',
            code=f'roomkit.box("Audit floor", {center!r}, {dimensions!r}, '
                 'semantic_class="architecture/floor", instance_id="audit_floor", edge=0)\n')
        scene, packet = r.construct(task, proposal, r.output/'candidate')
        report.update(native_evidence_images=len(packet['images']),
                      object_focus_images=len(packet['object_views']['audit_floor']),
                      scene=str(scene), candidate_revision=packet['candidate_revision'])
        report['ok'] = True
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        report.update(cost=r.ledger.summary(), stages=r.stages,
                      wall_seconds=time.monotonic()-r.started)
        save(r.output/'audit-report.json', report)
        r._job_lock.close()
        print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
