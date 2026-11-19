"""Versioned interchange artifacts: metres, right-handed Z-up, rotation columns = box axes."""
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    # Reject misspelled fields and NaN/Inf at every JSON load boundary. Permissive
    # parsing here could silently turn a malformed annotation into a valid score.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Box(Record):
    # Extent is the FULL side length, not a half-extent. Matrix columns are local
    # axes in world coordinates; this is shared by matching and support checks.
    center: tuple[float, float, float]
    extent: tuple[float, float, float]
    rotation: tuple[tuple[float, float, float], ...] = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    @model_validator(mode="after")
    def valid_box(self):
        r = np.asarray(self.rotation)
        if min(self.extent) <= 0 or r.shape != (3, 3):
            raise ValueError("Positive full extents and 3x3 rotation required")
        if not np.allclose(r.T @ r, np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(r), 1, atol=1e-5):
            raise ValueError("Box axes must be orthonormal and right-handed")
        return self


class Observation(Record):
    frame_id: str
    track_id: str | None = None
    mask: str | None = None
    crop: str | None = None


class ObjectState(Record):
    # A proposed object is still a prediction and counts in precision. Rejected
    # and missing hypotheses remain in the audit trail but are not scene objects.
    object_id: str
    box: Box
    category: str | None = None
    description: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    status: Literal["proposed", "confirmed", "ambiguous", "rejected", "missing"] = "proposed"
    mesh_source: Literal["primitive", "retrieved", "generated"] = "primitive"
    mesh_path: str | None = None
    material: str | None = None
    support_id: str | None = None
    observations: list[Observation] = Field(default_factory=list)
    uncertainty: str = "unquantified"
    provenance: list[str] = Field(default_factory=list)
    edit_history: list[str] = Field(default_factory=list)


class SceneState(Record):
    schema_version: Literal[1] = 1
    scene_id: str
    coordinate_frame: Literal["RH_Z_UP_METRES"] = "RH_Z_UP_METRES"
    scale_mode: Literal["estimated_scale", "oracle_scale"] = "estimated_scale"
    alignment_id: str = Field(min_length=1)
    objects: list[ObjectState]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [o.object_id for o in self.objects]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate stable object IDs")
        return self


class Frame(Record):
    frame_id: str
    timestamp_s: float = Field(ge=0)
    path: str
    sha256: str


class InputManifest(Record):
    # Deliberately no camera, depth, mask or GT field in the reconstruction input.
    schema_version: Literal[1] = 1
    dataset: Literal["ai2thor", "ca1m", "generic"]
    dataset_version: str
    scene_id: str
    split: Literal["train", "val", "test"]
    input_mode: Literal["rgb_only"] = "rgb_only"
    frames: list[Frame] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_frames(self):
        if len({f.frame_id for f in self.frames}) != len(self.frames):
            raise ValueError("Repeated frame IDs")
        if any(b.timestamp_s <= a.timestamp_s for a, b in zip(self.frames, self.frames[1:])):
            raise ValueError("Frame timestamps must increase")
        return self


class Issue(Record):
    object_id: str
    issue_type: str
    severity: Literal["low", "medium", "high"]
    evidence: dict
    suggested_tool: str
    confidence: float = Field(ge=0, le=1)
