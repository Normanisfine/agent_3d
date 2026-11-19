"""ARKitScenes raw-scene loading and conversion (runbook stage 1, data).

Conventions checked against apple/ARKitScenes threedod/benchmark_scripts:
- lowres_wide.traj rows: timestamp, axis-angle (3), translation (3) of the
  world->camera transform; its inverse is camera-to-world, OpenCV camera axes.
- 3D annotations live in the same world frame, which is gravity aligned, z up.
- vga_wide/<id>_<timestamp>.png frames share the trajectory clock; .pincam is
  "w h fx fy cx cy".
"""
import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from v2s import boxes

# ARKitScenes 3DOD's 17 categories.
CLASSES = ['cabinet', 'refrigerator', 'shelf', 'stove', 'bed', 'sink', 'washer', 'toilet', 'bathtub',
           'oven', 'dishwasher', 'fireplace', 'stool', 'chair', 'table', 'tv_monitor', 'sofa']

# Image rotation that makes the sky point up.
UPRIGHT = {'Up': None, 'Left': cv2.ROTATE_90_CLOCKWISE, 'Right': cv2.ROTATE_90_COUNTERCLOCKWISE,
           'Down': cv2.ROTATE_180}
# World-z components of the camera x/y/z axes for each orientation (ARKitScenes rectify_im.py).
_ORIENT = {'Up': [0, -1, 0], 'Left': [-1, 0, 0], 'Down': [0, 1, 0], 'Right': [1, 0, 0]}


def orientation_from_poses(c2w):
    """Majority vote of per-frame orientation, as in ARKitScenes threedod rectify_im.decide_pose.

    metadata.csv's sky_direction disagreed with the poses on scene 41125700 (metadata 'Up',
    poses 'Left' on 1034/1064 frames, and the frames are visibly sideways), so poses win.
    """
    names = list(_ORIENT)
    votes = np.argmax(c2w[:, 2, :3] @ np.array([_ORIENT[n] for n in names], float).T, axis=1)
    counts = {n: int((votes == i).sum()) for i, n in enumerate(names)}
    return max(counts, key=counts.get), counts


def stamp(path):
    return float(Path(path).stem.rsplit('_', 1)[1])


def read_traj(path):
    ts, c2w = [], []
    for line in Path(path).read_text().split('\n'):
        tok = line.split()
        if not tok:
            continue
        w2c = np.eye(4)
        w2c[:3, :3] = Rotation.from_rotvec([float(v) for v in tok[1:4]]).as_matrix()
        w2c[:3, 3] = [float(v) for v in tok[4:7]]
        ts.append(float(tok[0]))
        c2w.append(np.linalg.inv(w2c))
    return np.array(ts), np.array(c2w)


def pose_interpolator(ts, c2w):
    slerp = Slerp(ts, Rotation.from_matrix(c2w[:, :3, :3]))

    def pose(t):
        t = float(np.clip(t, ts[0], ts[-1]))
        out = np.eye(4)
        out[:3, :3] = slerp([t]).as_matrix()[0]
        out[:3, 3] = [np.interp(t, ts, c2w[:, i, 3]) for i in range(3)]
        return out
    return pose


def read_pincam(path):
    w, h, fx, fy, cx, cy = [float(v) for v in Path(path).read_text().split()]
    return (int(w), int(h)), np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])


def sky_direction(metadata_csv, video_id):
    for row in csv.DictReader(open(metadata_csv)):
        if row['video_id'] == str(video_id):
            return row['sky_direction']
    raise KeyError(video_id)


def gt_records(annotation_json):
    data = json.loads(Path(annotation_json).read_text())['data']
    out = []
    for i, obj in enumerate(data):
        label = obj['label'].replace(' ', '_').replace('-', '_').replace('/', '_')
        if label not in CLASSES:
            continue
        obb = obj['segments']['obbAligned']
        out.append(boxes.from_obb(f'gt_{i:02d}_{label}', label, obb['centroid'], obb['axesLengths'],
                                  obb['normalizedAxes']))
    return out


def project(points_world, c2w, K):
    w2c = np.linalg.inv(c2w)
    cam = points_world @ w2c[:3, :3].T + w2c[:3, 3]
    uv = cam @ K.T
    return uv[:, :2] / uv[:, 2:3], cam[:, 2]


