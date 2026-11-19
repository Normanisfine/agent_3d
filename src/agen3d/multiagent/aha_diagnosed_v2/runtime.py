"""Opt-in extension of original AHA; no box-only construction restriction."""
import copy
import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..aha.runtime import Runtime as OriginalRuntime, digest, validate_scope
from ..aha.contracts import Plan, Review
from .scheduling import dependency_plan, ready_tasks, lower_plan
from ..aha.isolation import execute

HERE = Path(__file__).parent
from ..store import BudgetExceeded, save
from .contracts import InstancePlan, CoveredReview, validate_plan
from .evidence import packets, review_key, POLICY_VERSION


class EvidenceReviewError(ValueError):
    """Invalid evidence/reviewer transport must not cause geometric reconstruction."""


class WriteScopeError(ValueError):
    """A permission contract failure requires replanning, not identical retries."""


class Runtime(OriginalRuntime):
    def __init__(self,*args,max_review_images=8,cheap_triage=False,**kwargs):
        if not 3 <= max_review_images <= 16:
            raise ValueError('max_review_images must be between 3 and 16')
        super().__init__(*args,**kwargs)
        self.max_review_images=max_review_images
        self.cheap_triage=cheap_triage
        self.instances={}
        self._scope_by_task={}
        self._review_lock=threading.Lock()
        self._review_locks={}
        self._triaged_tasks=set()
        self._review_cache_root=self.output/'covered-reviews'
        self._review_cache_root.mkdir()
        save(self.output/'variant.json',{'variant':'aha_diagnosed_v2','policy':POLICY_VERSION,
            'construction':'strong expressive Blender; one ID per physical instance',
            'cheap_triage':cheap_triage,'max_review_images':max_review_images,
            'native_final_gate':'unchanged; whole-room review still required'})

    def call(self,role,schema,packet,images,*,strong=False,retry=False):
        if role=='plan':
            request={**packet,'instance_policy':
                'Return InstancePlan. Enumerate distinct observed physical instances before tasks. '
                'Use separate IDs for each table, mirror, vase, pillow, and other requested accessory. '
                'A multipart object has ONE root; multiple physical objects must not share one root. '
                'Do not group all decor, doors, windows or repeated category instances under one ID. '
                'A structural room shell may remain one structure. Declare source image IDs and supports. '
                'Account for every existing root. Build all requested visible instances; declare exclusions '
                'with reasons rather than silently reducing scope. Preserve only existing correct roots. '
                'If an existing root wrongly groups several physical instances, report that uncertainty '
                'and plan an explicit migration; do not claim it is already instance-complete. '
                'Existing roots that need cuts or other changes must have disposition edit, and appear in '
                'task.edit_object_ids with edit_reason. Reads and preserve NEVER authorize writes. '
                'task.object_ids lists construction targets; edit_object_ids lists additional existing roots. '
                'Supports/context must exist or be built before consumers. Construction uses the strong model.',
                'planning_budget_guidance':'Every construction task uses the strong model and existing reservations. '
                    'Keep tasks local and minimize real dependencies; no generic box-only recipe restriction.'}
            plan=super().call(role,InstancePlan,request,images,strong=True,retry=retry)
            plan=validate_plan(plan,images,self.inventory)
            self.instances={i.instance_id:i for i in plan.instances}
            save(self.output/'instance-plan.json',plan.model_dump())
            self._save_instance_status()
            return plan
        return super().call(role,schema,packet,images,strong=strong,retry=retry)

    def bridge(self,action,scene,folder):
        try:
            return super().bridge(action,scene,folder)
        except BudgetExceeded:
            raise
        except Exception as exc:
            if action=='prepare':
                raise EvidenceReviewError('Evidence generation failed; preserve geometry: '+str(exc)) from exc
            raise

    def _save_instance_status(self):
        objects=self.inventory.get('objects',{})
        save(self.output/'instance-status.json',{
            oid:{'intent':i.disposition,'present':oid in objects,'source_image_ids':i.source_image_ids,
                 'tasks':{t:r['status'] for t,r in self.results.items()
                          if oid in getattr(self,'_task_objects',{}).get(t,[])},
                 'exclusion_reason':i.exclusion_reason,
                 'presence_is_visual_acceptance':False}
            for oid,i in self.instances.items()})

    def build_packet(self,task,feedback=None):
        packet=super().build_packet(task,feedback)
        ids=set(task.object_ids+task.reads_object_ids)
        if task.parallel_safe:
            packet['current_inventory']['objects']={k:v for k,v in packet['current_inventory']['objects'].items() if k in ids}
        packet.pop('prior_tasks',None)
        packet['instance_contract']={oid:self.instances[oid].model_dump() for oid in ids if oid in self.instances}
        packet['identity_rule']='One root per declared physical instance; never merge repeated objects by category. Preserve source-derived shape, not merely bounding boxes.'
        scope=getattr(self,'_scope_by_task',{}).get(task.task_id,
            {'create_object_ids':task.object_ids,'edit_object_ids':[],'edit_reason':''})
        packet['write_scope']={**scope,'authorized_write_ids':task.object_ids,
            'instruction':'Proposal object_ids must equal authorized_write_ids. Blender global object_ids '
                'contains only create_object_ids; editable_object_ids contains existing roots to modify. '
                'Preserve all other roots and cameras. Do not delete existing edit roots.'}
        return packet

    def construct(self, task, proposal, folder, *, prepare_evidence=True):
        validate_scope(proposal, task, self.revision)
        if digest(self.current) != self.revision:
            raise ValueError('Canonical scene changed outside the committer')
        if proposal.route == 'abstain':
            raise ValueError('Worker abstained: ' + proposal.reason)
        if proposal.route == 'asset' and proposal.asset_id not in self.catalog:
            raise ValueError('Unregistered collection asset')
        if proposal.route == 'code':
            compile(proposal.code, '<generated build.py>', 'exec')
        folder.mkdir(parents=True, exist_ok=False)
        shutil.copy2(self.current, folder / 'input.blend')
        scope=getattr(self,'_scope_by_task',{}).get(task.task_id,
            {'create_object_ids':task.object_ids,'edit_object_ids':[]})
        save(folder / 'request.json', {'proposal': proposal.model_dump(), **scope})
        (folder / 'build.py').write_text(proposal.code)
        if proposal.route == 'hunyuan':
            self.generate(proposal, folder)
        try:
            with self.compute('blender_build', self.c.timeout_s):
                execute(self.c, folder, HERE / 'blender_worker.py', folder / 'request.json')
        except Exception as exc:
            diff_path=folder/'scope-diff.json'
            if diff_path.exists():
                diff=json.loads(diff_path.read_text())
                if diff['unauthorized_changed_ids'] or diff['missing_required_ids']:
                    details={k:diff[k] for k in ('allowed_ids','changed_ids','unauthorized_changed_ids','missing_required_ids')}
                    raise WriteScopeError(json.dumps(details)) from exc
            raise
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
        from ..aha.artifacts import record_candidate
        record_candidate(folder, candidate, proposal.parent_revision, task)
        if not prepare_evidence:
            return candidate, validation
        review_request = self.bridge('prepare', candidate, folder / 'evidence')
        review_request['candidate_objects'] = validation['objects']
        return candidate, review_request

    def _covered_call(self,packet,images,*,strong):
        spec=self.c.supervisor if strong else self.c.worker
        key=review_key(packet,images,spec)
        with self._review_lock:
            lock=self._review_locks.setdefault(key,threading.Lock())
        with lock:
            if review_key(packet,images,spec)!=key:
                raise ValueError('Evidence changed while waiting for review cache')
            path=self._review_cache_root/(key+'.json')
            if path.exists():
                receipt=json.loads(path.read_text())
                review=CoveredReview.model_validate(receipt['review'])
                if (receipt['key']!=key or set(review.reviewed_images)!=set(images)
                    or {o.image_id for o in review.image_observations}!=set(images)
                    or review.candidate_revision!=packet['candidate_revision']):
                    raise ValueError('Invalid cached review receipt')
                self.ledger.event('covered_review_cache_hit',{'key':key,'role':'strong' if strong else 'cheap'})
                return review
            review=self.call('covered_strong_review' if strong else 'cheap_triage',CoveredReview,packet,images,strong=strong)
            if (set(review.reviewed_images)!=set(images)
                or {o.image_id for o in review.image_observations}!=set(images)
                or review.candidate_revision!=packet['candidate_revision']):
                raise ValueError('Review observations must use every exact delivered image ID')
            if review_key(packet,images,spec)!=key:
                raise ValueError('Evidence changed during bounded review')
            save(path,{'key':key,'review':review.model_dump(),'model':spec.model_dump(),
                       'reuse_scope':'exact task, revision, image bytes, model and policy only'})
            return review

    def critic(self,task,request,strong=False):
        try:
            return self._critic(task,request,strong)
        except BudgetExceeded:
            raise
        except Exception as exc:
            raise EvidenceReviewError(str(exc)) from exc

    def _critic(self,task,request,strong=False):
        # Build every packet first. One missing image stops before any paid call.
        chunks=packets(task,request,self.instances,self.c.source_images,self.max_review_images)
        self.ledger.event('bounded_review_plan',{'task':task.task_id,
            'candidate_revision':request['candidate_revision'],'batches':len(chunks),
            'max_images':max(len(c['images']) for c in chunks),
            'unique_images':len({i for c in chunks for i in c['images']})})
        with self._review_lock:
            triage=self.cheap_triage and task.task_id not in self._triaged_tasks
            if triage:self._triaged_tasks.add(task.task_id)
        def one(chunk):
            oid=chunk['object_id']
            packet={'candidate_revision':request['candidate_revision'],'object_id':oid,
                'instance':self.instances[oid].model_dump(),'task_instruction':task.instruction,
                'candidate_object':request.get('candidate_objects',{}).get(oid),
                'support_objects':{key:self.inventory.get('objects',{}).get(key)
                                   for key in task.reads_object_ids},
                'batch':chunk['batch'],'required_object_images':chunk['required_object_images'],
                'instruction':'Inspect every attached image and write one concrete image_observations entry '
                    'per exact image ID, plus actionable observations/defects. Compare source silhouette, '
                    'dimensions, orientation and support. Focus images show candidate contours over source '
                    'or approximate reference backgrounds; background holes are not candidate holes. '
                    'Original images are RGB context, not evidence that the candidate contains those objects. '
                    'Do not substitute a reviewed_images list for per-image observations. '
                    'This is a bounded object review, not complete-room or appearance acceptance.'}
            if triage:
                try:
                    cheap=self._covered_call(packet,chunk['images'],strong=False)
                    if cheap.verdict=='repair':
                        return cheap.model_copy(update={'severity':'critical'})
                except BudgetExceeded:
                    raise
                except Exception as exc:
                    self.ledger.event('cheap_triage_invalid',{'task':task.task_id,'error':str(exc)[:1000]})
            return self._covered_call(packet,chunk['images'],strong=True)
        limit=self.capacity['selected']['model_calls']
        with ThreadPoolExecutor(max_workers=min(limit,len(chunks))) as pool:
            reviews=list(pool.map(one,chunks))
        defects=[d for r in reviews for d in r.defects]
        return Review(candidate_revision=request['candidate_revision'],verdict='repair' if defects else 'pass',
            severity='critical' if defects else 'routine',defects=defects,
            observations=[o for r in reviews for o in r.observations],
            reviewed_images=sorted({i for r in reviews for i in r.reviewed_images}))

    def work(self,task,feedback=None,force_strong=False,start_attempt=0):
        if getattr(self,'_defer_repair',False):
            raise ValueError('Defer failed merged candidate repair: '+str(feedback))
        task=task.model_copy(update={'severity':'critical'})
        if force_strong:
            if self.takeovers >= self.c.max_takeovers:
                return {'status':'blocked_construction','reason':'Strong takeover limit'}
            self.takeovers+=1
            self.ledger.event('takeover',{'task':task.task_id,'feedback':feedback,
                                        'parent_revision':self.revision})
        from ..aha.contracts import Proposal
        for attempt in range(start_attempt,3):
            try:
                proposal=self.call('strong_build',Proposal,self.build_packet(task,feedback),
                                   self.c.source_images,strong=True)
                folder=self.output/'candidates'/f'{task.task_id}-{self.sequence:04d}-{attempt}'
                candidate,request=self.construct(task,proposal,folder)
                review=self.critic(task,request,strong=True)
                save(folder/'local-review.json',review.model_dump())
                if review.verdict=='pass':
                    if digest(self.current)!=proposal.parent_revision:
                        raise ValueError('Stale parent at commit')
                    inventory=json.loads((folder/'validation.json').read_text())
                    receipt={'status':'candidate_committed','scene':str(candidate),'revision':digest(candidate),
                        'evidence':str(folder/'evidence'),'strong_takeover':True,'final_accepted':False}
                    save(self.output/'latest_candidate.json',receipt)
                    self.current,self.revision,self.inventory=candidate,receipt['revision'],inventory
                    return receipt
                feedback=review.model_dump()
            except BudgetExceeded:
                raise
            except WriteScopeError as exc:
                return {'status':'blocked_scope','reason':str(exc),'geometry_retry_performed':False}
            except EvidenceReviewError as exc:
                return {'status':'blocked_review','reason':str(exc),'geometry_retry_performed':False}
            except Exception as exc:
                feedback={'error':f'{type(exc).__name__}: {exc}'[:2000]}
                self.ledger.event('construction_failed',{'task':task.task_id,**feedback})
        return {'status':'blocked_construction','reason':feedback}

    def schedule(self,plan):
        plan=validate_plan(plan,self.c.source_images,self.inventory)
        self.instances={i.instance_id:i for i in plan.instances}
        plan,self._scope_by_task=lower_plan(plan)
        self._task_objects={t.task_id:t.object_ids for t in plan.tasks}
        plan,added,ordering=dependency_plan(plan)
        save(self.output/'dependency-plan.json',{'plan':plan.model_dump(),'added_edges':added,
             'policy':'Strong object construction; completion-order scoped merge; bounded covered review'})
        wave=0
        while len(self.results)<len(plan.tasks):
            for task in plan.tasks:
                if task.task_id not in self.results and any(d in self.results and
                    self.results[d]['status']!='candidate_committed' for d in task.depends_on):
                    self.results[task.task_id]={'status':'blocked_dependency'}
            ready=ready_tasks(plan,self.results,self.capacity['selected']['builds'],ordering)
            if not ready:
                if len(self.results)!=len(plan.tasks):raise ValueError('No runnable dependency frontier')
                break
            wave+=1
            save(self.output/'progress.json',{'phase':'building','wave':wave,'active_tasks':[t.task_id for t in ready]})
            if len(ready)==1:
                self.results[ready[0].task_id]=self.work(ready[0])
            else:
                parent,revision=self.current,self.revision
                repairs=[]
                with ThreadPoolExecutor(max_workers=len(ready)) as pool:
                    futures={}
                    for task in ready:
                        snapshot=copy.copy(self)
                        snapshot.results=dict(self.results)
                        futures[pool.submit(snapshot.build_branch,task,wave,parent,revision)]=task
                    for future in as_completed(futures):
                        task=futures[future]
                        try:
                            branch=future.result()
                            self._defer_repair=True
                            try:self.results[task.task_id]=self.merge_branch(task,branch,wave)
                            finally:self._defer_repair=False
                        except BudgetExceeded:raise
                        except WriteScopeError as exc:
                            self.results[task.task_id]={'status':'blocked_scope','reason':str(exc),
                                                       'geometry_retry_performed':False}
                        except EvidenceReviewError as exc:
                            self.results[task.task_id]={'status':'blocked_review','reason':str(exc),
                                                       'geometry_retry_performed':False}
                        except Exception as exc:
                            self.ledger.event('parallel_fallback',{'task':task.task_id,'error':str(exc)[:1000]})
                            repairs.append((task,{'parallel_error':str(exc)[:2000]}))
                        save(self.output/'tasks.json',self.results)
                for task,feedback in repairs:
                    self.results[task.task_id]=self.work(task,feedback,force_strong=True,start_attempt=1)
            save(self.output/'tasks.json',self.results)
            self._save_instance_status()
        self._save_instance_status()
        save(self.output/'tasks.json',self.results)

    def run(self,**kwargs):
        result=super().run(**kwargs)
        result['architecture']='aha_diagnosed_v2'
        if (result.get('error') or '').startswith('EvidenceReviewError:'):
            result['status']='blocked_review'
            progress=json.loads((self.output/'progress.json').read_text())
            save(self.output/'progress.json',{**progress,'phase':'blocked_review'})
        if self.instances:self._save_instance_status()
        result['excluded_instances']=[i.model_dump() for i in self.instances.values() if i.disposition=='exclude']
        result['instance_plan']=str(self.output/'instance-plan.json') if self.instances else None
        result['limitations']=['Manifest assertions do not prove source inventory completeness.',
            'Final native whole-room review and evidence generation remain unchanged.',
            'Cheap triage can cause false rejection; strong review is required for local passes.',
            'No demonstrated full-room quality/cost gain yet.']
        save(self.output/'report.json',result)
        return result
