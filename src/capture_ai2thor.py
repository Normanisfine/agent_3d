"""Capture a pinned AI2-THOR scene along an explicit, scene-specific trajectory."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering
from rebuild_floorplan209 import BUILD, PROJECT, encode, write_json

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--trajectory', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--frames', type=int, default=240)
    parser.add_argument('--fps', type=int, default=20)
    parser.add_argument('--encode-only', action='store_true')
    args = parser.parse_args()
    out = (args.output or PROJECT/'datasets/ai2thor'/args.scene).resolve()
    trajectory = json.loads(args.trajectory.read_text())
    if trajectory['scene'] != args.scene:
        raise ValueError('Trajectory scene mismatch')
    waypoints = np.asarray(trajectory['waypoints_xz'], dtype=float)
    target_x, target_z = trajectory['look_at_xz']
    horizon = trajectory['horizon_degrees']
    if args.frames < 2 or args.fps <= 0:
        parser.error('frames must be >=2 and fps positive')
    if args.encode_only:
        manifest = json.loads((out/'reference/manifest.json').read_text())
        encode(out, len(manifest['frames']), manifest['fps'])
        return
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite {out}')
    for part in ('reference/rgb', 'ground_truth/depth_m', 'ground_truth/instance_segmentation',
                 'ground_truth/metadata', 'ground_truth/annotations', 'runtime_cache'):
        (out/part).mkdir(parents=True, exist_ok=True)

    class LocalController(Controller):
        @property
        def base_dir(self):
            return str(out/'runtime_cache')

    config = dict(local_executable_path=str(PROJECT/'datasets/ai2thor/releases'/BUILD/BUILD),
                  platform=CloudRendering, scene=args.scene, width=1440, height=960,
                  fieldOfView=70, quality='Ultra', snapToGrid=False,
                  renderDepthImage=True, renderInstanceSegmentation=True,
                  server_timeout=90, server_start_timeout=120)
    lengths = np.linalg.norm(np.diff(waypoints, axis=0), axis=1)
    cumulative = np.r_[0, np.cumsum(lengths)]
    rows, poses = [], []
    controller = LocalController(**config)
    try:
        assert controller.last_event.metadata['lastActionSuccess']
        y = controller.last_event.metadata['agent']['position']['y']
        for i, t in enumerate(np.linspace(0, cumulative[-1], args.frames)):
            j = min(np.searchsorted(cumulative, t, side='right')-1, len(lengths)-1)
            x, z = waypoints[j]+(waypoints[j+1]-waypoints[j])*(t-cumulative[j])/lengths[j]
            yaw = math.degrees(math.atan2(target_x-x, target_z-z)) % 360
            event = controller.step(action='TeleportFull', position={'x':float(x),'y':y,'z':float(z)},
                                    rotation={'x':0,'y':yaw,'z':0}, horizon=horizon, standing=True)
            if not event.metadata['lastActionSuccess']:
                raise RuntimeError(event.metadata['errorMessage'])
            event = controller.step(action='Pass')
            if not event.metadata['lastActionSuccess']:
                raise RuntimeError(event.metadata['errorMessage'])
            rgb = np.asarray(event.frame)
            depth = np.asarray(event.depth_frame)
            assert rgb.shape == (960,1440,3) and rgb.dtype == np.uint8
            assert depth.shape == (960,1440) and np.isfinite(depth).all() and depth.min() >= 0
            path = out / f'reference/rgb/{i:06d}.png'
            Image.fromarray(rgb, 'RGB').save(path)
            np.savez_compressed(out/f'ground_truth/depth_m/{i:06d}.npz', depth_m=depth)
            Image.fromarray(event.instance_segmentation_frame).save(
                out/f'ground_truth/instance_segmentation/{i:06d}.png')
            write_json(out/f'ground_truth/metadata/{i:06d}.json', event.metadata)
            write_json(out/f'ground_truth/annotations/{i:06d}.json', {
                'object_id_to_color': {k:list(map(int,v)) for k,v in event.object_id_to_color.items()},
                'boxes_xyxy': {k:list(map(int,v)) for k,v in event.instance_detections2D.items()},
                'mask_pixels': {k:int(v.sum()) for k,v in event.instance_masks.items()}})
            rows.append({'frame_id':f'{i:06d}', 'timestamp_s':i/args.fps,
                         'path':f'rgb/{i:06d}.png', 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            poses.append({'frame_id':f'{i:06d}', 'cameraPosition':event.metadata['cameraPosition'],
                          'agent':event.metadata['agent'], 'fov':event.metadata['fov']})
            if i % 20 == 0:
                print(f'Captured {i+1}/{args.frames}', flush=True)
    finally:
        controller.stop()
    write_json(out/'reference/manifest.json', {'dataset':'ai2thor','scene':args.scene,
               'build':BUILD,'width':1440,'height':960,'fps':args.fps,'frames':rows,
               'source':'Fresh native event.frame RGB; no grading or channel swap'})
    write_json(out/'ground_truth/cameras.json', {'coordinate_system':'Unity world, Y up; cameraHorizon positive down',
               'width':1440,'height':960,'vertical_fov_degrees':70,'frames':poses})
    write_json(out/'capture_config.json', {k:str(v) if k=='platform' else v for k,v in config.items()})
    write_json(out/'ground_truth/trajectory.json', {'waypoints_xz':waypoints.tolist(),
               'look_at_xz':[target_x,target_z],'horizon_degrees':horizon,'frames':args.frames,
               'source':trajectory['source']})
    encode(out, args.frames, args.fps)
    (out/'README.txt').write_text(
        f'{args.scene}: fresh original AI2-THOR reference and synchronized ground truth.\n'
        'reference/rgb/: native RGB PNG frames, authoritative colors.\n'
        'reference/original_camera_rgb.mp4: compatible H.264 YUV420 playback copy, 20 fps.\n'
        'reference/color_validation.jpg: native PNG (left), decoded MP4 (right).\n'
        'ground_truth/: depth in meters (.npz key depth_m), instance colors and ID mapping,\n'
        '2D boxes, complete per-frame simulator metadata (including 3D boxes), camera poses.\n'
        'Simulator physical labels are simulator assignments, not real-world measurements.\n'
        'Original Unity geometry remains in ../releases/. This is not a mesh export.\n'
        'Ground truth is for evaluation; use reference/rgb/ for RGB-only reconstruction.\n'
        'No randomization, furnishing changes, color grading, or BGR/RGB swap.\n'
        'Validation includes all video frames; MP4 is lossy, PNGs are lossless.\n'
        'Regenerate with envs/ai2thor/bin/python agen3d/src/capture_ai2thor.py --scene SCENE --trajectory PATH --output NEW_DIR\n')
    print('COMPLETE', out, flush=True)


if __name__ == '__main__':
    main()
