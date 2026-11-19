import math

import pytest

from agen3d.evaluation import EvaluationContext, Label, evaluate
from agen3d.geometry import box_from_corners, corners, oriented_iou
from agen3d.schema import Box, ObjectState, SceneState


def box(center=(0, 0, 0), extent=(1, 1, 1)):
    return Box(center=center, extent=extent)


def context(labels):
    return EvaluationContext(dataset="ai2thor", scene_id="synthetic", split="val",
                             alignment_id="identity", input_manifest_sha256="fixture",
                             labels=labels, annotation_notes="Synthetic exact cuboids")


def label(oid="g", **kw):
    return Label(object_id=oid, box=box(), category="chair", visible_frames=2,
                 max_area_fraction=.005, **kw)


def scene(objects):
    return SceneState(scene_id="synthetic", alignment_id="identity", objects=objects)


def pred(oid="p", category="chair", b=None):
    return ObjectState(object_id=oid, category=category, box=b or box())


def score(objects, labels):
    return evaluate(scene(objects), context(labels), "fixture")["thresholds"]["0.5"]


def test_identical_disjoint_contact_and_scale():
    assert oriented_iou(box(), box()) == pytest.approx(1)
    assert oriented_iou(box(), box(center=(2, 0, 0))) == 0
    assert oriented_iou(box(), box(center=(1, 0, 0))) == 0
    assert oriented_iou(box(), box(extent=(2, 2, 2))) == pytest.approx(1 / 8)


def test_rotation_and_corner_permutation():
    t = math.pi / 4
    rotation = ((math.cos(t), -math.sin(t), 0), (math.sin(t), math.cos(t), 0), (0, 0, 1))
    rotated = Box(center=(0, 0, 0), extent=(1, 1, 1), rotation=rotation)
    assert oriented_iou(box(), rotated) == pytest.approx(1 / math.sqrt(2))
    recovered = box_from_corners(corners(rotated)[[5, 3, 2, 7, 0, 6, 4, 1]])
    assert oriented_iou(rotated, recovered) == pytest.approx(1)


def test_invalid_rotation_and_extent():
    with pytest.raises(ValueError):
        Box(center=(0, 0, 0), extent=(0, 1, 1))
    with pytest.raises(ValueError):
        Box(center=(0, 0, 0), extent=(1, 1, 1), rotation=((1, 0, 0), (0, 1, 0), (0, 0, -1)))


def test_perfect_missing_duplicate_and_category():
    assert score([pred()], [label()])["f1"] == 1
    assert score([], [label()])["recall"] == 0
    duplicated = score([pred("a"), pred("b")], [label()])
    assert duplicated["precision"] == .5
    assert len(duplicated["matches"]) == 1
    assert score([pred(category="table")], [label()])["recall"] == 0


def test_empty_is_undefined_not_perfect():
    assert score([], [])["f1"] is None


def test_class_agnostic_and_visibility():
    gt = context([label()]).model_copy(update={"dataset": "ca1m"})
    result = evaluate(scene([pred(category="unknown")]), gt, "fixture")
    assert result["thresholds"]["0.5"]["recall"] == 1
    gt.labels[0].visible_frames = 1
    result = evaluate(scene([]), gt, "fixture")
    assert result["excluded_gt_count"] == 1
    assert result["thresholds"]["0.5"]["recall"] is None


def test_alignment_and_frame_binding():
    with pytest.raises(ValueError):
        evaluate(scene([]), context([]), "different_frames")
    wrong = scene([]).model_copy(update={"alignment_id": "different_basis"})
    with pytest.raises(ValueError):
        evaluate(wrong, context([]), "fixture")


def test_matching_maximizes_cardinality(monkeypatch):
    # Greedy highest IoU would select only a/x; optimal selects a/y and b/x.
    values = iter([.9, .6, .6, 0])
    monkeypatch.setattr("agen3d.evaluation.oriented_iou", lambda a, b: next(values))
    result = score([pred("a"), pred("b")], [label("x"), label("y")])
    assert result["recall"] == 1
