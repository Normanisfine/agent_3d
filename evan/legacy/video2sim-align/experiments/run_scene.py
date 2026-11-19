"""One scene end to end: score SAM3+PCA boxes, refine each with ICP, score again, draw overlays.

Usage: python experiments/run_scene.py --scene data/arkitscenes/scenes/<id> \
         --raw data/arkitscenes/raw/Validation/<id> --lift runs/<...>/lift --out runs/<...>/eval
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval'))
from v2s import arkit, boxes  # noqa: E402
from aligners import icp  # noqa: E402
import score  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', type=Path, required=True)
    ap.add_argument('--raw', type=Path, required=True)
    ap.add_argument('--lift', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    gt_path = a.scene / 'gt_boxes.json'
    cams = json.loads((a.lift / 'cams.json').read_text())
    sam = boxes.load(a.lift / 'sam_pca_boxes.json')

    refined, log = [], {}
    for rec in sam:
        pts = np.load(a.lift / 'obj_points' / f"{rec['object_id']}.npy")
        out, info = icp.align(rec, pts)
        refined.append(out)
        log[rec['object_id']] = info
    boxes.save(refined, a.out / 'icp_boxes.json')
    (a.out / 'icp_log.json').write_text(json.dumps(log, indent=1) + '\n')

    csv_path = a.out / 'scores.csv'
    summary = {}
    for name, path in [('B0_sam_pca', a.lift / 'sam_pca_boxes.json'), ('B0_sam_pca+icp', a.out / 'icp_boxes.json')]:
        for mode in ('rigid', 'sim3'):
            for ca in (False, True):
                res, aligned = score.run(path, gt_path, cams['pred'], cams['gt'], mode=mode, class_aware=ca)
                tag = f"{name}|{mode}|{'class' if ca else 'agnostic'}"
                score.append_csv(csv_path, tag, path, res)
                summary[tag] = {k: res[k] for k in ('f1@0.5', 'f1@1.0', 'recall@0.5', 'precision@0.5',
                                                    'center_err_m_median', 'size_log_ratio_median',
                                                    'yaw_err_deg_median', 'missed_not_detected',
                                                    'missed_misaligned', 'align_rmse_m', 'align_scale')}
                if mode == 'rigid' and not ca:
                    boxes.save(aligned, a.out / f"{name.replace('+', '_')}_in_gt_world.json")
                    summary[tag]['pairs@0.5'] = res['pairs@0.5']
    (a.out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')

    # Overlays: GT green, aligned SAM3+PCA red, aligned ICP blue, on native vga frames.
    fm = json.loads((a.scene / 'frame_map.json').read_text())['frames']
    gt = boxes.load(gt_path)
    pred0 = boxes.load(a.out / 'B0_sam_pca_in_gt_world.json')
    pred1 = boxes.load(a.out / 'B0_sam_pca_icp_in_gt_world.json')
    tiles = []
    for p in (0.15, 0.4, 0.6, 0.85):
        row = fm[int(p * (len(fm) - 1))]
        img = cv2.imread(str(a.raw / 'vga_wide' / row['vga_file']))
        c2w, K = np.array(row['c2w_arkit']), np.array(row['K_vga_native'])
        img = arkit.draw_boxes(img, gt, c2w, K, (0, 200, 0))
        img = arkit.draw_boxes(img, pred0, c2w, K, (0, 0, 255))
        img = arkit.draw_boxes(img, pred1, c2w, K, (255, 120, 0))
        meta = json.loads((a.scene / 'meta.json').read_text())
        rot = arkit.UPRIGHT[meta['sky_direction_from_poses']]
        if rot is not None:
            img = cv2.rotate(img, rot)
        tiles.append(img)
    cv2.imwrite(str(a.out / 'overlay_gt_green_sam_red_icp_blue.jpg'), np.concatenate(tiles, axis=1))
    for tag in summary:
        if tag.endswith('rigid|agnostic') or tag.endswith('sim3|agnostic'):
            s = summary[tag]
            print(f"{tag:32s} F1@0.5={s['f1@0.5']:.3f} F1@1.0={s['f1@1.0']:.3f} R@0.5={s['recall@0.5']:.3f} "
                  f"ctr={s['center_err_m_median']} size={s['size_log_ratio_median']} yaw={s['yaw_err_deg_median']} "
                  f"miss(nodet/misal)={s['missed_not_detected']}/{s['missed_misaligned']}")


if __name__ == '__main__':
    main()
