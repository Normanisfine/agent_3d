"""AHA-backed construction queue with local critique and explicit strong takeover."""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
import json
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

from ..resources import Checkpoints
from ..process import run_process
from ..providers import Provider
from ..store import BudgetExceeded, Ledger, save
from .contracts import Plan, Proposal, Review, ReferenceReview, Work, layout
from .artifacts import file_revision
from .isolation import execute
from .reviews import bind as bind_review
from .scheduling import HostMeter, calibrate, dependency_plan, ready_tasks

HERE = Path(__file__).parent


class InvalidFinalReview(RuntimeError):
    pass


def validate_scope(proposal, task, revision):
    if proposal.parent_revision != revision:
        raise ValueError('Stale candidate parent revision')
    if set(proposal.object_ids) != set(task.object_ids):
        raise ValueError('Candidate scope differs from assigned object IDs')


def resume_state(output, config):
    previous = json.loads((output / 'report.json').read_text())
    original = json.loads((output / 'config.json').read_text())
    if original != config.model_dump():
        raise ValueError('Resume requires the original unchanged job configuration/budget')
    if (previous['status'] != 'blocked_preparation' or not config.preparation or
            not (output / 'ledger.sqlite').is_file() or
            not any(s['stage'] == 'construction_bootstrap' and s['status'] == 'complete'
                    for s in previous['stages'])):
        raise ValueError('Resume supports only completed preparation blocked at reference review')
    return previous


def reference_summary(spec):
    """Bounded numerical evidence, always carrying source pixel/frame provenance."""
    import numpy as np
    cameras = json.loads(Path(spec['cameras']).read_text())
    config = json.loads(Path(spec['config']).read_text())
    with np.load(spec['reference'], allow_pickle=False) as ref:
        valid = (ref['geometry_valid'].astype(bool) & (ref['layer'] == 0)
                 & np.isfinite(ref['vertices']).all(axis=1))
        indices = np.flatnonzero(valid)
        if not len(indices):
            raise ValueError('No geometrically valid static reference points')
        selected = indices[np.linspace(0, len(indices)-1, min(64, len(indices))).astype(int)]
        points = ref['vertices'][indices]
        samples = [{'xyz': ref['vertices'][i].tolist(), 'source_frame': int(ref['source_frame'][i]),
                    'pixel_yx': ref['pixel_yx'][i].tolist(), 'confidence': float(ref['confidence'][i])}
                   for i in selected]
        bounds = np.quantile(points, [.02, .98], axis=0).tolist()
    return {'units': cameras['units'], 'model_to_world': config['model_to_world'],
            'source_cameras': [row for row in cameras['frames']
                               if row['source_frame'] in config['source_frames']],
            'static_reference_quantile_bounds': bounds, 'reference_samples': samples,
            'limitations': 'Sparse samples are context, not object bounds. Hidden space is unknown; scale is predicted.'}


