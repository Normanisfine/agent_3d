"""Model and service configuration shared by the room controllers."""
from typing import Literal

from pydantic import Field, model_validator
from agen3d.schema import Record


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


def __getattr__(name):
    if name in {"Decision", "Evidence", "Role", "RunConfig", "Task", "ToolCall"}:
        from .archive import contracts
        return getattr(contracts, name)
    raise AttributeError(name)
