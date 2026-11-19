"""Budget gates use caller-supplied dated prices; unknown costs are never zero."""
from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class Usage:
    step: str
    model: str
    input_tokens: int
    output_tokens: int
    gpu_seconds: float
    wall_seconds: float
    usd: float
    pricing_date: str
    retry: bool = False

    def __post_init__(self):
        for value in (self.input_tokens, self.output_tokens, self.gpu_seconds,
                      self.wall_seconds, self.usd):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Usage and cost must be finite and nonnegative")
        if not self.pricing_date:
            raise ValueError("Dated pricing assumptions required")


@dataclass
class CostTracker:
    budget_usd: float
    events: list[Usage] = field(default_factory=list)

    def __post_init__(self):
        if not math.isfinite(self.budget_usd) or self.budget_usd < 0:
            raise ValueError("Invalid budget")

    @property
    def spent(self):
        return sum(event.usd for event in self.events)

    def affordable(self, upper_bound_usd):
        # Use a conservative maximum charge, not the average observed call cost.
        # A future provider must cap output tokens and reserve this budget before
        # submitting work. This synchronous ledger is not a concurrent scheduler.
        return (math.isfinite(upper_bound_usd) and upper_bound_usd >= 0
                and self.spent + upper_bound_usd <= self.budget_usd)

    def record(self, usage):
        # Record actual overages too; never erase a charged failure.
        self.events.append(usage)


def route(confidence, failed_attempts, tracker, open_upper_bound, strong_upper_bound,
          allow_escalation=True):
    # Thresholds are pilot policy choices. Calibrate on development data before
    # making claims about optimal routing or treating confidence as probability.
    if not 0 <= confidence <= 1 or failed_attempts < 0:
        raise ValueError("Invalid routing evidence")
    if confidence >= .85 and failed_attempts == 0:
        return "deterministic"
    if allow_escalation and (confidence < .4 or failed_attempts >= 2):
        return "strong" if tracker.affordable(strong_upper_bound) else "stop"
    return "open" if tracker.affordable(open_upper_bound) else "stop"
