"""没配上任何真值的重建实例的人工核对表：每个实例一张对比图 + index.json + 能在本地直接打开的 index.html。

实例列表用打分的那一份（export/objects.json 过 evaluate.filter_predictions），减去 score_sim3.json 里 rows 的 pred_id。
每张图三格：左 = 源视频帧（perception/<scene>/hd/frames）在 hd.best_view 选的那一帧上的裁剪，画出框的 12 条棱；
中 = 同一台相机、同一个裁剪窗下 scene.blend 的渲染（scripts/blender_render_views.py，Workbench，按大小上色），画同样的棱；
右 = 整帧缩略图，标出裁剪窗。每次运行只起一个 Blender 进程，一个接一个跑。
另外从真值里列出每个实例附近的目标（配给了谁、过没过配对门槛），给人和预标参考。

用法：PYTHONPATH=src .runtime/venv/bin/python scripts/unmatched_audit.py [--skip-images] runs/A1-claude/42897538/0 ...
输出 results/unmatched_audit/{img/*.jpg, index.json, index.html}；同目录有 prelabels.json（{key: {"prelabel", "reason"}}，
外加可选的 "_meta"）就并进 index.json 和页面（"模型预标"）。--skip-images：不渲染、不重画图，只重写 index.json / index.html。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from smallobj import align, boxes, evaluate, handoff, hd, score
from smallobj.export_blend import BLENDER

PROJ = Path(__file__).resolve().parent.parent
OUT = PROJ / "results" / "unmatched_audit"
CHOICES = {"unlabeled": "视频里有，CA-1M 没标", "misplaced": "位置或尺寸偏了，配不上",
           "duplicate": "重复建了", "absent": "视频里没有"}
PANEL_WH = (560, 420)
OUTLINE = (255, 0, 220)
BLENDER_TIMEOUT_S = 150   # 一次运行的全部裁剪视图 + 辅助脚本自带的整体图；超时就放弃这次运行的渲染
GT_NEAR_M = 0.6


def _font(size):
    for f in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _key(arm, sid, oid):
    return f"{arm}_{sid}_" + re.sub(r"[^A-Za-z0-9_.-]+", "-", oid)


def audit_view(rec: dict, cams: dict, depths: dict, min_visible: float = 0.5):
    """核对用的那一帧：先只看按深度估计没被挡住一半以上的帧（handoff.visible_fraction，隔着墙的帧不要），
    在里面取 hd.best_view 的分数（画面内面积 ×（1 − 截断），框被切掉一大半的近景不选）× 可见比例² 最大的；
    一帧都没有（框整个在墙后面，或者框本身摆进了墙里）就在全部帧里按 hd.best_view 的分数取。交接记录里的 views 只按画面内面积排，
    第一帧常常只拍到框的一个角，或者隔着一堵墙。返回 {"frame", "bbox_xyxy", "truncation", "visible_frac"} 或 None。"""
    cands = []
    for f in cams["frames"]:
        xyxy, trunc = hd.project_box(rec, f, cams["size_wh"])
        if xyxy is None or trunc >= 1.0:
            continue
        vis = handoff.visible_fraction(rec, f, cams["size_wh"], depths[int(f["source_frame"])])
        score = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1]) * (1 - trunc) ** 2
        ok = vis >= min_visible
        cands.append((ok, score * vis ** 2 if ok else score, {"frame": int(f["source_frame"]), "bbox_xyxy": xyxy,
                                                              "truncation": round(trunc, 3), "visible_frac": round(vis, 2)}))
    return max(cands, key=lambda c: c[:2])[2] if cands else None


def collect(run: Path) -> dict:
    """一次运行里没配上真值的实例，带交接记录里的支撑 / 源帧，和真值坐标系里附近的目标。"""
    arm, sid = run.parts[-3], run.parts[-2]
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    sc = json.loads((run / "score_sim3.json").read_text())
    preds = boxes.load(run / "export" / "objects.json")
    counted = evaluate.filter_predictions(preds)
    if len(counted) != sc["n_pred"]:
        raise SystemExit(f"{run}：算分实例 {len(counted)} 个，和 score_sim3.json 的 n_pred = {sc['n_pred']} 对不上")
    un = handoff.unmatched(counted, sc["rows"])
    record = {o["id"]: o for o in handoff.build(run)["objects"]}
    pdir = handoff.perception_dir(run)
    cams = hd.load(pdir / "hd")
    by_frame = {int(f["source_frame"]): f for f in cams["frames"]}
    depths = {k: np.load(pdir / "hd" / "depth" / f"{k:06d}.npy") for k in by_frame}
    # 真值坐标系里的邻居：和打分同一个变换；顺手核对重新配对的结果和 score_sim3.json 一致
    scene_dir = PROJ / "scenes" / sid
    gts = boxes.load(scene_dir / "gt" / "boxes.json")
    tf = align.pipeline_to_gt(pdir / "bundle", scene_dir, with_scale=True)
    moved = {p["object_id"]: p for p in score.prepare_predictions(preds, tf, th)}
    rows = {r["gt_id"]: r for r in sc["rows"]}
    again = {r["gt_id"]: r.get("pred_id") for r in evaluate.outcomes(list(moved.values()), gts, th)}
    same = again == {k: r.get("pred_id") for k, r in rows.items()}
    items = []
    for p in un:
        oid, o, m = p["object_id"], record[p["object_id"]], moved[p["object_id"]]
        near = []
        for g in gts:
            d = float(np.linalg.norm(np.subtract(m["center"], g["center"])))
            if d <= GT_NEAR_M or (evaluate.dhat(m, g) <= 1.0 and max(g["size"]) < 6.0):   # 整层地面 / 天花板那种大框不列
                r = rows[g["object_id"]]
                near.append({"gt_id": g["object_id"][:8], "category": g["category"], "dist_m": round(d, 3),
                             "longest_m": round(max(g["size"]), 3), "longest_ratio": round(max(m["size"]) / max(g["size"]), 2),
                             "passes_gate": bool(evaluate._loose(m, g, th)), "D": r["D"], "matched_pred": r.get("pred_id")})
        near.sort(key=lambda n: n["dist_m"])
        around = [{"category": g["category"], "size": [round(v, 2) for v in g["size"]], "D": rows[g["object_id"]]["D"],
                   "matched_pred": rows[g["object_id"]].get("pred_id")}
                  for g in gts if boxes.contains(g, [m["center"]], margin=0.03)[0] and max(g["size"]) < 6.0]
        overlap = []
        for q in counted:
            if q is not p:
                iou = evaluate.iou3d(p, q)
                if iou >= 0.05:
                    overlap.append({"id": q["object_id"], "category": q.get("category"), "iou": round(iou, 2)})
        overlap.sort(key=lambda n: -n["iou"])
        view = audit_view(p, cams, depths)
        if view is not None:
            view["image"] = handoff._rel(pdir / "hd" / "frames" / f"{view['frame']:06d}.png", PROJ)
        items.append({"key": _key(arm, sid, oid), "run": handoff._rel(run, PROJ), "arm": arm, "scene": sid, "id": oid,
                      "category": o["category"], "size": [round(v, 3) for v in o["size"]],
                      "center": [round(v, 3) for v in o["center"]], "yaw": round(o["yaw"], 4),
                      "bin": evaluate.size_bin(m, th["bin_edges_m"]),
                      "support": o["support"], "inside": o["inside"], "from_inventory": o["from_inventory"],
                      "frame": view["frame"] if view else None, "frame_image": view["image"] if view else None,
                      "truncation": view["truncation"] if view else None,
                      "visible_frac": view["visible_frac"] if view else None,
                      "gt_nearby": near[:3], "gt_containing": around[:2], "pred_overlap": overlap[:2],
                      "image": f"img/{_key(arm, sid, oid)}.jpg", "render": None,
                      "prelabel": None, "prelabel_reason": None, "label": "", "note": "",
                      "_rec": p, "_view": view, "_cam": by_frame.get(view["frame"]) if view else None})
    return {"run": run, "arm": arm, "scene": sid, "n_pred": sc["n_pred"], "n_matched": sc["n_pred"] - len(un),
            "items": items, "size_wh": cams["size_wh"], "rescored_same": same}


def render_crops(run: Path, items: list, size_wh, tmp: Path) -> dict:
    """一个 Blender 进程渲染这次运行的全部裁剪视图；返回 {key: png 路径}（失败或超时返回空）。"""
    views = []
    for it in items:
        if it["_view"] is None:
            continue
        it["_window"] = handoff.crop_window(it["_view"]["bbox_xyxy"], size_wh, aspect=PANEL_WH[0] / PANEL_WH[1])
        K, wh = handoff.crop_view(it["_cam"]["K"], it["_window"], out_w=PANEL_WH[0])
        views.append({"name": it["key"], "c2w": it["_cam"]["c2w"], "K": K, "size_wh": wh})
    if not views:
        return {}
    spec = {"views": views, "out_dir": str(tmp), "scale": 1.0}
    (tmp / "spec.json").write_text(json.dumps(spec))
    try:
        cp = subprocess.run([str(BLENDER), "-b", str(run / "scene.blend"), "--python",
                             str(PROJ / "scripts" / "blender_render_views.py"), "--", str(tmp / "spec.json")],
                            capture_output=True, text=True, timeout=BLENDER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"{run}：Blender 超过 {BLENDER_TIMEOUT_S} s，放弃", flush=True)
        return {}
    if cp.returncode != 0:
        print(f"{run}：渲染失败 {cp.stderr[-300:]}", flush=True)
    return {v["name"]: tmp / f"{v['name']}.png" for v in views if (tmp / f"{v['name']}.png").exists()}


def _draw_edges(im, rec, cam, window):
    x0, y0, x1, y1 = window
    sx, sy = im.width / (x1 - x0), im.height / (y1 - y0)
    d = ImageDraw.Draw(im)
    for (ua, va), (ub, vb) in handoff.project_edges(rec, cam):
        pts = [(float(np.clip((u - x0) * sx, -1e4, 1e4)), float(np.clip((v - y0) * sy, -1e4, 1e4))) for u, v in ((ua, va), (ub, vb))]
        d.line(pts, fill=OUTLINE, width=2)


def compose(it: dict, render_png, size_wh, out: Path):
    """左：源帧裁剪；中：同机位渲染（没有就灰底说明）；右：整帧缩略图。上面一行说明。"""
    pw, ph = PANEL_WH
    head, gap = 34, 6
    frame = Image.open(PROJ / it["frame_image"]).convert("RGB")
    win = it["_window"]
    left = frame.crop([int(round(v)) for v in win]).resize((pw, ph), Image.LANCZOS)
    _draw_edges(left, it["_rec"], it["_cam"], win)
    if render_png is not None:
        mid = Image.open(render_png).convert("RGB").resize((pw, ph), Image.LANCZOS)
        _draw_edges(mid, it["_rec"], it["_cam"], win)
    else:
        mid = Image.new("RGB", (pw, ph), (225, 225, 225))
        ImageDraw.Draw(mid).text((20, ph // 2 - 12), "没有渲染出来", fill=(90, 90, 90), font=_font(22))
    tw = int(round(ph * size_wh[0] / size_wh[1]))
    thumb = frame.resize((tw, ph), Image.LANCZOS)
    full = [0, 0, size_wh[0], size_wh[1]]
    _draw_edges(thumb, it["_rec"], it["_cam"], full)
    s = ph / size_wh[1]
    ImageDraw.Draw(thumb).rectangle([win[0] * s, win[1] * s, win[2] * s - 1, win[3] * s - 1], outline=(255, 235, 0), width=2)
    sheet = Image.new("RGB", (pw * 2 + tw + gap * 2, head + ph), "white")
    d = ImageDraw.Draw(sheet)
    for x, im, name in ((0, left, f"视频帧 {it['frame']:06d}（裁剪）"), (pw + gap, mid, "同机位渲染（同一裁剪窗）"),
                        (2 * (pw + gap), thumb, "整帧（黄框 = 裁剪窗）")):
        sheet.paste(im, (x, head))
        d.text((x + 6, 4), name, fill=(40, 40, 40), font=_font(20))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=86)


PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>没配上真值的实例核对</title>
<style>
:root { --bg: #f5f4f1; --card: #ffffff; --ink: #1f2328; --muted: #646b74; --line: #d9d6cf; --accent: #2f6db3;
        --pre-bg: #f3f0e6; --pre-line: #b9ae8c; --done: #2d7d4f; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #17181a; --card: #222427; --ink: #e7e7e4; --muted: #9aa1aa; --line: #3a3d42; --accent: #7fb2ee;
          --pre-bg: #2b2a24; --pre-line: #6f684f; --done: #6fca94; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.55 "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
header { position: sticky; top: 0; z-index: 5; background: var(--bg); border-bottom: 1px solid var(--line); padding: 10px 16px; }
.bar { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; max-width: 1500px; margin: 0 auto; }
h1 { font-size: 18px; margin: 0; }
.count { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--done); }
button, select { font: inherit; color: var(--ink); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 5px 12px; cursor: pointer; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
main { max-width: 1500px; margin: 0 auto; padding: 12px 16px 60px; }
.intro { color: var(--muted); margin: 6px 0 14px; max-width: 110ch; }
.sw { display: inline-block; width: 11px; height: 11px; border-radius: 2px; margin: 0 3px 0 8px; vertical-align: -1px; }
.card { background: var(--card); border: 1px solid var(--line); border-left: 5px solid var(--line); border-radius: 8px; padding: 12px; margin: 0 0 16px; }
.card.done { border-left-color: var(--done); }
.card h2 { font-size: 16px; margin: 0 0 6px; overflow-wrap: anywhere; }
.card h2 small { font-weight: 400; color: var(--muted); }
.card img { display: block; width: 100%; height: auto; border: 1px solid var(--line); border-radius: 4px; background: #ddd; }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px 24px; margin-top: 10px; }
@media (max-width: 860px) { .cols { grid-template-columns: 1fr; } }
dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 2px 12px; margin: 0; font-size: 14px; }
dt { color: var(--muted); }
dd { margin: 0; overflow-wrap: anywhere; }
.pre { background: var(--pre-bg); border: 1px dashed var(--pre-line); border-radius: 6px; padding: 6px 10px; margin: 0 0 10px; font-size: 14px; }
.pre b { font-weight: 600; }
.pre .tag { display: inline-block; font-size: 12px; border: 1px solid var(--pre-line); border-radius: 10px; padding: 0 8px; margin-right: 6px; }
fieldset { border: 0; padding: 0; margin: 0; }
legend { padding: 0; font-weight: 600; margin-bottom: 4px; }
label.opt { display: block; padding: 3px 0; cursor: pointer; }
textarea { width: 100%; min-height: 44px; margin-top: 8px; font: inherit; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px; }
.clear { font-size: 13px; padding: 2px 8px; margin-top: 6px; }
.hidden { display: none; }
</style>
</head>
<body>
<header><div class="bar">
  <h1>没配上真值的实例核对</h1>
  <span>已标 <span class="count" id="done">0</span> / <span id="total">0</span></span>
  <select id="f-run" aria-label="筛选运行"><option value="">全部运行</option></select>
  <label><input type="checkbox" id="f-todo"> 只看没标的</label>
  <button class="primary" id="dl">下载答案（JSON）</button>
</div></header>
<main>
<p class="intro">每张图：左 = 源视频帧的裁剪，中 = 同一台相机下的重建渲染，右 = 整帧（黄框是裁剪窗）；洋红线是这个实例的框。
渲染按大小上色：<span class="sw" style="background:#e64d45"></span>XS &lt; 0.2 m<span class="sw" style="background:#f59e33"></span>S 0.2–0.5 m<span class="sw" style="background:#4587d1"></span>M 0.5–1.5 m<span class="sw" style="background:#5ca86b"></span>L ≥ 1.5 m<span class="sw" style="background:#dbd9d4"></span>墙 / 地面。
"模型预标"是 Claude 看图给的初步猜测，只供参考；下面的单选是你的判断，一开始都是空的。答案存在这个浏览器里（localStorage），标完点"下载答案"。</p>
<div id="cards"></div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const CHOICES = DATA.choices, ITEMS = DATA.items, STORE = 'unmatched_audit_v1';
let answers = {};
try { answers = JSON.parse(localStorage.getItem(STORE) || '{}') || {}; } catch (e) { answers = {}; }
const save = () => { try { localStorage.setItem(STORE, JSON.stringify(answers)); } catch (e) {} };
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const get = k => answers[k] || (answers[k] = {label: '', note: ''});
const cm = v => (v * 100).toFixed(v < 0.1 ? 1 : 0);

function meta(it) {
  const rows = [
    ['运行', it.run], ['类别', it.category || '—'],
    ['框大小', `${cm(it.size[0])} × ${cm(it.size[1])} × ${cm(it.size[2])} cm（${it.bin} 档）`],
    ['支撑', (it.support === null ? '无（挂墙 / 悬空 / 框里看不出）' : it.support === 'floor' ? '地面' : it.support) + (it.inside ? `；在 ${it.inside} 的框里` : '')],
    ['来自清单', it.from_inventory === null ? '—（这组没有清单）' : it.from_inventory ? '是' : '否'],
    ['源帧', it.frame === null ? '没有哪一帧看得到' : `${String(it.frame).padStart(6, '0')}（框出画 ${Math.round(it.truncation * 100)}%，按深度估计没被挡住 ${Math.round(it.visible_frac * 100)}%）`],
    ['附近的真值', it.gt_nearby.length ? it.gt_nearby.map(g =>
      `${esc(g.category)}：中心距 ${g.dist_m.toFixed(2)} m，最长边 ${cm(g.longest_m)} cm（本实例是它的 ${g.longest_ratio} 倍），` +
      (g.matched_pred ? `已配给 ${esc(g.matched_pred)}（${g.D}）` : '没人配上') + (g.passes_gate ? '，过得了配对门槛' : '，过不了配对门槛')).join('<br>') : '0.6 m 内没有'],
    ['包着它的真值', it.gt_containing.length ? it.gt_containing.map(g =>
      `${esc(g.category)}（${g.size.map(v => cm(v)).join(' × ')} cm）` + (g.matched_pred ? `，已配给 ${esc(g.matched_pred)}（${g.D}）` : '，没人配上')).join('<br>') : '没有'],
    ['和它重叠的实例', it.pred_overlap.length ? it.pred_overlap.map(p => `${esc(p.id)}（IoU ${p.iou}）`).join('，') : '没有'],
  ];
  return '<dl>' + rows.map(([k, v], i) => `<dt>${k}</dt><dd>${i < 6 ? esc(v) : v}</dd>`).join('') + '</dl>';
}

function card(it, n) {
  const el = document.createElement('section');
  el.className = 'card'; el.dataset.key = it.key; el.dataset.run = it.run;
  const pre = it.prelabel ? `<div class="pre"><span class="tag">模型预标</span><b>${esc(CHOICES[it.prelabel] || it.prelabel)}</b> — ${esc(it.prelabel_reason || '')}</div>`
                          : '<div class="pre"><span class="tag">模型预标</span>还没有</div>';
  el.innerHTML = `<h2>${n}. ${esc(it.id)} <small>${esc(it.arm)} · ${esc(it.scene)}</small></h2>
    <a href="${esc(it.image)}" target="_blank" rel="noopener"><img loading="lazy" src="${esc(it.image)}" alt="${esc(it.id)}：视频帧和同机位渲染"></a>
    <div class="cols"><div>${meta(it)}</div><div>${pre}
      <fieldset><legend>你的判断</legend>
      ${Object.entries(CHOICES).map(([c, t]) => `<label class="opt"><input type="radio" name="r-${esc(it.key)}" value="${c}"> ${esc(t)}</label>`).join('')}
      </fieldset>
      <button class="clear" type="button">清空这一条</button>
      <textarea placeholder="备注（可不填）" aria-label="备注"></textarea></div></div>`;
  const a = get(it.key);
  el.querySelectorAll('input[type=radio]').forEach(r => {
    r.checked = a.label === r.value;
    r.addEventListener('change', () => { get(it.key).label = r.value; save(); refresh(); });
  });
  const ta = el.querySelector('textarea');
  ta.value = a.note || '';
  ta.addEventListener('input', () => { get(it.key).note = ta.value; save(); });
  el.querySelector('.clear').addEventListener('click', () => {
    answers[it.key] = {label: '', note: ''}; ta.value = '';
    el.querySelectorAll('input[type=radio]').forEach(r => { r.checked = false; });
    save(); refresh();
  });
  return el;
}

function refresh() {
  const run = document.getElementById('f-run').value, todo = document.getElementById('f-todo').checked;
  let done = 0;
  document.querySelectorAll('.card').forEach(el => {
    const isDone = !!(answers[el.dataset.key] && answers[el.dataset.key].label);
    done += isDone;
    el.classList.toggle('done', isDone);
    el.classList.toggle('hidden', (run && el.dataset.run !== run) || (todo && isDone));
  });
  document.getElementById('done').textContent = done;
}

const cards = document.getElementById('cards'), sel = document.getElementById('f-run');
ITEMS.forEach((it, i) => cards.appendChild(card(it, i + 1)));
[...new Set(ITEMS.map(it => it.run))].forEach(r => { const o = document.createElement('option'); o.value = o.textContent = r; sel.appendChild(o); });
document.getElementById('total').textContent = ITEMS.length;
sel.addEventListener('change', refresh);
document.getElementById('f-todo').addEventListener('change', refresh);
document.getElementById('dl').addEventListener('click', () => {
  const out = {exported_at: new Date().toISOString(), choices: CHOICES,
    n_total: ITEMS.length, n_done: ITEMS.filter(it => get(it.key).label).length,
    answers: ITEMS.map(it => ({key: it.key, run: it.run, id: it.id, label: get(it.key).label,
      label_text: CHOICES[get(it.key).label] || '', note: get(it.key).note || '', prelabel: it.prelabel}))};
  const url = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: 'application/json'}));
  const a = document.createElement('a');
  a.href = url; a.download = 'unmatched_audit_answers.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
refresh();
</script>
</body>
</html>
"""


