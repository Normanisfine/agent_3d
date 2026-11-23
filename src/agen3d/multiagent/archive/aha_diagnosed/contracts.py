"""Source-derived instance intent and locally enforceable review coverage."""
from typing import Literal
from pydantic import Field, model_validator
from agen3d.schema import Record
from agen3d.multiagent.aha.contracts import Plan, Review


class Instance(Record):
    instance_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    semantic_class: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=1500)
    kind: Literal['physical_object', 'structure'] = 'physical_object'
    disposition: Literal['build', 'preserve', 'exclude']
    source_image_ids: list[str] = Field(min_length=1)
    support_id: str | None = None
    exclusion_reason: str | None = None
    # This is an explicit planner assertion, not proof of physical identity.
    physical_instance_count: Literal[1] = 1

    @model_validator(mode='after')
    def consistent(self):
        if len(self.source_image_ids) != len(set(self.source_image_ids)):
            raise ValueError('Duplicate source evidence')
        if self.disposition == 'exclude' and not self.exclusion_reason:
            raise ValueError('Excluded observed instances require a reason')
        if self.disposition != 'exclude' and self.exclusion_reason:
            raise ValueError('Only excluded instances may have an exclusion reason')
        if self.support_id == self.instance_id:
            raise ValueError('Instance cannot support itself')
        return self


class InstancePlan(Plan):
    scope_statement: str = Field(min_length=1)
    instances: list[Instance] = Field(min_length=1, max_length=128)
    uncertainties: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def instance_coverage(self):
        by_id = {i.instance_id:i for i in self.instances}
        if len(by_id) != len(self.instances):
            raise ValueError('Instance IDs must be unique')
        writes = {oid for task in self.tasks for oid in task.object_ids}
        required = {i.instance_id for i in self.instances if i.disposition == 'build'}
        if writes != required:
            raise ValueError('Every build instance must be tasked; tasks may only write build instances')
        for instance in self.instances:
            if instance.support_id and (instance.support_id not in by_id or
                    by_id[instance.support_id].disposition == 'exclude'):
                raise ValueError('Support must be a retained declared instance')
        return self


def validate_plan(plan, source_images, inventory):
    by_id={i.instance_id:i for i in plan.instances}
    existing=set(inventory.get('objects',{}))
    if not existing <= set(by_id):
        raise ValueError('Plan must account for every existing semantic root')
    for instance in plan.instances:
        if not set(instance.source_image_ids) <= set(source_images):
            raise ValueError('Instance cites an unavailable source image')
        if instance.disposition == 'preserve' and instance.instance_id not in existing:
            raise ValueError('Cannot preserve an absent instance')
        if instance.disposition == 'exclude' and instance.instance_id in existing:
            raise ValueError('Existing roots cannot be silently excluded or deleted')
    # Correct support read sets feed the existing conflict/dependency scheduler.
    tasks=[]
    for task in plan.tasks:
        if not set(task.reads_object_ids) <= set(by_id):
            raise ValueError('Undeclared read dependency')
        support={by_id[oid].support_id for oid in task.object_ids} - {None}
        tasks.append(task.model_copy(update={'reads_object_ids':sorted(
            (set(task.reads_object_ids)|support)-set(task.object_ids)), 'severity':'critical'}))
    # A read of a future build would silently use absent/stale support. Require
    # support construction before consumers rather than inventing a reversed DAG.
    built=set(existing)
    for task in tasks:
        if not set(task.reads_object_ids) <= built:
            raise ValueError('Support/context must exist or be built earlier in the plan')
        built.update(task.object_ids)
    return plan.model_copy(update={'tasks':tasks})


class ImageObservation(Record):
    image_id: str
    observation: str = Field(min_length=12, max_length=1500)

    @model_validator(mode='after')
    def substantive_text(self):
        if len(self.observation.strip()) < 12:
            raise ValueError('Blank or placeholder observation')
        return self


class CoveredReview(Review):
    image_observations: list[ImageObservation] = Field(min_length=1)

    @model_validator(mode='after')
    def coverage(self):
        ids=[row.image_id for row in self.image_observations]
        if len(ids)!=len(set(ids)) or set(ids)!=set(self.reviewed_images):
            raise ValueError('Each reviewed image requires exactly one concrete observation')
        return self
