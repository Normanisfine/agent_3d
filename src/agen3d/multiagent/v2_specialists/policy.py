"""V2 separates role model aliases from specialist tool execution."""


def candidates(role, models):
    if role in {"planner", "judge"}:
        return [role]
    # A geometry role can keep a Qwen controller and call HiSpatial as a tool.
    # Configuring models.geometry is an optional controller replacement.
    return [role if role in models else "cheap"]
