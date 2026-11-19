"""Offline agent-driven concurrency/merge smoke: real Blender, no paid model calls.

Uses deterministic proposals and stubbed visual evidence/review. Not a room-quality
or performance benchmark. Never selects an AHA delivery.
"""
import argparse
import json
import threading
import time
from pathlib import Path

from evaluate_aha_parallel import FixtureProvider
from agen3d.multiagent.aha.contracts import load, Plan, Work, Review
from agen3d.multiagent.aha.runtime import digest
from agen3d.multiagent.aha_driven.session import Session
from agen3d.multiagent.store import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = load(args.config)
    if config.preparation:
        parser.error('Supply a prepared construction config')
    config.output = str(args.output.resolve())
    session = Session(config, provider=FixtureProvider(0))
    session.created_at, session.active_seconds = time.time(), 0.
    session.candidates, session.input_binding, session.ready = {}, {}, True
    session.capacity = {'machine': {'fixture': True}, 'selected': {'builds': 2, 'model_calls': 2, 'gpu_jobs': 1}}
    session._model_slots = threading.BoundedSemaphore(2)
    try:
        session.initialize_construction()
        session.inspect()
        original = session.inventory['objects']
        tasks = [Work(task_id=f'fixture_{i}', object_ids=[f'fixture_{i}'],
                      instruction='Build offline fixture cube', parallel_safe=True) for i in range(2)]
        wave = session.build_wave(Plan(summary='Offline driven wave', tasks=tasks))
        assert all(r['status'] == 'built' for r in wave['results'].values()), wave
        assert not session.results
        output = session.output
    finally:
        session.close()
    session = Session.open(output)
    try:
        # The real independent visual review is deliberately NOT claimed by this smoke.
        def bridge(action, scene, folder):
            return {'candidate_revision': digest(scene),
                    'images': {'fixture': next(iter(session.c.source_images.values()))},
                    'object_views': {task.object_ids[0]: ['fixture'] for task in tasks}}
        session.bridge = bridge
        for task in tasks:
            candidate = session.merge(wave['results'][task.task_id]['branch'])['candidate_id']
            session.review(candidate, Review(candidate_revision=session.candidates[candidate]['revision'],
                verdict='pass', severity='routine', defects=[], reviewed_images=['fixture'],
                observations=['Offline fixture only; no visual fidelity assessment']))
            session.commit(candidate)
        assert all(session.inventory['objects'][oid] == value for oid, value in original.items())
        assert all(t.object_ids[0] in session.inventory['objects'] for t in tasks)
        result = {'committed': len(session.results), 'scene': str(session.current),
                  'original_objects_preserved': len(original), 'resumed_between_wave_and_merge': True,
                  'delivery_accepted': False,
                  'limitations': 'Real isolated build/merge/reopen checks; stubbed evidence and review. No fidelity or speed claim.'}
        save(output / 'evaluation.json', result)
        print(json.dumps(result, indent=2))
    finally:
        session.close()


if __name__ == '__main__':
    main()
