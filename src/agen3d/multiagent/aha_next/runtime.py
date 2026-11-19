"""Opt-in controller; original runtime and acceptance gates remain intact."""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace

from ..aha.runtime import Runtime as OriginalRuntime
from ..aha.contracts import Proposal
from ..aha.scheduling import dependency_plan, ready_tasks
from ..store import BudgetExceeded, save
from .recipes import Recipe, compile_recipe


class Runtime(OriginalRuntime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Shared across shallow branch snapshots. A failed cheap build opens the
        # circuit for the job. In-flight calls finish, but no new cheap builds start.
        self.worker_health = {'ready': False, 'disabled': False}
        self.health_lock = threading.Lock()

    def build_packet(self, task, feedback=None):
        packet = super().build_packet(task, feedback)
        # Retain geometry/cameras and all source images. Only drop unrelated history
        # and inventory for explicitly object-local work with declared read sets.
        if task.parallel_safe:
            ids = set(task.object_ids + task.reads_object_ids)
            packet['current_inventory']['objects'] = {
                k: v for k, v in packet['current_inventory']['objects'].items() if k in ids}
            packet.pop('prior_tasks', None)
        return packet

    def call(self, role, schema, packet, images, *, strong=False, retry=False):
        if schema is Proposal and not strong:
            with self.health_lock:
                disabled = self.worker_health['disabled']
            # Strong routing for these cases is performed by work/build_branch;
            # do not hide takeover costs or limits by changing roles here.
            if disabled:
                raise ValueError('Cheap builder circuit is open')
            task = SimpleNamespace(object_ids=packet['task']['object_ids'])
            compact = {k: v for k, v in packet.items() if k not in {
                'helper_api', 'helper_example', 'assembly_example', 'catalog',
                'hunyuan_available', 'generation_mask_ids', 'instruction', 'parallel_contract'}}
            compact['instruction'] = (
                'Return a Recipe, never code. Reconstruct exactly one assigned object from source RGB. '
                'Use at most 16 oriented box parts, centers and FULL extents in world metres, Z-up; '
                'rotation_z is radians. Cite actual source IDs. Preserve the world coordinate basis. '
                'Use route=abstain and parts=[] if evidence is insufficient or boxes cannot faithfully '
                'represent the object. Do not approximate curved furniture as a box merely to finish.')
            try:
                recipe = super().call('recipe_build', Recipe, compact, images)
                return compile_recipe(recipe, task, packet['parent_revision'], images)
            except BudgetExceeded:
                raise
            except Exception:
                with self.health_lock:
                    self.worker_health['disabled'] = True
                raise
        return super().call(role, schema, packet, images, strong=strong, retry=retry)

    def critic(self, task, request, strong=False):
        # Object focus selection can omit a source frame explicitly needed for
        # width/height judgment. Include original RGB alongside ALL required focus
        # views. The inherited binding verifies every delivered image and revision.
        enriched = copy.deepcopy(request)
        for key, path in self.c.source_images.items():
            evidence_id = 'original:' + key
            enriched['images'][evidence_id] = path
            for oid in task.object_ids:
                views = enriched['object_views'].setdefault(oid, [])
                if evidence_id not in views:
                    views.append(evidence_id)
        review = super().critic(task, enriched, strong=strong)
        if review.verdict != 'pass' and not strong:
            review = review.model_copy(update={'severity': 'critical'})
        return review

    def work(self, task, feedback=None, force_strong=False, start_attempt=0):
        if getattr(self, '_defer_repair', False):
            raise ValueError('Merged candidate requires strong repair: ' + str(feedback))
        with self.health_lock:
            disabled = self.worker_health['disabled']
        # One cheap attempt; any repair uses strong reconstruction. Multi-object
        # and exclusive/global tasks retain the expressive strong code builder.
        strong = force_strong or bool(feedback) or disabled
        if len(task.object_ids) != 1 or not task.parallel_safe:
            task = task.model_copy(update={'severity': 'critical'})
        result = super().work(task, feedback, strong, start_attempt)
        with self.health_lock:
            if result['status'] == 'candidate_committed' and not result.get('strong_takeover'):
                self.worker_health['ready'] = True
        return result

    def construct(self, task, proposal, folder, *, prepare_evidence=True):
        try:
            return super().construct(task, proposal, folder, prepare_evidence=prepare_evidence)
        except BudgetExceeded:
            raise
        except Exception:
            with self.health_lock:
                self.worker_health['disabled'] = True
            raise

    def schedule(self, plan):
        # Make planned global/multi-root work explicitly strong before scheduling.
        plan = plan.model_copy(update={'tasks': [
            t.model_copy(update={'severity': 'critical'})
            if not t.parallel_safe or len(t.object_ids) != 1 else t for t in plan.tasks]})
        plan, added = dependency_plan(plan)
        save(self.output / 'dependency-plan.json', {'plan': plan.model_dump(), 'added_edges': added,
             'policy': 'Reviewed cheap canary, bounded waves, completion-order serial merge; deferred strong repair.'})
        wave = 0
        while len(self.results) < len(plan.tasks):
            for task in plan.tasks:
                if task.task_id not in self.results and any(
                    d in self.results and self.results[d]['status'] != 'candidate_committed'
                    for d in task.depends_on):
                    self.results[task.task_id] = {'status': 'blocked_dependency'}
            with self.health_lock:
                warmed = self.worker_health['ready'] or self.worker_health['disabled']
            width = self.capacity['selected']['builds'] if warmed else 1
            ready = ready_tasks(plan, self.results, width)
            if not ready:
                if len(self.results) != len(plan.tasks):
                    raise ValueError('Dependency scheduler has no runnable tasks')
                break
            wave += 1
            save(self.output / 'progress.json', {'phase': 'building', 'wave': wave,
                 'active_tasks': [t.task_id for t in ready], 'worker_health': dict(self.worker_health)})
            if len(ready) == 1:
                task = ready[0]
                self.results[task.task_id] = self.work(task)
            else:
                parent, revision = self.current, self.revision
                repairs = []
                with ThreadPoolExecutor(max_workers=len(ready)) as pool:
                    futures = {}
                    for task in ready:
                        snapshot = copy.copy(self)
                        snapshot.results = dict(self.results)
                        futures[pool.submit(snapshot.build_branch, task, wave, parent, revision)] = task
                    for future in as_completed(futures):
                        task = futures[future]
                        try:
                            branch = future.result()
                            self._defer_repair = True
                            try:
                                self.results[task.task_id] = self.merge_branch(task, branch, wave)
                            finally:
                                self._defer_repair = False
                        except BudgetExceeded:
                            raise
                        except Exception as exc:
                            self.ledger.event('parallel_fallback', {'task': task.task_id, 'error': str(exc)})
                            repairs.append((task, {'parallel_error': str(exc)}))
                        save(self.output / 'tasks.json', self.results)
                for task, feedback in repairs:
                    self.results[task.task_id] = self.work(task, feedback, force_strong=True, start_attempt=1)
            save(self.output / 'tasks.json', self.results)
        save(self.output / 'progress.json', {'phase': 'construction_finished', 'results': self.results,
                                           'worker_health': dict(self.worker_health)})