def write_index(runs: list, out_dir: Path = OUT):
    """index.json（每个实例一条，label 留空）和内嵌同一份数据的 index.html。"""
    pre_path = out_dir / "prelabels.json"
    pre = json.loads(pre_path.read_text()) if pre_path.exists() else {}
    items = []
    for r in runs:
        for it in r["items"]:
            it = {k: v for k, v in it.items() if not k.startswith("_")}
            p = pre.get(it["key"])
            if p:
                if p["prelabel"] not in CHOICES:
                    raise SystemExit(f"prelabels.json：{it['key']} 的 prelabel {p['prelabel']!r} 不在 {list(CHOICES)} 里")
                it["prelabel"], it["prelabel_reason"] = p["prelabel"], p["reason"]
            items.append(it)
    index = {"generator": "scripts/unmatched_audit.py", "handoff_version": handoff.VERSION, "choices": CHOICES,
             "fields": {"label": "人的判断（choices 的键），一开始是空串；页面里标完用\"下载答案\"导出，不回写这个文件",
                        "prelabel": "Claude 看图给的初步猜测（choices 的键）和一句理由 prelabel_reason；不是人工结论",
                        "support": "同 <run>/objects.json（smallobj.handoff）",
                        "gt_nearby": "真值坐标系里中心距 ≤ 0.6 m 或 d̂ ≤ 1（最长边 < 6 m）的目标，最多 3 个：配给了谁、D 结局、这一对过不过宽松门槛",
                        "gt_containing": "框里包着这个实例中心的真值目标（最长边 < 6 m 的），最多 2 个：多半是它所属的那件大东西",
                        "frame": "核对图用的源帧：按 Pi3X 深度估计没被挡住一半以上（visible_frac ≥ 0.5）的帧里，画面内面积 ×（1 − 截断）× 可见比例² 最大的；没有这样的帧就在全部帧里按前两项取",
                        "render": "camera = 用源帧那台相机渲染的；none = 没渲染出来"},
             "prelabel_meta": pre.get("_meta"),
             "runs": [{"run": handoff._rel(r["run"], PROJ), "n_pred": r["n_pred"], "n_matched": r["n_matched"],
                       "n_unmatched": len(r["items"])} for r in runs],
             "n": len(items), "items": items}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
    data = json.dumps({"choices": CHOICES, "items": items}, ensure_ascii=False).replace("</", "<\\/")
    (out_dir / "index.html").write_text(PAGE.replace("__DATA__", data))
    return index


