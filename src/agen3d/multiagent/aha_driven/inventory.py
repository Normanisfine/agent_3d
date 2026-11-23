"""Boxer evidence and the supervisor's explicit ownership decisions."""
import json
from pathlib import Path
from typing import Annotated

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from agen3d.schema import Record
from ..aha.contracts import Plan

ItemID = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_-]+$')]
Positive = Annotated[float, Field(gt=0)]


class Detection(BaseModel):
    # Evan's export also contains provenance and redundant box fields.
    model_config = ConfigDict(extra='ignore', allow_inf_nan=False)
    item_id: ItemID
    category: str
    center: tuple[float, float, float]
    size: tuple[Positive, Positive, Positive]
    yaw: float
    score: float
    best_frame: int | None
    bbox2d_xyxy: tuple[float, float, float, float] | None


class Omission(Record):
    item_id: ItemID
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class InventoryPlan(Plan):
    omissions: list[Omission] = Field(default_factory=list)


class BoxerInventory(Record):
    source: str
    items: dict[str, Detection]
    crops: dict[str, str]
    plan: InventoryPlan | None = None

    @classmethod
    def load(cls, path):
        path = Path(path).resolve(strict=True)
        items, crops = {}, {}
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            raise ValueError('Expected a JSON array of Boxer detections')
        for row in rows:
            item = Detection.model_validate(row)
            key = item.item_id
            if key in items:
                raise ValueError(f'Duplicate inventory ID: {key}')
            items[key] = item
            crop = path.parent / 'inventory_crops' / (key + '.jpg')
            if crop.is_file():
                crops[key] = str(crop.resolve())
        return cls(source=str(path), items=items, crops=crops)

    def planner_manifest(self, folder):
        """Match the A2 planner's 16 labeled thumbnails per sheet."""
        crops = list(self.crops.items())
        sheets = []
        for start in range(0, len(crops), 16):
            batch = crops[start:start + 16]
            sheet = Image.new('RGB', (640, 150 * ((len(batch) + 3) // 4)), 'white')
            draw = ImageDraw.Draw(sheet)
            for index, (item_id, path) in enumerate(batch):
                x, y = index % 4 * 160, index // 4 * 150
                with Image.open(path) as crop:
                    crop.thumbnail((156, 124))
                    sheet.paste(crop, (x, y + 20))
                draw.text((x, y + 2), item_id, fill='black')
            target = folder / f'inventory_sheet_{start // 16}.jpg'
            sheet.save(target, quality=90)
            sheets.append(str(target))
        return {**self.model_dump(exclude={'plan'}), 'crop_sheets': sheets,
                'inventory_policy': 'Check predicted boxes against the source views. Give every '
                'visible instance an editable object ID, including items the detector missed. '
                'Assign each detection ID to one task or record a source-based omission reason.'}

    def decisions(self, plan, results, scene_objects):
        if plan is None:
            return {key: {'action': 'unassigned'} for key in self.items}
        decisions = {}
        for task in plan.tasks:
            for key in task.object_ids:
                if key not in self.items:
                    continue
                if key in decisions:
                    raise ValueError(f'Duplicate inventory assignment: {key}')
                committed = results.get(task.task_id, {}).get('status') == 'candidate_committed'
                decisions[key] = {'task': task.task_id, 'action': 'built' if committed and
                                  key in scene_objects else 'assigned'}
        for omission in plan.omissions:
            key = omission.item_id
            if key not in self.items or key in decisions:
                raise ValueError(f'Unknown or already accounted inventory ID: {key}')
            decisions[key] = {'action': 'skipped', 'reason': omission.reason}
        missing = self.items.keys() - decisions.keys()
        if missing:
            raise ValueError('Unaccounted inventory IDs: ' + ', '.join(sorted(missing)))
        return decisions

    def check_scope(self, task):
        if self.plan is None:
            raise ValueError('Register the supervisor inventory-plan before construction')
        owner = next((t for t in self.plan.tasks if t.task_id == task.task_id), None)
        expected = set(owner.object_ids if owner else ()) & self.items.keys()
        assigned = set(task.object_ids) & self.items.keys()
        if expected != assigned or len(task.object_ids) != len(set(task.object_ids)):
            raise ValueError(f'Task {task.task_id} differs from its inventory assignment')
        if owner and not set(owner.depends_on).issubset(task.depends_on):
            raise ValueError(f'Task {task.task_id} is missing a registered dependency')

    def evidence(self, task):
        selected = {k: self.items[k].model_dump(mode='json') for k in task.object_ids if k in self.items}
        crops = {'boxer_' + k: self.crops[k] for k in selected if k in self.crops}
        return selected, crops
