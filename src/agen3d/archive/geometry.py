"""Exact convex intersection of arbitrary oriented boxes (no AABB approximation)."""
from itertools import combinations, product

import numpy as np
from scipy.spatial import ConvexHull, QhullError

from agen3d.archive.scene import Box


def corners(box: Box):
    return np.asarray(box.center) + (np.array(list(product((-0.5, 0.5), repeat=3))) * box.extent) @ np.asarray(box.rotation).T


def planes(box: Box):
    # Six inequalities n.x <= d describe the interior of the box. Both signs of
    # each local axis are needed, with the same corresponding half-extent.
    r = np.asarray(box.rotation)
    normals = np.concatenate((r.T, -r.T))
    offsets = normals @ box.center + np.tile(np.asarray(box.extent) / 2, 2)
    return normals, offsets


def oriented_iou(a: Box, b: Box) -> float:
    # Recentre to keep numerical tolerance independent of world origin.
    origin = np.asarray(a.center)
    a = a.model_copy(update={"center": (0., 0., 0.)})
    b = b.model_copy(update={"center": tuple(np.asarray(b.center) - origin)})
    an, ad = planes(a)
    bn, bd = planes(b)
    n, d = np.concatenate((an, bn)), np.concatenate((ad, bd))
    vertices = []
    # Every vertex of the intersection lies at the intersection of at least
    # three boundary planes. Enumerating 12-choose-3 systems is cheap for boxes
    # and handles arbitrary roll/pitch/yaw without a yaw-only approximation.
    for indices in combinations(range(12), 3):
        matrix = n[list(indices)]
        if abs(np.linalg.det(matrix)) < 1e-10:
            continue
        v = np.linalg.solve(matrix, d[list(indices)])
        if np.all(n @ v <= d + 1e-9):
            vertices.append(v)
    if len(vertices) < 4:
        return 0.0
    try:
        # Coincident planes generate repeated vertices; deduplicate before hull
        # construction. Degenerate intersections have no three-dimensional volume.
        intersection = ConvexHull(np.unique(np.round(vertices, 10), axis=0)).volume
    except QhullError:
        return 0.0  # Face/edge contact has zero volume.
    va, vb = np.prod(a.extent), np.prod(b.extent)
    intersection = min(intersection, va, vb)
    return float(intersection / (va + vb - intersection))


def box_from_corners(points) -> Box:
    """Recover orthogonal edges without relying on a vendor's corner ordering."""
    p = np.asarray(points, dtype=float)
    if p.shape != (8, 3) or not np.isfinite(p).all():
        raise ValueError("Eight finite box corners required")
    vectors = p[1:] - p[0]
    # Diagonals also occur in this list. Orthogonality alone is insufficient:
    # regenerate all eight corners to verify a candidate edge triplet.
    for triple in combinations(vectors, 3):
        lengths = np.linalg.norm(triple, axis=1)
        if min(lengths) <= 0:
            continue
        axes = np.asarray(triple).T / lengths
        if not np.allclose(axes.T @ axes, np.eye(3), atol=1e-4):
            continue
        generated = p[0] + np.array(list(product((0, 1), repeat=3))) @ np.asarray(triple)
        if np.max(np.min(np.linalg.norm(generated[:, None] - p[None], axis=2), axis=1)) > 1e-4:
            continue
        if np.linalg.det(axes) < 0:
            axes[:, 2] *= -1
        # Remove floating point drift in exported simulator corners.
        u, _, vt = np.linalg.svd(axes)
        axes = u @ vt
        return Box(center=tuple(p.mean(axis=0)), extent=tuple(lengths),
                   rotation=tuple(map(tuple, axes)))
    raise ValueError("Corners do not describe an orthogonal cuboid")
