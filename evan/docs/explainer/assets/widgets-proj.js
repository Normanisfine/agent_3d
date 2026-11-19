/* 期末项目讲解页：交互组件（第 5 章）。注册到 window.RW，由 review.js 挂载到 [data-widget] 上。
   颜色只用 CSS 变量和 review.css 里的 svg 填色 class，深浅色都能看清。 */
(function () {
  "use strict";
  var RW = window.RW, U = RW && RW._u;
  if (!RW || !U) return;

  /* 5.2 节：小物体在画面里占几个像素。
     针孔模型：f = (W/2) / tan(视角/2)，跨度 = f × 大小 / 距离，面积按正方形估 ≈ 跨度²。
     默认 10 cm、2 m、60°：574 宽 f≈497.1、跨度≈24.9 px；1024 宽≈44.3 px；1920 宽≈83.1 px。 */
  RW["p-pixels"] = function (root) {
    var frames = [
      { name: "AHa-3D 用的分辨率", note: "Pi3X 默认，≤ 25.5 万像素", w: 574, h: 434 },
      { name: "CA-1M 原帧", note: "我们的“高清帧”", w: 1024, h: 768 },
      { name: "ARKitScenes 原始视频", note: "我们不下载", w: 1920, h: 1440 }
    ];
    var SEE = 100, GEN = 200, CAP = 150;
    var out = U.frame(root, "小物体在画面里占几个像素",
      "拖动三个滑块。默认值（10 cm、2 m、60°）和下面手算框里的数一致。60° 是 iPad 主摄量级的估计值，不是标定值。",
      U.slider("s", "物体大小（cm）", 1, 100, 1, 10) +
      U.slider("d", "距离（m）", 0.3, 8, 0.1, 2) +
      U.slider("fov", "水平视角（度）", 30, 120, 1, 60));

    function verdict(a) {
      if (a < SEE) return '<span class="w-no">过不了“看得见”</span>';
      if (a < GEN) return '<span style="color:var(--amber);font-weight:650">看得见；在这个分辨率上生成会 too_small</span>';
      return '<span class="w-ok">可以送去生成</span>';
    }

    function squares(spans) {
      var colW = 170, W = colW * spans.length + 130, H = CAP + 46, base = CAP + 10;
      var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" style="max-width:100%;height:auto" role="img" aria-label="物体在三种分辨率下的像素大小，按屏幕像素一比一画">';
      s += '<g font-size="12">';
      spans.forEach(function (sp, i) {
        var side = Math.min(sp, CAP), x = colW * i + (colW - side) / 2;
        var cls = sp * sp < SEE ? "f4" : (sp * sp < GEN ? "f3" : "f2");
        s += '<rect x="' + x.toFixed(1) + '" y="' + (base - side).toFixed(1) + '" width="' + side.toFixed(1) + '" height="' + side.toFixed(1) + '" class="' + cls + ' stroke"/>';
        s += '<text x="' + (colW * i + colW / 2) + '" y="' + (base + 18) + '" text-anchor="middle">' + frames[i].w + ' 宽：' + U.f(sp, 1) + ' px' + (sp > CAP ? '（截断）' : '') + '</text>';
      });
      var rx = colW * spans.length + 20, s100 = Math.sqrt(SEE), s200 = Math.sqrt(GEN);
      s += '<rect x="' + rx + '" y="' + (base - s100).toFixed(1) + '" width="' + s100.toFixed(1) + '" height="' + s100.toFixed(1) + '" class="f4" style="stroke:var(--accent);stroke-width:1.5"/>';
      s += '<text x="' + (rx + 18) + '" y="' + (base - 2) + '">100 px²</text>';
      s += '<rect x="' + rx + '" y="' + (base - 40 - s200).toFixed(1) + '" width="' + s200.toFixed(1) + '" height="' + s200.toFixed(1) + '" class="f3" style="stroke:var(--amber);stroke-width:1.5"/>';
      s += '<text x="' + (rx + 22) + '" y="' + (base - 42) + '">200 px²</text>';
      s += '<text x="' + rx + '" y="' + (base + 18) + '">门槛</text>';
      return s + '</g></svg>';
    }

    U.bind(root, function () {
      var cm = U.get(root, "s"), d = U.get(root, "d"), fov = U.get(root, "fov");
      U.setv(root, "s", cm.toFixed(0));
      U.setv(root, "d", d.toFixed(1));
      U.setv(root, "fov", fov.toFixed(0) + "°");
      var size = cm / 100, t = Math.tan(fov * Math.PI / 360);
      var h = '<table><tr><th>画面</th><th>宽 × 高</th><th>焦距 f（px）</th><th>跨度（px）</th><th>面积（px²）</th><th>判定</th></tr>';
      var spans = [];
      frames.forEach(function (fr) {
        var f = (fr.w / 2) / t, span = f * size / d, area = span * span;
        spans.push(span);
        var cls = area < SEE ? "bad" : (area < GEN ? "hl" : "good");
        h += '<tr><td style="text-align:left">' + fr.name + '<br><span class="w-note">' + fr.note + '</span></td><td>' + fr.w + ' × ' + fr.h +
          '</td><td>' + U.f(f, 1) + '</td><td>' + U.f(span, 1) + '</td><td class="' + cls + '">' + Math.round(area).toLocaleString("en-US") +
          '</td><td>' + verdict(area) + (span > fr.w ? '<br><span class="w-note">比整个画面还宽</span>' : '') + '</td></tr>';
      });
      h += '</table>';
      var dist = function (fr, thr) { return ((fr.w / 2) / t) * size / Math.sqrt(thr); };
      h += '<p class="w-note">574 宽（A0、A1 的“看得见”；高清帧消融在这个尺寸上生成）：离相机超过 <b>' + U.f(dist(frames[0], GEN), 2) +
        ' m</b> 面积跌破 200 px²，超过 <b>' + U.f(dist(frames[0], SEE), 2) + ' m</b> 跌破 100 px²。</p>';
      h += '<p class="w-note">1024 宽（P0 和 A2 起的“看得见”；A3 在 1024 宽上生成）：超过 <b>' + U.f(dist(frames[1], GEN), 2) +
        ' m</b> 跌破 200 px²（生成返回 too_small），超过 <b>' + U.f(dist(frames[1], SEE), 2) + ' m</b> 跌破 100 px²。面积按正对相机的正方形估，是最好情况；真实可见面积通常更小。</p>';
      h += '<p class="w-note">下面的方块按屏幕像素一比一画（窄屏会整体缩小），颜色和判定一致：绿色可以送去生成，橙色在这个分辨率上生成会 too_small，红色过不了“看得见”。右边两个小方块是 100 px² 和 200 px² 两道门槛。</p>';
      out.innerHTML = h + squares(spans);
    });
  };
})();