class Runtime:
    def initialize_concurrency(self):
        self._model_slots = threading.BoundedSemaphore(1)
        self._stage_lock = threading.Lock()
        self._host_meter = HostMeter()
        self.capacity = {"selected": {"builds": 1, "model_calls": 1}}

    def __init__(self, config, provider=None, *, resume_preparation=False):
        self.initialize_concurrency()
        self.started = time.monotonic()
        self.c = config
        self.output = Path(config.output)
        self.output.mkdir(parents=True, exist_ok=resume_preparation)
        import fcntl
        self._job_lock = (self.output / '.job.lock').open('a')
        try:
            fcntl.flock(self._job_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            previous = resume_state(self.output, config) if resume_preparation else None
        except BaseException:
            self._job_lock.close()
            raise
        self.resume_preparation = resume_preparation
        self.previous_wall_seconds = previous['wall_seconds'] if previous else 0.
        self.ledger = Ledger(self.output / 'ledger.sqlite', config.budget_usd)
        self.provider = provider or Provider()
        self.current = None
        self.revision = None
        self.takeovers = self.generations = 0
        self.sequence = 0
        self.results = {}
        self.inventory = {}
        self.reference = None
        self.reference_limitations = []
        self.evidence = {**config.source_images, **config.masks}
        self.stages = previous['stages'] if previous else []
        if previous:
            import uuid
            history = self.output / 'history' / uuid.uuid4().hex
            history.mkdir(parents=True)
            shutil.copy2(self.output / 'report.json', history / 'report.json')
            if (self.output / 'reference-review.json').exists():
                shutil.copy2(self.output / 'reference-review.json', history / 'reference-review.json')
        else:
            save(self.output / 'config.json', config.model_dump())

    @contextmanager
    def compute(self, label, timeout, reservation=None):
        """Bill non-overlapping local execution intervals, including failed attempts."""
        rate = self.c.host_hourly_usd
        amount = reservation or self.c.compute_reservation_usd
        if rate is not None:
            amount = max(amount, timeout * rate / 3600)
        key = self.ledger.reserve(label, amount,
            self.c.judge_holdback + self.c.repair_holdback,
            budget_exempt=self.c.local_compute_budget_exempt, category='local_compute')
        started = time.monotonic()
        self._host_meter.start(key)
        stage = {'stage': label, 'status': 'failed', 'hourly_usd': rate,
                 'resource': 'local host wall time (CPU/GPU together; no utilization estimate)'}
        try:
            yield
            stage['status'] = 'complete'
        finally:
            stage['wall_seconds'] = time.monotonic() - started
            stage['billed_host_seconds'] = self._host_meter.finish(key)
            actual = stage['billed_host_seconds'] * rate / 3600 if rate is not None else None
            self.ledger.settle(key, actual, stage)
            with self._stage_lock:
                self.stages.append(stage)
                save(getattr(self, '_stage_output', self.output) / 'stages.json', self.stages)

    def prepare(self):
        from .reference import prepare, source_video
        from .bootstrap import bootstrap, handoff
        if self.resume_preparation:
            with self.compute('preparation_reuse_validation', self.c.timeout_s):
                generated = handoff(self.output / 'reference', self.output / 'bootstrap', restore=True)
            self.review_reference(generated)
            return
        prep = self.c.preparation
        video = source_video(prep.input)
        save(self.output / 'source.json', {'video': str(video)})
        reference = self.output / 'reference'
        with self.compute('reference_preparation', prep.timeout_s, prep.reservation_usd):
            result = prepare(reference, video=video, timeout=prep.timeout_s,
                aha_repo=self.c.aha_repo, python=self.c.python,
                num_frames=prep.num_frames, pixel_limit=prep.pixel_limit)
            if not result['ok']:
                raise RuntimeError('Reference preparation failed; see ' + result['log'])
        with self.compute('construction_bootstrap', self.c.timeout_s):
            generated = bootstrap(self.c, reference, self.output / 'bootstrap', video)
        self.review_reference(generated)

    def review_reference(self, generated):
        review = self.cached_reference_review(generated) if self.resume_preparation else None
        if review is None:
            review = self.call('reference_review', ReferenceReview,
            {'candidate_revision': generated['revision'], 'alignment': generated['alignment'],
             'instruction': 'Review every source/reference/overlay and floor/wall support image. '
                 'Decide whether camera alignment, floor/up axis and reference coverage are usable '
                 'for room construction. Reject incorrect geometry/alignment or insufficient evidence. '
                 'Predicted scale is uncalibrated; projection consistency alone is not accuracy. '
                 'This review permits construction only and never accepts the final room. '
                 'Put only problems that block construction in defects; pass requires defects=[]. '
                 'Put non-blocking caveats in limitations. Never downgrade a blocking defect to get a pass.'},
                generated['review_images'], strong=True)
        save(self.output / 'reference-review.json', review.model_dump())
        if review.verdict != 'pass':
            raise ValueError('Reference review requires repair: ' + '; '.join(review.defects))
        self.c = self.c.model_copy(update={key: generated[key]
            for key in ('source_scene', 'layout_spec', 'source_images')})
        self.c.preparation = None
        save(self.output / 'construction-config.json', self.c.model_dump())
        self.reference_limitations = review.limitations

    def cached_reference_review(self, generated):
        # Only the latest call is eligible: never revive an older pass over a rejection.
        with self.ledger.connect() as db:
            row = db.execute("SELECT id FROM charges WHERE label='reference_review' ORDER BY rowid DESC LIMIT 1").fetchone()
        if not row:
            return None
        receipt_path = self.output / 'calls' / (row[0] + '.json')
        if not receipt_path.is_file():
            return None
        receipt = json.loads(receipt_path.read_text())
        expected = {key: file_revision(path) for key, path in generated['review_images'].items()}
        if receipt.get('images') != expected:
            return None
        try:
            review, aliases = bind_review(ReferenceReview.model_validate_json(receipt['text']),
                                         generated['revision'], generated['review_images'])
        except (ValueError, KeyError):
            return None
        if review.verdict != 'pass':
            return None
        save(self.output / 'reference-review-reuse.json', {'call_id': row[0],
             'revision': generated['revision'],
             'image_aliases': aliases, 'reason': 'Same reference revision and review images'})
        self.ledger.event('reference_review_reused', {'call_id': row[0], 'aliases': aliases})
        return review

    def initialize_construction(self):
        self.current = Path(self.c.source_scene)
        self.revision = file_revision(self.current)
        self.evidence = {**self.c.source_images, **self.c.masks}
        entries = json.loads((Path(self.c.aha_repo) / 'assets/index.json').read_text())['entries']
        self.catalog = {row['id']: row for row in entries
                        if row.get('kind') == 'collection' and row.get('status') == 'registered'}

    def call(self, role, schema, packet, images, *, strong=False, retry=False):
        spec = self.c.supervisor if strong else self.c.worker
        holdback = self.c.judge_holdback + (
            self.c.repair_holdback if not strong or role in {'plan', 'reference_review'} else 0)
        paths = [Path(p) for p in images.values()]
        image_versions = ({k: file_revision(p) for k, p in images.items()}
                          if role == 'reference_review' else list(images))
        key = self.ledger.reserve(role, spec.call_reservation_usd, holdback,
                                  budget_exempt=self.c.exempt(spec),
                                  category='codex_cli' if spec.backend == 'codex' else 'paid_api')
        reply = None
        start = time.monotonic()
        response_schema = schema.model_json_schema()
        if issubclass(schema, Proposal):
            response_schema['required'] = list(dict.fromkeys([*response_schema.get('required', []), 'code']))
            response_schema['properties']['code']['description'] = (
                'Complete executable Blender Python for route=code, not a plan or import list. '
                'Use provided globals bpy, roomkit, tag_root, remove_object and object_ids. '
                'Use an empty string only for non-code routes.')
        if issubclass(schema, Review):
            response_schema['properties']['candidate_revision']['const'] = packet['candidate_revision']
            response_schema['properties']['reviewed_images'].update(
                items={'type': 'string', 'enum': list(images)},
                minItems=len(images), maxItems=len(images), uniqueItems=True)
        try:
            from contextlib import nullcontext
            with getattr(self, '_model_slots', nullcontext()):
                reply = self.provider.complete(spec,
                    'Return only JSON matching the supplied schema. Use attached images as evidence. '
                    'Do not claim execution: the scheduler executes and verifies artifacts. '
                    'No native shell/tools are available. Report uncertainty and abstain if needed.',
                    {**packet, 'schema': response_schema, 'image_order': list(images),
                     'image_manifest': [{'id': k, 'filename': Path(v).name}
                                        for k, v in images.items()],
                     'evidence_response_rule': (
                         'Copy candidate_revision exactly. reviewed_images must contain every exact image_order ID once; '
                         'filenames are not the requested IDs.' if issubclass(schema, Review) else
                         'Follow the response schema. For a construction Proposal, copy parent_revision and assigned '
                         'object_ids exactly; route=code requires a complete executable program in code.')}, paths, self.output)
        finally:
            self.ledger.settle(key, reply.actual_usd if reply else None,
                               {'usage': reply.usage if reply else {}, 'role': role, 'backend': spec.backend,
                                'wall_seconds': time.monotonic()-start})
        save(self.output / 'calls' / f'{key}.json', {'text': reply.text, 'images': image_versions,
             'backend': spec.backend, 'model': spec.model, 'usage': reply.usage,
             'raw_text': getattr(reply, 'raw_text', None)})
        if reply.usage.get('finish_reason') == 'length':
            raise ValueError('Model output truncated at max_output_tokens; see recorded response and usage')
        try:
            parsed = schema.model_validate_json(reply.text)
            if isinstance(parsed, Review):
                parsed, aliases = bind_review(parsed, packet['candidate_revision'], images)
                if aliases:
                    self.ledger.event('review_image_aliases', {'call': key, 'aliases': aliases})
            return parsed
        except (ValidationError, ValueError) as exc:
            if not issubclass(schema, Review) or retry:
                raise
            self.ledger.event('invalid_review', {'call': key, 'error': str(exc)})
            return self.call(role, schema, {**packet, 'previous_invalid_response': reply.text,
                'validation_error': str(exc), 'correction_instruction':
                'Re-evaluate the evidence and return a consistent response. Do not discard blockers. '
                'Use repair with blocking defects, or pass with no blocking defects and explicit limitations.'},
                images, strong=strong, retry=True)

    def bridge(self, action, scene, folder):
        self.sequence += 1
        request = self.output / 'bridge' / f'{self.sequence:04d}-{action}.json'
        result = request.with_suffix('.result.json')
        save(request, {'action': action, 'aha_repo': self.c.aha_repo,
            'blender': self.c.blender, 'spec': layout(self.c, scene),
            'evidence_dir': str(folder), 'result': str(result), 'judge': self.c.judge.model_dump()})
        # Review is a model charge; do not charge local rendering time twice.
        from contextlib import nullcontext
        meter = self.compute('aha_' + action, self.c.timeout_s) if action != 'review' else nullcontext()
        with meter, request.with_suffix('.log').open('w') as log:
            process = run_process([self.c.python, str(HERE / 'bridge.py'), str(request)],
                                  timeout=self.c.timeout_s, stdout=log, stderr=log)
            if process.returncode or not result.is_file():
                raise RuntimeError(f'AHA {action} failed; see {request.with_suffix(".log")}')
        return json.loads(result.read_text())

    def inspect(self):
        folder = self.output / 'initial-inspection'
        folder.mkdir()
        shutil.copy2(self.current, folder / 'input.blend')
        save(folder / 'request.json', {'inspect_only': True})
        with self.compute('initial_inspection', self.c.timeout_s):
            execute(self.c, folder, HERE / 'blender_worker.py', folder / 'request.json')
        self.inventory = json.loads((folder / 'inventory.json').read_text())

    def generate(self, proposal, folder):
        if not self.c.hunyuan or self.generations >= self.c.max_generations:
            raise ValueError('Hunyuan unavailable or generation limit reached')
        if proposal.image_id not in self.c.source_images or proposal.mask_id not in self.c.masks:
            raise ValueError('Generation requires registered source image and mask')
        service = self.c.hunyuan
        checkpoint = Checkpoints().entrypoint(service.checkpoint)
        with Image.open(self.evidence[proposal.image_id]) as im, Image.open(self.evidence[proposal.mask_id]) as mask:
            if im.size != mask.size:
                raise ValueError('Mask and source raster must match; no implicit resize')
            rgba = im.convert('RGBA')
            mask = mask.convert('L')
            bounds = mask.getbbox()
            if not bounds:
                raise ValueError('Empty generation mask')
            rgba.putalpha(mask)
            rgba.crop(bounds).save(folder / 'crop.png')
        request = {'service': 'hunyuan', 'repo': service.repo, 'checkpoint': str(checkpoint),
                   'image': str(folder / 'crop.png'), 'seed': 42, 'output': str(folder / 'generation')}
        save(folder / 'generation-request.json', request)
        (folder / 'generation').mkdir()
        self.generations += 1
        with self.compute('hunyuan', service.timeout_s, service.reservation_usd):
            env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
            import fcntl
            with (self.output.parent / '.agen3d-gpu.lock').open('a') as lock, (folder / 'generation.log').open('w') as log:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                proc = run_process([service.python, str(HERE.parent / 'specialist_worker.py'),
                                    str(folder / 'generation-request.json')],
                                   timeout=service.timeout_s, stdout=log, stderr=log, env=env)
            mesh = folder / 'generation/mesh.glb'
            if proc.returncode or not mesh.is_file() or not mesh.stat().st_size:
                raise RuntimeError('Hunyuan failed to export a mesh; inspect generation.log')
            shutil.copy2(mesh, folder / 'mesh.glb')

    def construct(self, task, proposal, folder, *, prepare_evidence=True):
        validate_scope(proposal, task, self.revision)
        if file_revision(self.current) != self.revision:
            raise ValueError('Canonical scene changed outside the committer')
        if proposal.route == 'abstain':
            raise ValueError('Worker abstained: ' + proposal.reason)
        if proposal.route == 'asset' and proposal.asset_id not in self.catalog:
            raise ValueError('Unregistered collection asset')
        if proposal.route == 'code':
            compile(proposal.code, '<generated build.py>', 'exec')
        folder.mkdir(parents=True, exist_ok=False)
        shutil.copy2(self.current, folder / 'input.blend')
        save(folder / 'request.json', {'proposal': proposal.model_dump()})
        (folder / 'build.py').write_text(proposal.code)
        if proposal.route == 'hunyuan':
            self.generate(proposal, folder)
        with self.compute('blender_build', self.c.timeout_s):
            execute(self.c, folder, HERE / 'blender_worker.py', folder / 'request.json')
        candidate = folder / 'scene.blend'
        if not candidate.is_file() or candidate.is_symlink() or not candidate.stat().st_size:
            raise ValueError('No usable saved scene receipt')
        # Reopen in a fresh process, without executing the generated program.
        save(folder / 'verify.json', {'proposal': proposal.model_dump(), 'verify_only': True})
        with self.compute('blender_verify', self.c.timeout_s):
            execute(self.c, folder, HERE / 'blender_worker.py', folder / 'verify.json')
        validation = json.loads((folder / 'validation.json').read_text())
        if not validation['ok']:
            raise ValueError('Candidate failed artifact checks')
        from .artifacts import record_candidate
        record_candidate(folder, candidate, proposal.parent_revision, task)
        if not prepare_evidence:
            return candidate, validation
        review_request = self.bridge('prepare', candidate, folder / 'evidence')
        review_request['candidate_objects'] = validation['objects']
        return candidate, review_request

    def critic(self, task, request, strong=False):
        images = {key: request['images'][key] for oid in task.object_ids
                  for key in request['object_views'].get(oid, [])}
        if not images:
            raise ValueError('No source-bound object focus evidence')
        # Review exact IDs individually, then aggregate. Never truncate required views.
        observations, defects = [], []
        severity = 'routine'
        reviewed = []
        def review_object(oid):
            ids = request['object_views'].get(oid, [])
            if not ids:
                raise ValueError('Required object missing from AHA review packet: ' + oid)
            supplied = {k: request['images'][k] for k in ids}
            review = self.call('strong_critic' if strong else 'local_critic', Review,
                {'candidate_revision': request['candidate_revision'], 'object_id': oid,
                 'candidate_object': request.get('candidate_objects', {}).get(oid),
                 'task_instruction': task.instruction,
                 'image_legend': 'These are AHA object-focus overlays, not candidate RGB renders. '
                     'The colored highlighted contour is the assigned candidate object. '
                     'Source-view backgrounds are actual source RGB; top/front/side backgrounds are '
                     'the approximate reconstructed reference mesh. Holes, streaks or missing surfaces '
                     'in those backgrounds are not evidence of holes in the candidate. '
                     'Use the highlighted contour and supplied object metadata to assess the assigned '
                     'object only. Do not demand unrelated, unassigned objects. If a feature cannot be '
                     'assessed from contours, state that limitation rather than inventing a defect.',
                 'instruction': 'Compare source and candidate geometry, dimensions, orientation, '
                 'support and neighbors. A missing part or incorrect silhouette is a defect.'},
                supplied, strong=strong)
            if (review.candidate_revision != request['candidate_revision'] or
                    set(review.reviewed_images) != set(supplied)):
                raise ValueError('Critic omitted images or reviewed a stale revision')
            return review

        count = getattr(self, "capacity", {}).get("selected", {}).get("model_calls", 1)
        with ThreadPoolExecutor(max_workers=min(count, len(task.object_ids))) as pool:
            reviews = list(pool.map(review_object, task.object_ids))
        for review in reviews:
            observations.extend(review.observations)
            defects.extend(review.defects)
            reviewed.extend(review.reviewed_images)
            if review.severity == 'critical':
                severity = 'critical'
        return Review(candidate_revision=request['candidate_revision'],
                      verdict='repair' if defects else 'pass', severity=severity,
                      observations=observations, defects=defects, reviewed_images=reviewed)

    def build_packet(self, task, feedback=None):
        # Full review receipts remain on disk; builders need actionable findings, not
        # repeated observations about every passing object from earlier attempts.
        if isinstance(feedback, dict):
            feedback = {k: v for k, v in feedback.items() if k not in {'observations', 'reviewed_images'}}
        return {'task': task.model_dump(), 'parent_revision': self.revision,
            'instruction': 'Construct or repair assigned semantic roots. Use roomkit helpers and bpy. '
            'Code has globals bpy, roomkit, tag_root, remove_object(id), object_ids. '
            'Use these provided globals directly; do not import roomkit or load source image IDs as Blender datablocks. '
            'Call tag_root for every complete object. Do not change other IDs or cameras. '
            'Scene is already open; runtime saves it. Scene coordinates are right-handed, Z-up, in metres. '
            'roomkit.box location is its CENTER; dimensions are FULL sizes along (X, Y, Z). '
            'Height is Z. For a floor-standing item, center_z - height/2 must meet the support floor. '
            'For a wall at constant Y, width is X and depth is Y. Preserve the existing world basis.',
            'parallel_contract': 'If parallel_safe is true, bake modifiers, use self-contained semantic roots '
                'without external parent/constraint/driver references, and do not change world/render settings '
                'or shared materials. Only assigned hierarchies will be imported into the canonical scene.',
            'catalog': [{'id': k, 'name': v['name'], 'dimensions': v.get('dimensions_m')}
                        for k, v in self.catalog.items()], 'feedback': feedback,
            'evidence_ids': list(self.evidence),
            'hunyuan_available': self.c.hunyuan is not None and bool(self.c.masks),
            'generation_mask_ids': list(self.c.masks),
            'prior_tasks': {key: {'status': value['status']} for key, value in self.results.items()},
            'current_inventory': {'objects': self.inventory.get('objects', {})},
            'reference_geometry': self.reference,
            'helper_api': 'roomkit.box(name, location, dimensions, material=None, target=None, edge=.008, '
                'semantic_class=None, instance_id=None, support_id=None); '
                'tag_root(root, semantic_class, instance_id=None, asset_id=None, support_id=None). '
                'box returns an already-tagged semantic root if semantic_class is supplied; do not tag it twice. '
                'tag_root accepts a Blender Object, never an object-name string.',
            'helper_example': 'root = roomkit.box("part", (0, 0, 1), (1, 1, .1), '
                'semantic_class="furniture/table", instance_id="assigned_id") '
                '# root is already tagged; substitute your assigned ID and evidence-based geometry.',
            'assembly_example': 'For a multipart object, give the ID to ONE Empty root, never to every part:\n'
                'root = bpy.data.objects.new(object_ids[0], None)\n'
                'bpy.context.scene.collection.objects.link(root)\n'
                'for name, center, size in parts:\n'
                '    child = roomkit.box(name, center, size)  # no semantic_class or instance_id\n'
                '    child.parent = root  # root is at the origin, so coordinates stay unchanged\n'
                'tag_root(root, "architecture/door", instance_id=object_ids[0])\n'
                'Define parts with your actual geometry. Exactly one root per assigned ID.'}

    def work(self, task, feedback=None, force_strong=False, start_attempt=0):
        strong = force_strong or task.severity == 'critical'
        takeover_counted = False
        for attempt in range(start_attempt, 3):
            # Planned supervisor work is not a takeover from a failed worker.
            if strong and (force_strong or task.severity != 'critical') and not takeover_counted:
                if self.takeovers >= self.c.max_takeovers:
                    return {'status': 'blocked_construction', 'reason': 'Strong takeover limit'}
                self.takeovers += 1
                takeover_counted = True
                self.ledger.event('takeover', {'task': task.task_id, 'feedback': feedback,
                                             'parent_revision': self.revision})
            packet = self.build_packet(task, feedback)
            try:
                proposal = self.call('strong_build' if strong else 'build', Proposal,
                                     packet, self.c.source_images, strong=strong)
                folder = self.output / 'candidates' / f'{task.task_id}-{self.sequence:04d}-{attempt}'
                candidate, request = self.construct(task, proposal, folder)
                review = self.critic(task, request, strong=strong)
                save(folder / 'local-review.json', review.model_dump())
                if review.verdict == 'pass':
                    # Serial commit after rechecking the immutable parent.
                    if file_revision(self.current) != proposal.parent_revision:
                        raise ValueError('Stale parent at commit')
                    inventory = json.loads((folder / 'validation.json').read_text())
                    revision = file_revision(candidate)
                    receipt = {'status': 'candidate_committed', 'scene': str(candidate),
                               'revision': revision, 'evidence': str(folder / 'evidence'),
                               'strong_takeover': strong, 'final_accepted': False}
                    save(self.output / 'latest_candidate.json', receipt)
                    self.current, self.revision, self.inventory = candidate, revision, inventory
                    return receipt
                feedback = review.model_dump()
                strong = strong or review.severity == 'critical' or attempt >= 1
            except BudgetExceeded:
                raise
            except Exception as exc:
                feedback = {'error': f'{type(exc).__name__}: {exc}'}
                self.ledger.event('construction_failed', {'task': task.task_id, **feedback})
                strong = strong or attempt >= 1
        return {'status': 'blocked_construction', 'reason': feedback}

    def build_branch(self, task, wave, parent, revision):
        branch = copy.copy(self)
        branch.current, branch.revision = parent, revision
        branch.output = self.output / 'parallel' / f'wave-{wave:04d}' / task.task_id
        branch.output.mkdir(parents=True)
        branch._stage_output = self.output
        branch.evidence = dict(self.evidence)
        branch.results = dict(self.results)
        strong = task.severity == 'critical'
        proposal = branch.call('strong_build' if strong else 'build', Proposal,
                               branch.build_packet(task), self.c.source_images, strong=strong)
        # GPU generation and mutable global assets stay on the serial route.
        if proposal.route == 'hunyuan':
            raise ValueError('GPU generation requires serial construction')
        folder = branch.output / 'candidate'
        candidate, validation = branch.construct(task, proposal, folder, prepare_evidence=False)
        return {'scene': candidate, 'scene_revision': file_revision(candidate), 'validation': validation, 'proposal': proposal,
                'parent': revision, 'strong': strong}

    def merge_branch(self, task, branch, wave):
        # The branch is immutable. Rebase via a trusted object import, never by relabeling a stale proposal.
        validate_scope(branch['proposal'], task, branch['parent'])
        if file_revision(branch['scene']) != branch['scene_revision']:
            raise ValueError('Parallel candidate changed before merge')
        folder = self.output / 'candidates' / f'{task.task_id}-wave-{wave:04d}-merge'
        folder.mkdir(parents=True)
        shutil.copy2(self.current, folder / 'input.blend')
        shutil.copy2(branch['scene'], folder / 'candidate.blend')
        revision = file_revision(self.current)
        if revision != self.revision:
            raise ValueError('Canonical scene changed before merge')
        proposal = branch['proposal'].model_copy(update={'parent_revision': revision})
        save(folder / 'request.json', {'proposal': proposal.model_dump(), 'merge_only': True,
             'expected_objects': branch['validation']['objects'], 'branch_parent_revision': branch['parent']})
        with self.compute('blender_merge', self.c.timeout_s):
            execute(self.c, folder, HERE / 'blender_worker.py', folder / 'request.json')
        save(folder / 'verify.json', {'proposal': proposal.model_dump(), 'verify_only': True})
        with self.compute('blender_verify', self.c.timeout_s):
            execute(self.c, folder, HERE / 'blender_worker.py', folder / 'verify.json')
        candidate = folder / 'scene.blend'
        validation = json.loads((folder / 'validation.json').read_text())
        if not validation['ok']:
            raise ValueError('Merged candidate failed validation')
        from .artifacts import record_candidate
        record_candidate(folder, candidate, revision, task)
        request = self.bridge('prepare', candidate, folder / 'evidence')
        request['candidate_objects'] = validation['objects']
        review = self.critic(task, request, strong=branch['strong'])
        save(folder / 'local-review.json', review.model_dump())
        if review.verdict != 'pass':
            return self.work(task, feedback=review.model_dump(), force_strong=review.severity == 'critical', start_attempt=1)
        if file_revision(self.current) != revision:
            raise ValueError('Canonical scene changed during merge review')
        receipt = {'status': 'candidate_committed', 'scene': str(candidate), 'revision': file_revision(candidate),
                   'evidence': str(folder / 'evidence'), 'strong_takeover': branch['strong'],
                   'branch_parent_revision': branch['parent'], 'final_accepted': False}
        save(self.output / 'latest_candidate.json', receipt)
        self.current, self.revision, self.inventory = candidate, receipt['revision'], validation
        return receipt

    def schedule(self, plan):
        plan, added = dependency_plan(plan)
        save(self.output / 'dependency-plan.json', {'plan': plan.model_dump(), 'added_edges': added,
             'build_limit': self.capacity['selected']['builds'],
             'policy': 'Disjoint object branches; serial scoped merge, fresh review and commit.'})
        wave = 0
        while len(self.results) < len(plan.tasks):
            for task in plan.tasks:
                if task.task_id not in self.results and any(
                        dep in self.results and self.results[dep]['status'] != 'candidate_committed'
                        for dep in task.depends_on):
                    self.results[task.task_id] = {'status': 'blocked_dependency'}
            ready = ready_tasks(plan, self.results, self.capacity['selected']['builds'])
            if not ready:
                save(self.output / 'tasks.json', self.results)
                if len(self.results) != len(plan.tasks):
                    raise ValueError('Dependency scheduler has no runnable tasks')
                break
            wave += 1
            save(self.output / 'progress.json', {'phase': 'building', 'wave': wave,
                 'active_tasks': [t.task_id for t in ready], 'completed': len(self.results),
                 'total': len(plan.tasks), 'limits': self.capacity['selected']})
            if len(ready) == 1:
                task = ready[0]
                self.results[task.task_id] = self.work(task)
            else:
                parent, revision = self.current, self.revision
                with ThreadPoolExecutor(max_workers=len(ready)) as pool:
                    futures = {}
                    for task in ready:
                        snapshot = copy.copy(self)
                        snapshot.results = dict(self.results)
                        futures[task.task_id] = pool.submit(snapshot.build_branch, task, wave, parent, revision)
                    # Consume in plan order for deterministic commits; branches only read the snapshot.
                    for task in ready:
                        try:
                            branch = futures[task.task_id].result()
                            save(self.output / 'progress.json', {'phase': 'merging_and_reviewing',
                                 'wave': wave, 'active_tasks': [task.task_id],
                                 'completed': len(self.results), 'total': len(plan.tasks)})
                            self.results[task.task_id] = self.merge_branch(task, branch, wave)
                        except BudgetExceeded:
                            raise
                        except Exception as exc:
                            self.ledger.event('parallel_fallback', {'task': task.task_id, 'error': str(exc)})
                            self.results[task.task_id] = self.work(task, feedback={'parallel_error': str(exc)}, start_attempt=1)
                        save(self.output / 'tasks.json', self.results)
            save(self.output / 'tasks.json', self.results)
        save(self.output / 'progress.json', {'phase': 'construction_finished', 'results': self.results})

    def run(self, *, cuda=False):
        status, error = 'blocked_preparation' if self.c.preparation else 'blocked_construction', None
        try:
            with self.compute('capacity_calibration', self.c.timeout_s):
                self.capacity = calibrate(self.c, self.output / 'capacity')
            self._model_slots = threading.BoundedSemaphore(self.capacity['selected']['model_calls'])
            if self.c.preparation:
                self.prepare()
            status = 'blocked_construction'
            self.initialize_construction()
            self.reference = reference_summary(layout(self.c, self.current))
            self.reference['review_limitations'] = self.reference_limitations
            save(self.output / 'reference-summary.json', self.reference)
            self.inspect()
            plan = self.call('plan', Plan, {'instruction': self.c.instruction,
                'instruction_detail': 'Return ordered construction tasks with stable semantic IDs. '
                'Decide the minimal true dependency DAG, explaining dependencies in dependency_reason. '
                'List reads_object_ids for supports, placement context and shared materials. '
                'Mark parallel_safe=true only for disjoint object-local geometry with baked modifiers '
                'and no global world/render/camera/shared-material edits or external parents/constraints. '
                'Shell, lighting and global material changes are exclusive (parallel_safe=false). '
                'Avoid artificial chains between independent furnishings. Do not create a final-review '
                'construction task: the scheduler always performs independent final review itself. '
                'Use critical severity to take over seriously wrong architecture/major geometry immediately. '
                'Cover shell, openings, major furniture and required visible details.',
                'parent_revision': self.revision, 'current_inventory': self.inventory,
                'reference_geometry': self.reference, 'budget': self.ledger.summary(),
                'max_strong_takeovers': self.c.max_takeovers,
                'local_stage_reservation_usd': self.c.compute_reservation_usd,
                'codex_budget_exempt': self.c.codex_budget_exempt,
                'local_compute_budget_exempt': self.c.local_compute_budget_exempt,
                'planning_budget_guidance': 'Group related construction work into bounded tasks. '
                    'Codex calls are excluded from the dollar cap when codex_budget_exempt is true. Paid API calls count; local execution is excluded when local_compute_budget_exempt is true. '
                    'Budget exclusions do not mean actual costs are known.'},
                self.c.source_images, strong=True)
            save(self.output / 'plan.json', plan.model_dump())
            self.schedule(plan)
            if all(r['status'] == 'candidate_committed' for r in self.results.values()):
                # Regenerate whole-scene evidence after all local commits; fresh independent gate.
                self.bridge('prepare', self.current, self.output / 'final-evidence')
                key = self.ledger.reserve('final_judge', self.c.judge.call_reservation_usd,
                                          budget_exempt=self.c.exempt(self.c.judge), category='codex_cli')
                try:
                    result = self.bridge('review', self.current, self.output / 'final-evidence')
                finally:
                    self.ledger.settle(key, None, {'backend': 'codex', 'native_aha_gate': True})
                if result['verdict'] == 'invalid_review':
                    raise InvalidFinalReview(result['error'])
                if result['verdict'] != 'accepted' and self.takeovers < self.c.max_takeovers:
                    # Final major failures may go straight to expensive reconstruction.
                    ids = sorted({oid for t in plan.tasks for oid in t.object_ids})
                    if len(ids) <= 32:
                        repair = Work(task_id='final_repair', object_ids=ids, severity='critical',
                            instruction='Repair the independent final judge findings using source evidence.')
                        self.results[repair.task_id] = self.work(repair, result['visual_review'], force_strong=True)
                        save(self.output / 'tasks.json', self.results)
                        if self.results[repair.task_id]['status'] == 'candidate_committed':
                            self.bridge('prepare', self.current, self.output / 'repaired-final-evidence')
                            key = self.ledger.reserve('final_judge_after_takeover', self.c.judge.call_reservation_usd,
                                          budget_exempt=self.c.exempt(self.c.judge), category='codex_cli')
                            try:
                                result = self.bridge('review', self.current, self.output / 'repaired-final-evidence')
                            finally:
                                self.ledger.settle(key, None, {'backend': 'codex', 'native_aha_gate': True})
                            if result['verdict'] == 'invalid_review':
                                raise InvalidFinalReview(result['error'])
                status = 'layout_validated' if result['verdict'] == 'accepted' else 'needs_repair'
                evidence_dir = (self.output / 'repaired-final-evidence' if
                    (self.output / 'repaired-final-evidence').exists() else self.output / 'final-evidence')
                save(self.output / 'handoff.json', {'scene': str(self.current),
                     'evidence': str(evidence_dir), 'layout_status': status,
                     'delivery_accepted': False,
                     'next_step': 'Bind this layout to the AHA task acceptance/delivery workflow.'})
        except InvalidFinalReview as exc:
            status, error = 'blocked_review', str(exc)
        except BudgetExceeded as exc:
            status, error = 'incomplete_budget', str(exc)
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        result = {'architecture': 'aha', 'status': status, 'error': error,
            'scene': str(self.current) if self.current else None, 'results': self.results,
            'takeovers': self.takeovers, 'generations': self.generations,
            'cost': self.ledger.summary(),
            'wall_seconds': self.previous_wall_seconds + time.monotonic()-self.started,
            'stages': self.stages, 'local_compute_cost_complete': self.c.host_hourly_usd is not None,
            'delivery_accepted': False}
        from .artifacts import safe_export
        result['output'] = safe_export(self)
        save(self.output / 'report.json', result)
        save(self.output / 'progress.json', {'phase': status, 'error': error, 'results': self.results})
        self._job_lock.close()
        return result
