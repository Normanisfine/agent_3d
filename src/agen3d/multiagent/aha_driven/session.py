"""Durable, single-writer operations without an automatic planning/repair loop."""
import fcntl
import json
import time
import threading
import uuid
from pathlib import Path

from ..aha.contracts import Config, Proposal, Review, Work, layout
from ..aha.runtime import Runtime, reference_summary
from ..aha.artifacts import file_revision
from ..aha.reviews import bind
from ..providers import Provider
from ..store import Ledger, save
from .parallel import ParallelSteps
from .inventory import BoxerInventory


FIELDS = ('revision', 'takeovers', 'generations', 'sequence', 'results', 'inventory',
          'reference', 'reference_limitations', 'evidence', 'stages')


def read(path):
    return json.loads(Path(path).read_text())


class Session(ParallelSteps, Runtime):
    """Reuse execution primitives, never Runtime.run/work's automatic policy."""

    boxer: BoxerInventory | None = None

    @classmethod
    def create(cls, config, *, cuda=False, inventory_path=None):
        boxer = BoxerInventory.load(inventory_path) if inventory_path else None
        if boxer is not None:
            config = config.model_copy(update={'hunyuan': None, 'max_generations': 0})
        self = cls(config)
        self.boxer = boxer
        self.created_at = time.time()
        self.active_seconds = 0.
        self.candidates = {}
        self.ready = False
        try:
            if self.c.preparation:
                self.prepare()
            self.initialize_construction()
            self.reference = reference_summary(layout(self.c, self.current))
            self.reference['review_limitations'] = self.reference_limitations
            self.inspect()
            if boxer is not None:
                crop_ids = {'boxer_' + k for k in boxer.crops}
                if crop_ids.intersection(self.evidence):
                    raise ValueError('Boxer crop IDs collide with registered scene evidence')
                save(self.output / 'boxer-inventory.json', boxer.planner_manifest(self.output))
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
            if state.get('boxer') is not None:
                self.boxer = BoxerInventory.model_validate(state['boxer'])
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
            for name in ('created_at', 'active_seconds', 'candidates', 'ready'):
                setattr(self, name, state[name])
            if 'input_binding' in state:
                self.revision = file_revision(self.current)
            elif file_revision(self.current) != self.revision:
                raise ValueError('Canonical scene changed outside this session')
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
                         candidates=self.candidates, ready=self.ready,
                         capacity=self.capacity, branches=getattr(self, 'branches', {}),
                         waves=getattr(self, 'waves', {}))
            if self.boxer is not None:
                state['boxer'] = self.boxer.model_dump()
            save(self.output / 'session.json', state)
            if self.boxer is not None:
                save(self.output / 'inventory-decisions.json', self.inventory_decisions())
            from ..aha.artifacts import safe_export
            safe_export(self)
            save(self.output / 'report.json', self.summary())
        finally:
            self._job_lock.close()

    def summary(self):
        handoff_path = self.output / 'handoff.json'
        handoff = read(handoff_path) if handoff_path.exists() else {}
        status = (handoff.get('layout_status', 'in_progress') if self.ready else 'blocked_preparation')
        inventory_files = {} if self.boxer is None else {
            'boxer_inventory': str(self.output / 'boxer-inventory.json'),
            'inventory_decisions': str(self.output / 'inventory-decisions.json')}
        return {'architecture': 'aha_driven', 'status': status, **inventory_files,
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

    def inventory_decisions(self):
        return self.boxer.decisions(self.boxer.plan, self.results, self.inventory.get('objects', {}))

    def register_inventory_plan(self, plan):
        if self.boxer is None:
            raise ValueError('Initialize the session with --inventory first')
        decisions = self.boxer.decisions(plan, self.results, self.inventory.get('objects', {}))
        for key, previous in self.inventory_decisions().items():
            if previous.get('task') in self.results and decisions[key] != previous:
                raise ValueError(f'Cannot reassign a committed task item: {key}')
            if decisions[key].get('task') in self.results and decisions[key] != previous:
                raise ValueError(f'Cannot add an item to a committed task: {key}')
        if self.boxer.plan != plan:
            if (self.output / 'handoff.json').is_file():
                save(self.output / 'handoff.json', {'scene': str(self.current),
                     'layout_status': 'unreviewed', 'delivery_accepted': False})
            save(self.output / 'inventory-plan.json', plan.model_dump())
            self.boxer.plan = plan
        return decisions

    def check_task(self, task):
        if self.boxer is not None:
            self.boxer.check_scope(task)
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
        if self.boxer is not None:
            items, crops = self.boxer.evidence(task)
            packet['assigned_boxer_items'] = items
            images.update(crops)
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
        registered = self.c.source_images
        if self.boxer is not None:
            items, crops = self.boxer.evidence(task)
            if packet.get('assigned_boxer_items') != items or any(images.get(k) != v for k, v in crops.items()):
                raise ValueError('Worker packet differs from assigned Boxer evidence')
            registered = {**registered, **crops}
        if any(registered.get(k) != v for k, v in images.items()):
            raise ValueError('Worker packet contains unregistered images')
        proposal = self.call('driven_strong_build' if strong else 'driven_build', Proposal,
                             packet, images, strong=strong)
        path = self.output / 'proposals' / (uuid.uuid4().hex + '.json')
        save(path, proposal.model_dump())
        return path

    def call(self, role, schema, packet, images, **kwargs):
        # Parallel branches use Runtime.build_branch instead of the serial packet command.
        if self.boxer is not None and role in ('build', 'strong_build'):
            task = Work.model_validate(packet['task'])
            self.check_task(task)
            items, crops = self.boxer.evidence(task)
            packet = {**packet, 'assigned_boxer_items': items}
            images = {**images, **crops}
        return super().call(role, schema, packet, images, **kwargs)

    def build(self, task, proposal):
        self.check_task(task)
        identity = uuid.uuid4().hex
        folder = self.output / 'candidates' / identity
        candidate, request = self.construct(task, proposal, folder)
        return self.register_candidate(identity, task, candidate, folder, request)

    def register_candidate(self, identity, task, candidate, folder, request):
        save(folder / 'review-request.json', request)
        self.candidates[identity] = {'task': task.model_dump(), 'parent': self.revision,
            'revision': file_revision(candidate), 'scene': str(candidate), 'folder': str(folder),
            'binding': {str(p): file_revision(p) for p in [*request['images'].values(),
                folder / 'review-request.json', folder / 'validation.json']}, 'status': 'built'}
        return {'candidate_id': identity, 'review_request': str(folder / 'review-request.json')}

    def candidate(self, identity):
        row = self.candidates[identity]
        if file_revision(self.current) != self.revision:
            raise ValueError('Canonical scene changed outside this session')
        if row['parent'] != self.revision:
            raise ValueError('Candidate has a stale parent; rebuild against current scene')
        if file_revision(row['scene']) != row['revision']:
            raise ValueError('Candidate scene changed')
        for path, expected in row['binding'].items():
            if file_revision(path) != expected:
                raise ValueError('Candidate evidence changed')
        request = read(Path(row['folder']) / 'review-request.json')
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
        review, _ = bind(review, request['candidate_revision'], images)
        self.candidate(identity)  # Recheck after model call.
        path = Path(row['folder']) / 'local-review.json'
        save(path, review.model_dump())
        row.update(status='reviewed' if review.verdict == 'pass' else 'needs_repair',
                   review_revision=file_revision(path))
        self.ledger.event('driven_review', {'candidate': identity, 'external': external,
                                          'verdict': review.verdict})
        return review.model_dump()

    def commit(self, identity):
        row, request = self.candidate(identity)
        path = Path(row['folder']) / 'local-review.json'
        if row['status'] != 'reviewed' or file_revision(path) != row['review_revision']:
            raise ValueError('Commit requires an unchanged passing review')
        review = Review.model_validate(read(path))
        if review.candidate_revision != request['candidate_revision']:
            raise ValueError('Review belongs to a different evidence revision')
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
        if self.boxer is not None and (self.boxer.plan is None or any(
                d['action'] == 'assigned' for d in self.inventory_decisions().values())):
            raise ValueError('Complete assigned inventory tasks or record omissions before final review')
        if file_revision(self.current) != self.revision:
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
        if file_revision(self.current) != self.revision:
            raise ValueError('Canonical scene changed during final review')
        handoff = {'scene': str(self.current), 'revision': self.revision, 'evidence': str(folder),
                   'layout_status': 'layout_validated' if result['verdict'] == 'accepted'
                                    else 'blocked_review' if result['verdict'] == 'invalid_review'
                                    else 'needs_repair',
                   'delivery_accepted': False,
                   'next_step': 'Use existing AHA task acceptance/delivery workflow.'}
        save(self.output / 'handoff.json', handoff)
        return handoff
