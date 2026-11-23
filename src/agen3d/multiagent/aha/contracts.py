"""Typed construction outputs: a prose completion cannot mutate a scene."""
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from agen3d.schema import Record
from ..contracts import ModelSpec, ServiceSpec


class Work(Record):
    task_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    object_ids: list[str] = Field(min_length=1, max_length=32)
    instruction: str = Field(min_length=1, max_length=12000)
    depends_on: list[str] = Field(default_factory=list)
    severity: Literal['routine', 'critical'] = 'routine'
    parallel_safe: bool = Field(default=False, description='True only for independent object-local changes; global scene changes are exclusive.')
    reads_object_ids: list[str] = Field(default_factory=list, description='Existing objects used for support, placement or shared material context.')
    dependency_reason: str = ''


class Plan(Record):
    summary: str
    tasks: list[Work] = Field(min_length=1, max_length=32)

    @model_validator(mode='after')
    def dag(self):
        seen = set()
        for task in self.tasks:
            if task.task_id in seen or not set(task.depends_on) <= seen:
                raise ValueError('Tasks must have unique IDs and topologically ordered dependencies')
            seen.add(task.task_id)
        return self


class Proposal(Record):
    parent_revision: str
    object_ids: list[str] = Field(min_length=1)
    route: Literal['code', 'asset', 'hunyuan', 'abstain']
    reason: str = Field(min_length=1)
    code: str = Field(default='', max_length=100000)
    asset_id: str | None = None
    image_id: str | None = None
    mask_id: str | None = None
    # A generated mesh is placed from normalized local bounds, never treated as metric truth.
    location: tuple[float, float, float] = (0., 0., 0.)
    dimensions: tuple[float, float, float] = (1., 1., 1.)
    rotation_z: float = 0.
    semantic_class: str = 'furniture/object'

    @model_validator(mode='after')
    def required(self):
        import math
        if not all(math.isfinite(x) for x in (*self.location, *self.dimensions, self.rotation_z)):
            raise ValueError('Transforms must be finite')
        if min(self.dimensions) <= 0:
            raise ValueError('Dimensions must be positive')
        if self.route == 'code' and not self.code.strip():
            raise ValueError('Code route requires an executable program')
        if self.route == 'asset' and not self.asset_id:
            raise ValueError('Asset route requires a catalog ID')
        if self.route == 'hunyuan' and (not self.image_id or not self.mask_id):
            raise ValueError('Hunyuan requires registered image and mask IDs')
        if self.route in {'asset', 'hunyuan'} and len(self.object_ids) != 1:
            raise ValueError('Asset/generation tasks replace exactly one semantic root')
        return self


class Review(Record):
    candidate_revision: str
    verdict: Literal['pass', 'repair']
    severity: Literal['routine', 'critical']
    observations: list[str] = Field(min_length=1)
    defects: list[str]
    reviewed_images: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def no_false_pass(self):
        if self.verdict == 'pass' and self.defects:
            raise ValueError('Unresolved defects cannot pass')
        if self.verdict == 'repair' and not self.defects:
            raise ValueError('Repair needs an actionable defect')
        return self


class ReferenceReview(Review):
    defects: list[str] = Field(description='Blocking problems requiring reference repair before construction. '
                              'Must be empty for verdict=pass; nonempty for verdict=repair.')
    limitations: list[str] = Field(default_factory=list, description='Non-blocking uncertainties or '
                                  'approximate reference artifacts to carry into construction.')


class Preparation(Record):
    input: str
    timeout_s: int = Field(default=3600, ge=1, le=14400)
    reservation_usd: float = Field(default=.5, gt=0, allow_inf_nan=False)
    num_frames: Literal[32, 64] = 32
    pixel_limit: int = Field(default=255000, ge=10000, le=1000000)


class Parallelism(Record):
    enabled: bool = True
    max_builds: int = Field(default=4, ge=1, le=8)
    max_model_calls: int = Field(default=4, ge=1, le=16)
    memory_per_build_gib: float = Field(default=4., ge=1, le=64)
    benchmark: bool = True


