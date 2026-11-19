"""Recapture original FloorPlan209 RGB and synchronized evaluator-only GT.

Run with envs/ai2thor/bin/python. Outputs are new, never overwritten.
PNG RGB is authoritative. MP4 is a BT.709 matrix, limited-range YUV420 playback copy.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering

PROJECT = Path(__file__).resolve().parents[1]
BUILD = 'thor-CloudRendering-f0825767cd50d69f666c7f282e54abfe58f1e917'
WAYPOINTS = np.array([[-2., -1.], [-1.5, -1.], [-1.5, -4.25], [-3.5, -4.25],
                      [-6.5, -4.25], [-6.5, -1.], [-6., -.75], [-3.5, -.75]])


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def encode(out, count, fps):
    video = out / 'reference/original_camera_rgb.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
                    '-framerate', str(fps), '-i', str(out / 'reference/rgb/%06d.png'),
                    '-vf', 'scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p',
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-threads', '8',
                    '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709',
                    '-color_trc', 'bt709', '-movflags', '+faststart', str(video)], check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                               '-of', 'json', str(video)]))['streams'][0]
    assert int(probe['nb_frames']) == count
    assert probe['pix_fmt'] == 'yuv420p' and probe['color_space'] == 'bt709'
    assert abs(float(probe['duration']) - count/fps) < 0.01
    process = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'rawvideo',
                                '-pix_fmt', 'rgb24', '-threads', '2', '-'], stdout=subprocess.PIPE)
    rows = []
    chosen = set(np.linspace(0, count-1, min(6, count), dtype=int).tolist())
    sheet = Image.new('RGB', (960, 344*len(chosen)), 'white')
    draw = ImageDraw.Draw(sheet)
    for i in range(count):
        original = np.asarray(Image.open(out / f'reference/rgb/{i:06d}.png'))
        raw = process.stdout.read(original.size)
        assert len(raw) == original.size, f'Truncated video at {i}'
        decoded = np.frombuffer(raw, dtype=np.uint8).reshape(original.shape)
        delta = decoded.astype(np.float32) - original.astype(np.float32)
        rows.append({'frame': i, 'mae_rgb_8bit': float(np.abs(delta).mean()),
                     'channel_bias_rgb_8bit': delta.mean(axis=(0, 1)).tolist()})
        if i in chosen:
            j = sorted(chosen).index(i)
            sheet.paste(Image.fromarray(original).resize((480,320)), (0,j*344+24))
            sheet.paste(Image.fromarray(decoded).resize((480,320)), (480,j*344+24))
            draw.text((4,j*344+4), f'Native PNG / frame {i}', fill='black')
            draw.text((484,j*344+4), 'Decoded MP4 / BT.709 YUV420', fill='black')
    assert process.stdout.read(1) == b''
    assert process.wait() == 0
    max_mae = max(r['mae_rgb_8bit'] for r in rows)
    max_bias = max(abs(v) for r in rows for v in r['channel_bias_rgb_8bit'])
    assert max_mae < 4.0 and max_bias < 2.0, (max_mae, max_bias)
    sheet.save(out / 'reference/color_validation.jpg', quality=95)
    write_json(out / 'validation.json', {'status': 'passed', 'frames': count,
               'full_video_decode': True, 'max_frame_mae_rgb_8bit': max_mae,
               'max_abs_channel_bias_rgb_8bit': max_bias, 'video_stream': probe,
               'frames_validation': rows, 'note': 'MP4 is lossy; native PNGs are authoritative.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PROJECT/'datasets/ai2thor/FloorPlan209')
    parser.add_argument('--frames', type=int, default=240)
    parser.add_argument('--fps', type=int, default=20)
    parser.add_argument('--encode-only', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
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
                  platform=CloudRendering, scene='FloorPlan209', width=1440, height=960,
                  fieldOfView=70, quality='Ultra', snapToGrid=False,
                  renderDepthImage=True, renderInstanceSegmentation=True,
                  server_timeout=90, server_start_timeout=120)
    lengths = np.linalg.norm(np.diff(WAYPOINTS, axis=0), axis=1)
    cumulative = np.r_[0, np.cumsum(lengths)]
    rows, poses = [], []
    controller = LocalController(**config)
    try:
        assert controller.last_event.metadata['lastActionSuccess']
        y = controller.last_event.metadata['agent']['position']['y']
        for i, t in enumerate(np.linspace(0, cumulative[-1], args.frames)):
            j = min(np.searchsorted(cumulative, t, side='right')-1, len(lengths)-1)
            x, z = WAYPOINTS[j]+(WAYPOINTS[j+1]-WAYPOINTS[j])*(t-cumulative[j])/lengths[j]
            yaw = math.degrees(math.atan2(-4.3-x, -2.6-z)) % 360
            event = controller.step(action='TeleportFull', position={'x':float(x),'y':y,'z':float(z)},
                                    rotation={'x':0,'y':yaw,'z':0}, horizon=12, standing=True)
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
    write_json(out/'reference/manifest.json', {'dataset':'ai2thor','scene':'FloorPlan209',
               'build':BUILD,'width':1440,'height':960,'fps':args.fps,'frames':rows,
               'source':'Fresh native event.frame RGB; no grading or channel swap'})
    write_json(out/'ground_truth/cameras.json', {'coordinate_system':'Unity world, Y up; cameraHorizon positive down',
               'width':1440,'height':960,'vertical_fov_degrees':70,'frames':poses})
    write_json(out/'capture_config.json', {k:str(v) if k=='platform' else v for k,v in config.items()})
    write_json(out/'ground_truth/trajectory.json', {'waypoints_xz':WAYPOINTS.tolist(),
               'look_at_xz':[-4.3,-2.6],'horizon_degrees':12,'frames':args.frames,
               'source':'Same waypoint trajectory as original comparison capture'})
    encode(out, args.frames, args.fps)
    (out/'README.txt').write_text(
        'FloorPlan209: fresh original AI2-THOR reference and synchronized ground truth.\n'
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
        'Regenerate with envs/ai2thor/bin/python agen3d/src/rebuild_floorplan209.py --output NEW_DIR\n')
    print('COMPLETE', out, flush=True)


if __name__ == '__main__':
    main()
