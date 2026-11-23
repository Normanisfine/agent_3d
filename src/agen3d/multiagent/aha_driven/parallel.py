"""Agent-selected build waves; merging, review and commit remain explicit steps."""
import copy
import json
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..aha.contracts import Proposal, Work
from ..aha.runtime import HERE, validate_scope
from ..aha.artifacts import file_revision
from ..aha.isolation import execute
from ..aha.scheduling import calibrate, dependency_plan, ready_tasks
from ..store import save


class ParallelSteps:
    def calibrate_capacity(self):
        with self.compute('capacity_calibration', self.c.timeout_s):
            self.capacity = calibrate(self.c, self.output / 'capacity' / uuid.uuid4().hex)
        self._model_slots = threading.BoundedSemaphore(self.capacity['selected']['model_calls'])
        return self.capacity

    def build_wave(self, plan):
        """Build one ready frontier only; never merge, review, retry or commit."""
        if file_revision(self.current) != self.revision:
            raise ValueError('Canonical scene changed outside this session')
        if 'machine' not in self.capacity:
            self.calibrate_capacity()
        plan, edges = dependency_plan(plan)
        tasks = ready_tasks(plan, self.results, self.capacity['selected']['builds'])
        if not tasks:
            raise ValueError('No ready tasks; inspect dependencies and committed results')
        if any(not task.parallel_safe for task in tasks):
            raise ValueError('Exclusive tasks require the serial build/review/commit path')
        if self.boxer is not None:
            for task in tasks:
                self.check_task(task)
        waves = getattr(self, 'waves', {})
        self.waves = waves
        self.branches = getattr(self, 'branches', {})
        number = max([int(k) for k in waves] + [0]) + 1
        key = str(number)
        waves[key] = {'parent': self.revision, 'allowed_revisions': [self.revision],
                      'plan': plan.model_dump(), 'added_edges': edges,
                      'tasks': [t.task_id for t in tasks], 'results': {}}
        parent, revision = self.current, self.revision
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = {}
            for task in tasks:
                snapshot = copy.copy(self)
                snapshot.results = dict(self.results)
                futures[task.task_id] = pool.submit(snapshot.build_branch, task, number, parent, revision)
            for task in tasks:
                identity = f'{number}-{task.task_id}'
                try:
                    branch = futures[task.task_id].result()
                    branch['scene'] = str(branch['scene'])
                    branch['proposal'] = branch['proposal'].model_dump()
                    branch.update(task=task.model_dump(), wave=key, status='built')
                    self.branches[identity] = branch
                    waves[key]['results'][task.task_id] = {'branch': identity, 'status': 'built'}
                except Exception as exc:
                    waves[key]['results'][task.task_id] = {'status': 'failed',
                        'error': f'{type(exc).__name__}: {exc}'}
                    self.ledger.event('driven_branch_failed', waves[key]['results'][task.task_id])
        save(self.output / 'parallel' / f'wave-{number:04d}' / 'wave.json', waves[key])
        return {'wave': key, 'results': waves[key]['results'],
                'next_step': 'Merge each successful branch, then review and commit explicitly.'}

    def merge(self, identity):
        branch = self.branches[identity]
        wave = self.waves[branch['wave']]
        if branch['status'] == 'committed':
            raise ValueError('Branch already committed')
        if self.revision not in wave['allowed_revisions']:
            raise ValueError('Unrelated scene changes invalidate this wave; build a new wave')
        task = Work.model_validate(branch['task'])
        self.check_task(task)
        proposal = Proposal.model_validate(branch['proposal'])
        validate_scope(proposal, task, wave['parent'])
        if branch['parent'] != wave['parent'] or file_revision(branch['scene']) != branch['scene_revision']:
            raise ValueError('Parallel branch changed before merge')
        if file_revision(self.current) != self.revision:
            raise ValueError('Canonical scene changed before merge')
        candidate_id = uuid.uuid4().hex
        folder = self.output / 'candidates' / candidate_id
        folder.mkdir(parents=True)
        shutil.copy2(self.current, folder / 'input.blend')
        shutil.copy2(branch['scene'], folder / 'candidate.blend')
        proposal = proposal.model_copy(update={'parent_revision': self.revision})
        save(folder / 'request.json', {'proposal': proposal.model_dump(), 'merge_only': True,
             'expected_objects': branch['validation']['objects'], 'branch_parent_revision': branch['parent']})
        with self.compute('blender_merge', self.c.timeout_s):
            execute(self.c, folder, HERE / 'blender_worker.py', folder / 'request.json')
        save(folder / 'verify.json', {'proposal': proposal.model_dump(), 'verify_only': True})
        with self.compute('blender_verify', self.c.timeout_s):
            execute(self.c, folder, HERE / 'blender_worker.py', folder / 'verify.json')
        validation = json.loads((folder / 'validation.json').read_text())
        if not validation['ok']:
            raise ValueError('Merged candidate failed validation')
        candidate = folder / 'scene.blend'
        from ..aha.artifacts import record_candidate
        record_candidate(folder, candidate, self.revision, task)
        request = self.bridge('prepare', candidate, folder / 'evidence')
        request['candidate_objects'] = validation['objects']
        result = self.register_candidate(candidate_id, task, candidate, folder, request)
        self.candidates[candidate_id]['branch'] = identity
        return result