def draw_boxes(image, records, c2w, K, color=(0, 255, 0)):
    img = image.copy()
    for rec in records:
        uv, z = project(boxes.corners(rec), c2w, K)
        for a, b in boxes.EDGES:
            if z[a] > 0.05 and z[b] > 0.05:
                cv2.line(img, tuple(int(v) for v in uv[a]), tuple(int(v) for v in uv[b]), color, 2, cv2.LINE_AA)
        if (z > 0.05).all():
            p = uv.mean(0).astype(int)
            cv2.putText(img, rec['category'], tuple(p), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
    return img


def prepare(raw_dir, metadata_csv, out_dir, fps_out=10):
    """Write video.mp4 (upright, fps_out) + frame_map.json + gt_boxes.json + meta.json."""
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    video_id = raw_dir.name
    out_dir.mkdir(parents=True, exist_ok=False)
    sky_metadata = sky_direction(metadata_csv, video_id)
    ts, c2w = read_traj(raw_dir / 'lowres_wide.traj')
    sky, votes = orientation_from_poses(c2w)
    pose = pose_interpolator(ts, c2w)
    frames = sorted((raw_dir / 'vga_wide').glob('*.png'), key=stamp)
    frames = [f for f in frames if ts[0] <= stamp(f) <= ts[-1]]
    native_fps = (len(frames) - 1) / (stamp(frames[-1]) - stamp(frames[0]))
    step = max(1, round(native_fps / fps_out))
    frames = frames[::step]
    first = cv2.imread(str(frames[0]))
    if UPRIGHT[sky] is not None:
        first = cv2.rotate(first, UPRIGHT[sky])
    h, w = first.shape[:2]
    writer = cv2.VideoWriter(str(out_dir / 'video.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), fps_out, (w, h))
    rows = []
    for i, f in enumerate(frames):
        img = cv2.imread(str(f))
        if UPRIGHT[sky] is not None:
            img = cv2.rotate(img, UPRIGHT[sky])
        writer.write(img)
        size, K = read_pincam(raw_dir / 'vga_wide_intrinsics' / (f.stem + '.pincam'))
        rows.append({'video_frame': i, 'arkit_timestamp': stamp(f), 'vga_file': f.name,
                     'c2w_arkit': pose(stamp(f)).tolist(), 'K_vga_native': K.tolist()})
    writer.release()
    (out_dir / 'frame_map.json').write_text(json.dumps(
        {'note': 'video_frame i of video.mp4 is vga_file; c2w_arkit is camera-to-world (OpenCV axes) '
                 'interpolated from lowres_wide.traj; K is for the native (unrotated) vga frame',
         'frames': rows}) + '\n')
    gt = gt_records(raw_dir / f'{video_id}_3dod_annotation.json')
    boxes.save(gt, out_dir / 'gt_boxes.json')
    meta = {'video_id': video_id, 'sky_direction_from_poses': sky, 'orientation_votes': votes,
            'sky_direction_metadata_csv': sky_metadata, 'fps_out': fps_out, 'native_vga_fps': native_fps,
            'frame_step': step, 'num_video_frames': len(rows), 'duration_s': stamp(frames[-1]) - stamp(frames[0]),
            'num_gt_objects': len(gt)}
    (out_dir / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    return meta


def lidar_cloud(raw_dir, frame_step=12, pixel_step=2, max_depth=5.0, voxel=0.02):
    """Fuse ARKit lowres_depth (uint16 mm, 256x192) into one world point cloud (ARKit world, z up)."""
    import open3d as o3d
    raw_dir = Path(raw_dir)
    ts, c2w = read_traj(raw_dir / 'lowres_wide.traj')
    pose = pose_interpolator(ts, c2w)
    intr = sorted((raw_dir / 'lowres_wide_intrinsics').glob('*.pincam'), key=stamp)
    intr_ts = np.array([stamp(p) for p in intr])
    depths = sorted((raw_dir / 'lowres_depth').glob('*.png'), key=stamp)[::frame_step]
    cloud = o3d.geometry.PointCloud()
    for f in depths:
        t = stamp(f)
        if not ts[0] <= t <= ts[-1]:
            continue
        d = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)[::pixel_step, ::pixel_step].astype(np.float64) / 1000.0
        _, K = read_pincam(intr[int(np.argmin(np.abs(intr_ts - t)))])
        v, u = np.nonzero((d > 0.1) & (d < max_depth))
        z = d[v, u]
        x = (u * pixel_step - K[0, 2]) * z / K[0, 0]
        y = (v * pixel_step - K[1, 2]) * z / K[1, 1]
        cam = np.stack([x, y, z], 1)
        P = pose(t)
        cloud += o3d.geometry.PointCloud(o3d.utility.Vector3dVector(cam @ P[:3, :3].T + P[:3, 3]))
        if len(cloud.points) > 3_000_000:
            cloud = cloud.voxel_down_sample(voxel)
    return np.asarray(cloud.voxel_down_sample(voxel).points)


def check_projection(raw_dir, scene_dir, picks=(0.1, 0.5, 0.9)):
    """Draw GT boxes on native vga frames: verifies intrinsics, poses and box parsing together."""
    raw_dir, scene_dir = Path(raw_dir), Path(scene_dir)
    fm = json.loads((scene_dir / 'frame_map.json').read_text())['frames']
    gt = boxes.load(scene_dir / 'gt_boxes.json')
    tiles = []
    for p in picks:
        row = fm[int(p * (len(fm) - 1))]
        img = cv2.imread(str(raw_dir / 'vga_wide' / row['vga_file']))
        img = draw_boxes(img, gt, np.array(row['c2w_arkit']), np.array(row['K_vga_native']))
        cv2.putText(img, f"frame {row['video_frame']}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
        tiles.append(img)
    sheet = np.concatenate(tiles, axis=1)
    cv2.imwrite(str(scene_dir / 'gt_projection_check.jpg'), sheet)
    return scene_dir / 'gt_projection_check.jpg'


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('raw_dir', type=Path)
    ap.add_argument('--metadata', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--fps', type=int, default=10)
    a = ap.parse_args()
    print(json.dumps(prepare(a.raw_dir, a.metadata, a.out, a.fps), indent=1))
    print(check_projection(a.raw_dir, a.out))
