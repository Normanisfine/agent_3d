"""Check every saved reference/GT pair; optionally compare a previous RGB capture."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--previous-rgb', type=Path)
    args = parser.parse_args()
    root = args.dataset
    manifest = json.loads((root/'reference/manifest.json').read_text())
    cameras = json.loads((root/'ground_truth/cameras.json').read_text())['frames']
    assert len(cameras) == len(manifest['frames'])
    results = []
    for item, camera in zip(manifest['frames'], cameras):
        frame = item['frame_id']
        assert camera['frame_id'] == frame
        path = root/'reference'/item['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
        rgb = np.asarray(Image.open(path))
        shape = (manifest['height'], manifest['width'])
        assert rgb.shape == (*shape, 3)
        with np.load(root/f'ground_truth/depth_m/{frame}.npz') as data:
            depth = data['depth_m']
            assert depth.shape == shape and depth.dtype == np.float32
            assert np.isfinite(depth).all() and depth.min() >= 0 and depth.max() > 0
        seg = np.asarray(Image.open(root/f'ground_truth/instance_segmentation/{frame}.png'))
        assert seg.shape == rgb.shape
        metadata = json.loads((root/f'ground_truth/metadata/{frame}.json').read_text())
        annotations = json.loads((root/f'ground_truth/annotations/{frame}.json').read_text())
        assert metadata['lastActionSuccess'] and metadata['sceneName'] in (manifest['scene'], manifest['scene'] + '_physics')
        assert metadata['cameraPosition'] == camera['cameraPosition']
        assert metadata['objects'] and annotations['object_id_to_color']
        assert all(0 <= count <= shape[0]*shape[1] for count in annotations['mask_pixels'].values())
        row = {'frame':frame,'object_count':len(metadata['objects']),
               'depth_range_m':[float(depth.min()),float(depth.max())]}
        if args.previous_rgb:
            old = np.asarray(Image.open(args.previous_rgb/f'{frame}.png'))
            assert old.shape == rgb.shape
            delta = rgb.astype(np.float32)-old.astype(np.float32)
            row['previous_rgb_mae_8bit'] = float(np.abs(delta).mean())
            row['previous_rgb_channel_bias_8bit'] = delta.mean(axis=(0,1)).tolist()
        results.append(row)
    report = {'status':'passed','frames_checked':len(results),
              'checks':['PNG SHA256','RGB/depth/segmentation sizes','finite meter depth',
                        'metadata action/scene','camera alignment','annotation presence'],
              'frames':results}
    if args.previous_rgb:
        report['mean_previous_rgb_mae_8bit'] = float(np.mean([r['previous_rgb_mae_8bit'] for r in results]))
    (root/'ground_truth_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='frames'},indent=2))


if __name__ == '__main__':
    main()
