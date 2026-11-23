"""Input-derived box/track checks and bounded support repair, without GT access."""
from dataclasses import dataclass

import numpy as np

from .geometry import corners
from agen3d.archive.scene import Issue, SceneState


@dataclass(frozen=True)
class Verifier:
    contact_tolerance_m: float = 0.02

    def check(self, scene: SceneState) -> list[Issue]:
        active = {o.object_id: o for o in scene.objects if o.status not in {"rejected", "missing"}}
        issues, tracks = [], {}
        for obj in active.values():
            for track in {o.track_id for o in obj.observations if o.track_id}:
                if track in tracks:
                    issues.append(Issue(object_id=obj.object_id, issue_type="duplicate_track",
                                        severity="high", evidence={"other": tracks[track], "track": track},
                                        suggested_tool="review_association", confidence=0.9))
                tracks[track] = obj.object_id
            if not obj.support_id:
                continue
            support = active.get(obj.support_id)
            if support is None or support.object_id == obj.object_id:
                issues.append(Issue(object_id=obj.object_id, issue_type="unknown_support",
                                    severity="medium", evidence={"support_id": obj.support_id},
                                    suggested_tool="review_support", confidence=1))
                continue
            # Only axis-aligned support surfaces qualify for automatic height repair.
            if not np.allclose(support.box.rotation, np.eye(3), atol=1e-6):
                continue
            points, surface = corners(obj.box), corners(support.box)
            overlaps = np.all(points[:, :2].max(0) > surface[:, :2].min(0)) and np.all(points[:, :2].min(0) < surface[:, :2].max(0))
            gap = float(points[:, 2].min() - surface[:, 2].max())
            if overlaps and abs(gap) > self.contact_tolerance_m:
                issues.append(Issue(object_id=obj.object_id, issue_type="support_gap",
                                    severity="medium", evidence={"gap_m": gap, "support_id": support.object_id},
                                    suggested_tool="snap_support", confidence=0.8))
        return issues


def repair(scene: SceneState, verifier: Verifier, max_steps=3, max_translation_m=0.1):
    """Each accepted step decreases verified issue count; preserve full before/after trace.

    Box-level diagnostic only: acceptance does not certify rendered image agreement.
    """
    if max_steps < 0 or max_translation_m <= 0:
        raise ValueError("Invalid repair bounds")
    current = scene.model_copy(deep=True)
    # Work on detached snapshots: callers can retain the original as a baseline,
    # and a rejected proposal cannot leak mutations back into the accepted scene.
    trace = []
    for _ in range(max_steps):
        issues = verifier.check(current)
        candidates = [i for i in issues if i.suggested_tool == "snap_support"
                      and abs(i.evidence["gap_m"]) <= max_translation_m]
        if not candidates:
            break
        issue = candidates[0]
        trial = current.model_copy(deep=True)
        obj = next(o for o in trial.objects if o.object_id == issue.object_id)
        before = obj.box.model_dump()
        x, y, z = obj.box.center
        obj.box.center = (x, y, z - issue.evidence["gap_m"])
        obj.edit_history.append(f"snap_support: dz={-issue.evidence['gap_m']:.6f}m")
        remaining = verifier.check(trial)
        # This is a conservative box-level acceptance criterion, not a quality
        # claim. Render agreement and collision checks must gate Blender edits.
        accepted = len(remaining) < len(issues)
        trace.append({"issue": issue.model_dump(), "before": before, "after": obj.box.model_dump(),
                      "accepted": accepted})
        if not accepted:
            break
        current = trial
    return current, trace, verifier.check(current)
