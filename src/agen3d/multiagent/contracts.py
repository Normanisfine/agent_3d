"""Strict wire contracts shared by CLI agents, VLMs, tools and scheduler."""
from typing import Literal

from pydantic import Field, model_validator

from agen3d.schema import Record

Role = Literal["planner", "inventory", "geometry", "asset", "critic", "judge", "physics"]


class Task(Record):
    task_id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    role: Role
    instruction: str = Field(min_length=1, max_length=12000)
    object_ids: list[str] = Field(default_factory=list, max_length=32)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)
    depends_on: list[str] = Field(default_factory=list)
    max_turns: int = Field(default=4, ge=1, le=12)


class ToolCall(Record):
    name: str
    arguments: dict = Field(default_factory=dict)


class Decision(Record):
    status: Literal["tool", "done", "pass", "repair", "abstain"]
    summary: str = Field(max_length=6000)
    calls: list[ToolCall] = Field(default_factory=list, max_length=4)
    tasks: list[Task] = Field(default_factory=list, max_length=32)
    evidence_used: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def action_shape(self):
        if (self.status == "tool") != bool(self.calls):
            raise ValueError("Only status=tool carries calls; a tool turn needs at least one call")
        if self.status == "tool" and self.tasks:
            raise ValueError("Return a plan on a final decision, not alongside tools")
        return self


class Evidence(Record):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: Literal["image", "json", "mask", "depth", "mesh"]
    description: str


class ModelSpec(Record):
    backend: Literal["openrouter", "openai_compatible", "codex", "claude", "mock"]
    model: str | None = None
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max", "ultra"] | None = None
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_env: str = "OPENROUTER_API_KEY"
    provider: str | None = None
    response_mode: Literal['schema', 'json', 'text'] = 'schema'
    temperature: float | None = Field(default=0., ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    top_k: int | None = Field(default=None, ge=0)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    repetition_penalty: float | None = Field(default=None, gt=0, le=2)
    seed: int | None = None
    max_output_tokens: int = Field(default=1800, ge=64, le=16000)
    timeout_s: int = Field(default=180, ge=1, le=1800)
    # Operator-defined conservative ceilings, NOT claims about provider prices.
    call_reservation_usd: float = Field(default=0.05, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def needs_model(self):
        if self.reasoning_effort is not None and self.backend != "codex":
            raise ValueError("reasoning_effort is currently supported only by the Codex adapter")
        if self.backend in {"openrouter", "openai_compatible"} and not self.model:
            raise ValueError("API backends need an explicit model ID")
        return self


class ServiceSpec(Record):
    python: str
    repo: str
    checkpoint: str | None = None
    timeout_s: int = Field(default=600, ge=1, le=3600)
    reservation_usd: float = Field(gt=0, allow_inf_nan=False)


class RunConfig(Record):
    variant: Literal["v1", "v2", "v3"] = "v1"
    scene: str
    evidence_root: str
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    output: str
    models: dict[str, ModelSpec]
    services: dict[Literal["pi3x", "sam3", "sam3d", "hunyuan", "hispatial"], ServiceSpec] = Field(default_factory=dict)
    budget_usd: float = Field(gt=0, allow_inf_nan=False)
    judge_reserve_usd: float = Field(gt=0, allow_inf_nan=False)
    max_tasks: int = Field(default=24, ge=1, le=100)
    max_strong_escalations: int = Field(default=2, ge=0, le=10)
    max_generations: int = Field(default=2, ge=0, le=20)
    source: str = "Reconstruct/refine the supplied canonical scene using only attached evidence."
    tasks: list[Task] = Field(default_factory=list)

    @model_validator(mode="after")
    def model_aliases(self):
        if not {"planner", "judge", "cheap"} <= self.models.keys():
            raise ValueError("models must define planner, judge, cheap")
        if self.judge_reserve_usd >= self.budget_usd:
            raise ValueError("Final judge reserve must be below total budget")
        if self.judge_reserve_usd < self.models["judge"].call_reservation_usd:
            raise ValueError("Reserve must fund at least one final judge call")
        if self.variant == "v3" and "medium" not in self.models:
            raise ValueError("V3 requires a medium model alias")
        return self
