"""Extract the outcome, instance and usage counts quoted in the small-object and cost sections."""

import hashlib
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
RESULTS = PAPER.parents[1] / "evan" / "results" / "test_opus"
VARIANTS = ["A0", "A1", "A2", "A3r", "A3v"]
BINS = ["XS", "S", "M", "L"]


def outcome_counts(summary):
    """Turn one saved per-bin summary into correct / misplaced / unmatched target counts."""
    counts = {}
    for size in BINS:
        n = summary[size]["n"]
        counts[size] = {
            "n": n,
            "correct": round(summary[size]["recall_D"] * n),
            "misplaced": round(summary[size]["misplaced_D"] * n),
            "unmatched": round(summary[size]["missed_D"] * n),
        }
        assert sum(counts[size][k] for k in ("correct", "misplaced", "unmatched")) == n
    return counts


def predicted_instances():
    # runs.md is the only saved table that records how many instances each run reconstructed.
    lines = (RESULTS / "runs.md").read_text(encoding="utf-8").splitlines()
    column = [c.strip() for c in lines[0].strip("|").split("|")].index("预测物体")
    totals = dict.fromkeys(VARIANTS, 0)
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[0] in totals:
            totals[cells[0]] += int(cells[column])
    return totals


def main():
    raw = (RESULTS / "summary.json").read_bytes()
    summary = json.loads(raw)
    instances = predicted_instances()
    out = {
        "source": "evan/results/test_opus/summary.json and runs.md",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "kind": "existing_results_summary_not_new_experiment",
        "criterion": "D",
        "alignment": "GT-camera Sim(3), scale corrected",
        "arms": {},
        "accepted_runs": [],
    }
    usage = []
    for arm in VARIANTS:
        outcomes = outcome_counts(summary["recall_pooled"][arm]["sim3"])
        out["arms"][arm] = {
            "outcomes": outcomes,
            "predicted_instances": instances[arm],
            # Matching is one-to-one, so matched targets and matched instances are the same count.
            "matched_instances": sum(o["correct"] + o["misplaced"] for o in outcomes.values()),
            "correct_instances": sum(o["correct"] for o in outcomes.values()),
        }
        for key, run in summary["runs"][arm].items():
            if "log" not in run:
                continue
            usage.append(run["log"]["usage"])
            if run["log"]["aha_accepted"]:
                room = outcome_counts(run["summary_sim3"])
                out["accepted_runs"].append({
                    "arm": arm,
                    "run": key,
                    "under_50cm_targets": room["XS"]["n"] + room["S"]["n"],
                    "under_50cm_correct": room["XS"]["correct"] + room["S"]["correct"],
                })
    fields = ("turns", "input_tokens", "cached_input_tokens", "output_tokens")
    out["driver_usage"] = {
        "n_runs": len(usage),
        "mean": {f: sum(u[f] for u in usage) / len(usage) for f in fields},
        "cached_share_of_input": sum(u["cached_input_tokens"] for u in usage)
        / sum(u["input_tokens"] for u in usage),
    }
    target = PAPER / "small-object-outcomes.json"
    target.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
