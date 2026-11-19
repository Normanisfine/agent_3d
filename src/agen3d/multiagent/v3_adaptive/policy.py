"""V3 offers tiers; the engine advances only when a task remains unresolved."""


def candidates(role, models):
    if role in {"planner", "judge"}:
        return [role]
    # Reusing the planner transport does not grant planner permissions: the
    # escalated task retains its original worker role and tool catalog.
    return ["cheap", "medium", "planner"]
