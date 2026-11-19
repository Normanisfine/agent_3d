"""V1 deliberately shares weights, but engine.task gives each role its own context."""


def candidates(role, models):
    # Keeping leadership fixed isolates worker model substitution in experiments.
    return [role if role in {"planner", "judge"} else "cheap"]
