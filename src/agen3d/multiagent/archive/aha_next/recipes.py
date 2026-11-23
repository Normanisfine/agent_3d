"""Small, typed output language for cheap object-local builders.

This is a representation boundary, not a visual quality certificate.
"""
from typing import Literal
from pydantic import Field, model_validator
from agen3d.schema import Record
from agen3d.multiagent.aha.contracts import Proposal


class Part(Record):
    center: tuple[float, float, float]
    dimensions: tuple[float, float, float]
    rotation_z: float = 0.
    color: tuple[float, float, float] = (.5, .5, .5)

    @model_validator(mode='after')
    def bounds(self):
        if min(self.dimensions) <= 0 or max(self.dimensions) > 30:
            raise ValueError('Part extents must be positive and at most 30 metres')
        if max(abs(v) for v in self.center) > 100:
            raise ValueError('Part center exceeds 100 metre room envelope')
        if not all(0 <= v <= 1 for v in self.color):
            raise ValueError('RGB must be in [0, 1]')
        return self


class Recipe(Record):
    parent_revision: str
    object_id: str
    route: Literal['parts', 'abstain']
    reason: str = Field(min_length=1, max_length=1200)
    semantic_class: str = Field(min_length=1, max_length=100)
    source_ids: list[str] = Field(min_length=1)
    parts: list[Part] = Field(max_length=16)

    @model_validator(mode='after')
    def shape(self):
        if (self.route == 'parts') != bool(self.parts):
            raise ValueError('parts requires geometry; abstain requires empty parts')
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError('Duplicate evidence IDs')
        return self


def compile_recipe(recipe, task, revision, images):
    if recipe.parent_revision != revision or task.object_ids != [recipe.object_id]:
        raise ValueError('Recipe parent or scope mismatch')
    if not set(recipe.source_ids) <= set(images):
        raise ValueError('Recipe cites unavailable source evidence')
    if recipe.route == 'abstain':
        raise ValueError('Recipe abstained: ' + recipe.reason)
    oid = recipe.object_id
    lines = [f'remove_object({oid!r})',
             f'root = bpy.data.objects.new({oid!r}, None)',
             'bpy.context.scene.collection.objects.link(root)']
    for index, part in enumerate(recipe.parts):
        name = f'{oid}_part_{index}'
        lines += [f'mat = bpy.data.materials.new({name!r})',
                  f'mat.diffuse_color = {(*part.color, 1.)!r}',
                  f'child = roomkit.box({name!r}, {part.center!r}, {part.dimensions!r}, material=mat)',
                  f'child.rotation_euler.z = {part.rotation_z!r}',
                  'child.parent = root']
    lines.append(f'tag_root(root, {recipe.semantic_class!r}, instance_id={oid!r})')
    return Proposal(parent_revision=revision, object_ids=[oid], route='code',
                    reason=recipe.reason, code='\n'.join(lines))
