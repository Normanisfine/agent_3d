"""Durable, single-writer operations without an automatic planning/repair loop."""
import fcntl
import json
import time
import threading
import uuid
from pathlib import Path

from ..aha.contracts import Config, Proposal, Review, Work, layout
from ..aha.runtime import Runtime, digest, reference_summary
from ..aha.reviews import bind
from ..providers import Provider
from ..store import Ledger, save
from .parallel import ParallelSteps


FIELDS = ('revision', 'takeovers', 'generations', 'sequence', 'results', 'inventory',
          'reference', 'reference_limitations', 'evidence', 'source_hashes', 'stages')


def read(path):
    return json.loads(Path(path).read_text())


class Session(ParallelSteps, Runtime):
    """Reuse execution primitives, never Runtime.run/work's automatic policy."""

    @classmethod
    def create(cls, config, *, cuda=False):
        self = cls(config)
        self.created_at = time.time()
        self.active_seconds = 0.
        self.candidates = {}
        self.ready = False
        self.input_binding = {}
        try:
            from ..aha.doctor import check
            with self.compute('job_preflight', self.c.timeout_s):
                readiness = check(self.c, cuda=cuda or bool(self.c.preparation))
                save(self.output / 'readiness.json', readiness)
                if not readiness['required_ready']:
                    raise ValueError('Required tools unavailable; see readiness.json')
            if self.c.preparation:
                self.prepare()
            self.initialize_construction()
            self.bridge('preflight', self.current, self.output / 'preflight')
            self.reference = reference_summary(layout(self.c, self.current))
            self.reference['review_limitations'] = self.reference_limitations
            self.inspect()
            inputs = layout(self.c, self.current)
            paths = [self.c.source_scene, self.c.layout_spec, *self.evidence.values()]
            paths.extend(v for k, v in inputs.items() if k != 'source_scene'
                         and isinstance(v, str) and Path(v).is_file())
            self.input_binding = {p: digest(p) for p in paths}
            self.ready = True
            return self
        except BaseException:
            self.close()
            raise

    @classmethod
    def open(cls, output):
        self = cls.__new__(cls)
        self.output = Path(output).resolve()
        self._job_lock = (self.output / '.job.lock').open('a')
        try:
            fcntl.flock(self._job_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state = read(self.output / 'session.json')
            if not state['ready']:
                raise ValueError('Initialization failed; inspect logs and use a fresh output directory')
            self.c = Config.model_validate(state['config'])
            self.initialize_concurrency()
            self.started = time.monotonic()
            self.provider = Provider()
            self.ledger = Ledger(self.output / 'ledger.sqlite', self.c.budget_usd)
            self.current = Path(state['current'])
            self.capacity = state.get('capacity', self.capacity)
            self._model_slots = threading.BoundedSemaphore(self.capacity['selected']['model_calls'])
            self.branches = state.get('branches', {})
            self.waves = state.get('waves', {})
            for name in FIELDS:
                setattr(self, name, state[name])
            for name in ('created_at', 'active_seconds', 'candidates', 'ready', 'input_binding'):
                setattr(self, name, state[name])
            if digest(self.current) != self.revision:
                raise ValueError('Canonical scene changed outside this session')
            for path, expected in self.input_binding.items():
                if digest(path) != expected:
                    raise ValueError('Bound input changed: ' + path)
            entries = read(Path(self.c.aha_repo) / 'assets/index.json')['entries']
            self.catalog = {r['id']: r for r in entries
                            if r.get('kind') == 'collection' and r.get('status') == 'registered'}
            return self
        except BaseException:
            self._job_lock.close()
            raise

    def close(self):
        try:
            self.active_seconds += time.monotonic() - self.started
            state = {name: getattr(self, name) for name in FIELDS}
            state.update(config=self.c.model_dump(), current=str(self.current) if self.current else None,
                         created_at=self.created_at, active_seconds=self.active_seconds,
                         candidates=self.candidates, ready=self.ready, input_binding=self.input_binding,
                         capacity=self.capacity, branches=getattr(self, 'branches', {}),
                         waves=getattr(self, 'waves', {}))
            save(self.output / 'session.json', state)
            from ..aha.artifacts import safe_export
            safe_export(self)
            save(self.output / 'report.json', self.summary())
        finally:
            self._job_lock.close()

    def summary(self):
        handoff_path = self.output / 'handoff.json'
        handoff = read(handoff_path) if handoff_path.exists() else {}
        status = (handoff.get('layout_status', 'in_progress') if self.ready else 'blocked_preparation')
        return {'architecture': 'aha_driven', 'status': status,
                'output': read(self.output / 'output.json') if (self.output / 'output.json').exists() else None,
                'scene': str(self.current), 'revision': self.revision,
                'ready': self.ready, 'results': self.results, 'capacity': self.capacity,
                'branches': {k: {'task_id': v['task']['task_id'], 'status': v['status']}
                             for k, v in getattr(self, 'branches', {}).items()},
                'candidates': {k: {'task_id': v['task']['task_id'], 'status': v['status']}
                               for k, v in self.candidates.items()},
                'active_command_seconds': self.active_seconds,
                'elapsed_seconds': time.time() - self.created_at,
                'cost': self.ledger.summary(), 'external_supervisor_usage': None,
                'accounting_note': 'Conversation and external subagent tokens/time are not captured. '
                    'Use provider exports for total-cost comparisons; unknown is not zero.',
                'delivery_accepted': False}

    def check_task(self, task):
        for dependency in task.depends_on:
            if self.results.get(dependency, {}).get('status') != 'candidate_committed':
                raise ValueError('Uncommitted dependency: ' + dependency)

    def packet(self, task, image_ids, asset_ids):
        self.check_task(task)
        if not image_ids:
            raise ValueError('Select at least one source image')
        images = {k: self.c.source_images[k] for k in image_ids}
        assets = [{k: self.catalog[a].get(k) for k in ('id', 'name', 'dimensions_m')}
                  for a in asset_ids]
        shared = self.build_packet(task)
        packet = {'task': task.model_dump(), 'parent_revision': self.revision,
                  'reference_geometry': self.reference, 'catalog': assets,
                  'current_inventory': shared['current_inventory'],
                  'instruction': shared['instruction'] + ' Abstain when evidence is insufficient.',
                  'parallel_contract': shared['parallel_contract'],
                  'helper_api': shared['helper_api'],
                  'helper_example': shared['helper_example'],
                  'assembly_example': shared['assembly_example'],
                  'images': images, 'schema': Proposal.model_json_schema()}
        folder = self.output / 'packets' / uuid.uuid4().hex
        save(folder / 'packet.json', packet)
        return folder / 'packet.json'

    def propose(self, packet_path, *, strong=False):
        packet = read(packet_path)
        task = Work.model_validate(packet['task'])
        self.check_task(task)
        if packet['parent_revision'] != self.revision:
            raise ValueError('Stale worker packet')
        images = packet.pop('images')
        if any(self.c.source_images.get(k) != v for k, v in images.items()):
            raise ValueError('Worker packet contains unregistered images')
        proposal = self.call('driven_strong_build' if strong else 'driven_build', Proposal,
                             packet, images, strong=strong)
        path = self.output / 'proposals' / (uuid.uuid4().hex + '.json')
        save(path, proposal.model_dump())
        return path

    def build(self, task, proposal):
        self.check_task(task)
        identity = uuid.uuid4().hex
        folder = self.output / 'candidates' / identity
        candidate, request = self.construct(task, proposal, folder)
        return self.register_candidate(identity, task, candidate, folder, request)

    def register_candidate(self, identity, task, candidate, folder, request):
        save(folder / 'review-request.json', request)
        self.candidates[identity] = {'task': task.model_dump(), 'parent': self.revision,
            'revision': digest(candidate), 'scene': str(candidate), 'folder': str(folder),
            'binding': {str(p): digest(p) for p in [*request['images'].values(),
                folder / 'review-request.json', folder / 'validation.json']}, 'status': 'built'}
        return {'candidate_id': identity, 'review_request': str(folder / 'review-request.json')}

    def candidate(self, identity):
        row = self.candidates[identity]
        if digest(self.current) != self.revision:
            raise ValueError('Canonical scene changed outside this session')
        if row['parent'] != self.revision:
            raise ValueError('Candidate has a stale parent; rebuild against current scene')
        if digest(row['scene']) != row['revision']:
            raise ValueError('Candidate scene changed')
        for path, expected in row['binding'].items():
            if digest(path) != expected:
                raise ValueError('Candidate evidence changed')
        request = read(Path(row['folder']) / 'review-request.json')
        if request['candidate_revision'] != row['revision']:
            raise ValueError('Review request revision differs from candidate')
        return row, request

    def review(self, identity, review=None, *, strong=False):
        row, request = self.candidate(identity)
        task = Work.model_validate(row['task'])
        images = {k: request['images'][k] for oid in task.object_ids
                  for k in request['object_views'].get(oid, [])}
        if any(not request['object_views'].get(oid) for oid in task.object_ids):
            raise ValueError('Missing object review evidence')
        external = review is not None
        review = review or self.critic(task, request, strong=strong)
        review, _ = bind(review, row['revision'], images)
        self.candidate(identity)  # Recheck after model call.
        path = Path(row['folder']) / 'local-review.json'
        save(path, review.model_dump())
        row.update(status='reviewed' if review.verdict == 'pass' else 'needs_repair',
                   review_hash=digest(path))
        self.ledger.event('driven_review', {'candidate': identity, 'external': external,
                                          'verdict': review.verdict})
        return review.model_dump()

    def commit(self, identity):
        row, _ = self.candidate(identity)
        path = Path(row['folder']) / 'local-review.json'
        if row['status'] != 'reviewed' or digest(path) != row['review_hash']:
            raise ValueError('Commit requires an unchanged passing review')
        review = Review.model_validate(read(path))
        if review.verdict != 'pass':
            raise ValueError('Review rejected candidate')
        self.check_task(Work.model_validate(row['task']))
        self.current, self.revision = Path(row['scene']), row['revision']
        self.inventory = read(Path(row['folder']) / 'validation.json')
        row['status'] = 'committed'
        if row.get('branch'):
            branch = self.branches[row['branch']]
            branch['status'] = 'committed'
            self.waves[branch['wave']]['allowed_revisions'].append(self.revision)
        receipt = {'status': 'candidate_committed', 'scene': str(self.current),
                   'revision': self.revision, 'final_accepted': False}
        self.results[row['task']['task_id']] = receipt
        save(self.output / 'latest_candidate.json', receipt)
        # Any prior final gate describes a different scene revision.
        save(self.output / 'handoff.json', {'scene': str(self.current),
             'layout_status': 'unreviewed', 'delivery_accepted': False})
        return receipt

    def final_review(self):
        if digest(self.current) != self.revision:
            raise ValueError('Canonical scene changed outside this session')
        folder = self.output / ('final-evidence-' + uuid.uuid4().hex)
        self.bridge('prepare', self.current, folder)
        key = self.ledger.reserve('final_judge', self.c.judge.call_reservation_usd,
                                 budget_exempt=self.c.exempt(self.c.judge), category='codex_cli')
        started = time.monotonic()
        try:
            result = self.bridge('review', self.current, folder)
        finally:
            self.ledger.settle(key, None, {'backend': 'codex', 'native_aha_gate': True,
                                         'wall_seconds': time.monotonic() - started})
        if digest(self.current) != self.revision:
            raise ValueError('Canonical scene changed during final review')
        handoff = {'scene': str(self.current), 'revision': self.revision, 'evidence': str(folder),
                   'layout_status': 'layout_validated' if result['verdict'] == 'accepted'
                                    else 'blocked_review' if result['verdict'] == 'invalid_review'
                                    else 'needs_repair',
                   'delivery_accepted': False,
                   'next_step': 'Use existing AHA task acceptance/delivery workflow.'}
        save(self.output / 'handoff.json', handoff)
        return handoff
