"""Base model shared by the reconstruction controllers."""
from pydantic import BaseModel, ConfigDict


__all__ = [
    "Record", "Box", "Observation", "ObjectState", "SceneState", "Frame", "InputManifest", "Issue",
]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# Keep scene types available to callers using the original schema module.
def __getattr__(name):
    if name in __all__:
        from .archive import scene
        return getattr(scene, name)
    raise AttributeError(name)
