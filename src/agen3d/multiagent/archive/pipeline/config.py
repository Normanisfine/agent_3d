"""Operator configuration; dataset labels are not part of any model request."""
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from agen3d.schema import Record
from agen3d.multiagent.contracts import ModelSpec, ServiceSpec
from agen3d.multiagent.resources import resolve_resource, interpreter_path, load_env as load_env


class PipelineConfig(Record):
    variant: Literal["v1", "v2", "v3"] = "v1"
    input: str
    scene_id: str
    dataset_kind: Literal["ai2thor", "ca1m", "generic"] = "generic"
    evaluation_dataset: str | None = None
    output: str
    aha_repo: str
    blender: str
    frames: int = Field(default=16, ge=4, le=32)
    segmentation_views: int = Field(default=8, ge=2, le=16)
    max_categories: int = Field(default=32, ge=1, le=80)
    max_objects: int = Field(default=100, ge=1, le=200)
    repair_rounds: int = Field(default=1, ge=0, le=3)
    budget_usd: float = Field(default=3, gt=0)
    judge_reserve_usd: float = Field(default=.75, gt=0)
    gpu_hourly_usd: float | None = Field(default=None, ge=0)
    cpu_hourly_usd: float | None = Field(default=None, ge=0)
    models: dict[str, ModelSpec]
    services: dict[str, ServiceSpec]

    @model_validator(mode="after")
    def required(self):
        if not {"planner", "judge", "cheap"} <= self.models.keys():
            raise ValueError("Planner, judge and cheap aliases required")
        if not {"pi3x", "sam3"} <= self.services.keys():
            raise ValueError("Pi3X and SAM 3 services required")
        if self.segmentation_views > self.frames:
            raise ValueError("Segmentation views cannot exceed selected frames")
        return self


def load(path):
    path = Path(path).resolve()
    config = PipelineConfig.model_validate_json(path.read_text())
    for field in ("input", "evaluation_dataset", "output", "aha_repo", "blender"):
        value = getattr(config, field)
        if value is not None:
            setattr(config, field, str((path.parent / value).resolve()))
    for service in config.services.values():
        service.repo = resolve_resource(service.repo, "repos") or str((path.parent / service.repo).resolve())
        service.python = resolve_resource(service.python, "runtimes") or interpreter_path(path.parent, service.python)
    return config
