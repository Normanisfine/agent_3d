"""Scene-level elapsed time, stage timing and normalized provider usage summaries."""
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from agen3d.multiagent.store import save


class Timings:
    def __init__(self, output):
        self.output = output
        self.start = time.monotonic()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.stages = []

    @contextmanager
    def stage(self, name):
        start = time.monotonic()
        record = {"stage": name, "status": "running"}
        self.stages.append(record)
        try:
            yield
            record["status"] = "completed"
        except Exception as exc:
            record.update(status="failed", error_type=type(exc).__name__, error=str(exc)[:1200])
            raise
        finally:
            record["wall_seconds"] = time.monotonic() - start
            self.flush()

    def flush(self):
        result = {"started_at": self.started_at, "wall_seconds": time.monotonic() - self.start,
                  "stages": self.stages}
        save(self.output / "timing.json", result)
        return result


def usage_summary(ledger):
    result = {}
    for charge in ledger.summary()["charges"]:
        detail = charge["detail"]
        alias = detail.get("alias", charge["label"].split(":")[0])
        row = result.setdefault(alias, {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                      "cached_input_tokens": 0, "unknown_token_calls": 0,
                                      "known_actual_usd": 0, "unknown_charge_calls": 0,
                                      "wall_seconds": 0})
        row["calls"] += 1
        row["wall_seconds"] += detail.get("wall_seconds", 0)
        if charge["actual"] is None:
            row["unknown_charge_calls"] += 1
        else:
            row["known_actual_usd"] += charge["actual"]
        wrapper = detail.get("usage", {})
        usages = wrapper.get("turns", [wrapper.get("usage", {})])
        if not usages or not any(usages):
            row["unknown_token_calls"] += 1
        for usage in usages:
            row["input_tokens"] += usage.get("prompt_tokens", usage.get("input_tokens", 0))
            row["output_tokens"] += usage.get("completion_tokens", usage.get("output_tokens", 0))
            row["cached_input_tokens"] += usage.get("cached_input_tokens", usage.get("cache_read_input_tokens",
                usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)))
    return result


def complete_costs(ledger, timing, gpu_seconds, render_seconds, cpu_rate):
    """Add host wall time outside separately billed GPU/render jobs.

    The CPU rate represents allocated host time, including orchestration waits.
    These retrospective host costs are outside the model-call reservation budget.
    """
    host_seconds = max(0., timing["wall_seconds"] - gpu_seconds - render_seconds)
    host_cost = host_seconds / 3600 * cpu_rate if cpu_rate is not None else None
    summary = ledger.summary() if ledger else {"known_actual_usd": 0., "unknown_or_pending_calls": 0}
    unknown = summary["unknown_or_pending_calls"] + int(host_cost is None)
    known = summary["known_actual_usd"] + (host_cost or 0.)
    return {"call_ledger": summary, "other_host_wall_seconds": host_seconds,
            "other_host_actual_usd": host_cost, "known_actual_usd": known,
            "unknown_cost_items": unknown, "total_actual_usd": None if unknown else known,
            "basis": "GPU/render ledger plus remaining allocated host wall time; includes preprocessing and evaluation",
            "budget_scope": "Call reservations only; additional host cost is retrospective"}