class Config(Record):
    architecture: Literal['aha'] = 'aha'
    parallelism: Parallelism = Field(default_factory=Parallelism)
    aha_repo: str
    blender: str
    python: str
    source_scene: str | None = None
    layout_spec: str | None = None
    preparation: Preparation | None = None
    output: str
    source_images: dict[str, str] = Field(default_factory=dict)
    masks: dict[str, str] = Field(default_factory=dict)
    supervisor: ModelSpec
    worker: ModelSpec
    judge: ModelSpec
    hunyuan: ServiceSpec | None = None
    codex_budget_exempt: bool = True
    local_compute_budget_exempt: bool = True
    budget_usd: float = Field(default=5., gt=0, allow_inf_nan=False)
    judge_reserve_usd: float = Field(default=1., gt=0, allow_inf_nan=False)
    repair_reserve_usd: float = Field(default=1., gt=0, allow_inf_nan=False)
    max_takeovers: int = Field(default=3, ge=1, le=20)
    max_generations: int = Field(default=2, ge=0, le=20)
    timeout_s: int = Field(default=1200, ge=1, le=7200)
    host_hourly_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    compute_reservation_usd: float = Field(default=.1, gt=0, allow_inf_nan=False)
    instruction: str = 'Reconstruct the room faithfully using the supplied source evidence.'

    def exempt(self, spec):
        return self.codex_budget_exempt and spec.backend == 'codex'

    @property
    def judge_holdback(self):
        return 0. if self.exempt(self.judge) else self.judge_reserve_usd

    @property
    def repair_holdback(self):
        return 0. if self.exempt(self.supervisor) else self.repair_reserve_usd

    @model_validator(mode='after')
    def budgets(self):
        if self.preparation:
            if self.source_scene or self.layout_spec or self.source_images or self.masks:
                raise ValueError('Preparation generates scene/layout/evidence; do not mix prepared inputs')
        elif not (self.source_scene and self.layout_spec and self.source_images):
            raise ValueError('Supply preparation.input or complete prepared construction inputs')
        if self.judge.backend != 'codex':
            raise ValueError('AHA final gate currently requires Codex; Claude may supervise/build')
        if self.supervisor.backend not in {'codex', 'claude', 'mock'}:
            raise ValueError('Supervisor must use Codex or Claude')
        if self.judge_holdback < self.judge.call_reservation_usd and not self.exempt(self.judge):
            raise ValueError('Judge reserve must fund final review')
        if self.repair_holdback < self.supervisor.call_reservation_usd and not self.exempt(self.supervisor):
            raise ValueError('Repair reserve must fund a takeover')
        if self.judge_holdback + self.repair_holdback >= self.budget_usd:
            raise ValueError('Reserves leave no working budget')
        if set(self.source_images) & set(self.masks):
            raise ValueError('Image and mask evidence IDs must be distinct')
        return self


def load(path, *, room_input=None, output=None):
    path = Path(path).resolve()
    c = Config.model_validate_json(path.read_text())
    for name in ('aha_repo', 'blender', 'python', 'source_scene', 'layout_spec', 'output'):
        value = getattr(c, name)
        if value:
            # Resolving a virtualenv interpreter symlink bypasses pyvenv.cfg.
            resolved = os.path.abspath(path.parent / value) if name == 'python' else str((path.parent / value).resolve())
            setattr(c, name, resolved)
    if output is not None:
        c.output = str(Path(output).resolve())
    if room_input is not None:
        if c.preparation is None:
            raise ValueError('--input requires a video preparation config')
        c.preparation.input = str(Path(room_input).resolve())
    elif c.preparation:
        c.preparation.input = str((path.parent / c.preparation.input).resolve())
    for mapping in (c.source_images, c.masks):
        for key, value in mapping.items():
            mapping[key] = str((path.parent / value).resolve())
    if c.hunyuan:
        for name in ('python', 'repo'):
            value = path.parent / getattr(c.hunyuan, name)
            setattr(c.hunyuan, name, os.path.abspath(value) if name == 'python' else str(value.resolve()))
    return c


def layout(c, scene):
    spec_path = Path(c.layout_spec)
    spec = json.loads(spec_path.read_text())
    for key in ('reference', 'cameras', 'inputs', 'config', 'source_video', 'camera_cache',
                'reference_manifest', 'inputs_metadata', 'scale_provenance'):
        if spec.get(key):
            spec[key] = str((spec_path.parent / spec[key]).resolve())
    spec['source_scene'] = str(Path(scene).resolve())
    return spec