def main(argv):
    skip = "--skip-images" in argv
    run_dirs = [Path(a).resolve() for a in argv if not a.startswith("--")]
    runs = [collect(r) for r in run_dirs]
    for r in runs:
        print(f"{r['arm']} {r['scene']}：算分实例 {r['n_pred']}，配上 {r['n_matched']}，没配上 {len(r['items'])}；"
              f"重新配对和 score_sim3.json {'一致' if r['rescored_same'] else '不一致'}", flush=True)
        if skip:
            for it in r["items"]:
                it["render"] = "camera" if (OUT / it["image"]).exists() and it["_view"] else "none"
            continue
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            pngs = render_crops(r["run"], r["items"], r["size_wh"], Path(tmp))   # 一次一个 Blender 进程
            for it in r["items"]:
                if it["_view"] is None:
                    it["render"], it["image"] = "none", None
                    continue
                it["render"] = "camera" if it["key"] in pngs else "none"
                compose(it, pngs.get(it["key"]), r["size_wh"], OUT / it["image"])
    index = write_index(runs)
    by_arm = {}
    for it in index["items"]:
        by_arm[it["arm"]] = by_arm.get(it["arm"], 0) + 1
    print("没配上的实例：", by_arm, "合计", index["n"], "；同机位渲染", sum(it["render"] == "camera" for it in index["items"]))
    print(OUT / "index.html")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
