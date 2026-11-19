/* CIS 6220 期中复习：交互组件。每个组件注册到 window.RW，由 review.js 挂载到 [data-widget] 上。 */
(function () {
  "use strict";
  var RW = window.RW = window.RW || {};
  var U = RW._u = {};

  /* ---------------- 通用小工具 ---------------- */
  U.f = function (x, d) {
    if (x === Infinity) return "∞";
    if (x === -Infinity) return "−∞";
    if (!isFinite(x)) return String(x);
    d = d == null ? 3 : d;
    var a = Math.abs(x);
    if (a !== 0 && (a >= 1e6 || a < Math.pow(10, -d))) {
      var s = x.toExponential(2).replace("e+", "e").replace("e-", "e−");
      return s;
    }
    return x.toFixed(d);
  };
  U.softmax = function (a) {
    var fin = a.filter(function (v) { return isFinite(v); });
    var m = Math.max.apply(null, fin);
    var e = a.map(function (v) { return isFinite(v) ? Math.exp(v - m) : 0; });
    var s = e.reduce(function (p, q) { return p + q; }, 0);
    return e.map(function (v) { return v / s; });
  };
  U.slider = function (key, label, min, max, step, val) {
    return '<label>' + label + ' <input type="range" data-k="' + key + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + val + '"><span class="w-val" data-v="' + key + '"></span></label>';
  };
  U.check = function (key, label, on) {
    return '<label><input type="checkbox" data-k="' + key + '"' + (on ? " checked" : "") + '> ' + label + '</label>';
  };
  U.select = function (key, label, opts, val) {
    var h = '<label>' + label + ' <select data-k="' + key + '">';
    opts.forEach(function (o) { h += '<option value="' + o[0] + '"' + (String(o[0]) === String(val) ? " selected" : "") + '>' + o[1] + '</option>'; });
    return h + '</select></label>';
  };
  U.get = function (root, key) {
    var el = root.querySelector('[data-k="' + key + '"]');
    if (!el) return null;
    if (el.type === "checkbox") return el.checked;
    if (el.tagName === "SELECT") return el.value;
    return parseFloat(el.value);
  };
  U.setv = function (root, key, text) {
    var el = root.querySelector('[data-v="' + key + '"]');
    if (el) el.textContent = text;
  };
  U.bind = function (root, fn) {
    root.addEventListener("input", fn);
    root.addEventListener("change", fn);
    fn();
  };
  U.frame = function (root, title, intro, controls) {
    root.insertAdjacentHTML("beforeend",
      '<div class="w-title">' + title + '</div>' + (intro ? '<p class="w-intro">' + intro + '</p>' : "") +
      '<div class="w-controls">' + (controls || "") + '</div><div class="w-out"></div>');
    return root.querySelector(".w-out");
  };
  U.table = function (M, o) {
    o = o || {};
    var h = "<table>";
    if (o.cols) { h += "<tr><th></th>"; o.cols.forEach(function (c) { h += "<th>" + c + "</th>"; }); h += "</tr>"; }
    M.forEach(function (row, i) {
      h += "<tr>" + (o.rows ? "<th>" + o.rows[i] + "</th>" : "");
      row.forEach(function (v, j) {
        var cls = o.cls ? o.cls(i, j, v) : "";
        h += '<td' + (cls ? ' class="' + cls + '"' : "") + ">" + (typeof v === "number" ? U.f(v, o.d == null ? 3 : o.d) : v) + "</td>";
      });
      h += "</tr>";
    });
    return h + "</table>";
  };
  U.bars = function (rows) {
    var h = "";
    rows.forEach(function (r) {
      var w = Math.max(0, Math.min(1, r.w)) * 100;
      h += '<div class="bar-row"><span class="bar-lab">' + r.lab + '</span><span class="bar-track"><span class="bar-fill ' + (r.cls || "") + '" style="width:' + w.toFixed(1) + '%;display:block"></span></span><span class="bar-num">' + r.num + '</span></div>';
    });
    return h;
  };
  U.bytes = function (b) {
    var u = ["B", "KB", "MB", "GB", "TB", "PB"], i = 0;
    while (Math.abs(b) >= 1000 && i < u.length - 1) { b /= 1000; i++; }
    return (b >= 100 ? b.toFixed(0) : b >= 10 ? b.toFixed(1) : b.toFixed(2)) + " " + u[i];
  };
  U.big = function (x) {
    var u = ["", "K", "M", "B", "T", "P", "E"], i = 0;
    while (Math.abs(x) >= 1000 && i < u.length - 1) { x /= 1000; i++; }
    return (x >= 100 ? x.toFixed(0) : x >= 10 ? x.toFixed(1) : x.toFixed(2)) + u[i];
  };
  U.mulberry = function (seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  };
  U.gauss = function (rnd) {
    var u = 1 - rnd(), v = rnd();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
  /* 简单折线图：series = [{ys:[], cls:"blue"|"red"|"green"|"grey", label}]，xs 共享 */
  U.plot = function (o) {
    var W = o.w || 520, H = o.h || 220, L = 46, R = 12, T = 12, B = 34;
    var xmin = o.xmin, xmax = o.xmax, ymin = o.ymin, ymax = o.ymax;
    function X(x) { return L + (x - xmin) / (xmax - xmin) * (W - L - R); }
    function Y(y) { return T + (1 - (y - ymin) / (ymax - ymin)) * (H - T - B); }
    var col = { blue: "#0a84ff", red: "#ff453a", green: "#28a745", grey: "#888", amber: "#ff9f0a", violet: "#bf5af2" };
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" style="max-width:100%;height:auto" role="img">';
    s += '<line x1="' + L + '" y1="' + Y(ymin) + '" x2="' + (W - R) + '" y2="' + Y(ymin) + '" class="stroke" stroke-width="1"/>';
    s += '<line x1="' + L + '" y1="' + T + '" x2="' + L + '" y2="' + Y(ymin) + '" class="stroke" stroke-width="1"/>';
    (o.yticks || []).forEach(function (t) { s += '<line x1="' + L + '" y1="' + Y(t) + '" x2="' + (W - R) + '" y2="' + Y(t) + '" stroke="#999" stroke-opacity=".25"/><text x="' + (L - 4) + '" y="' + (Y(t) + 4) + '" font-size="10" text-anchor="end">' + (o.yfmt ? o.yfmt(t) : t) + '</text>'; });
    (o.xticks || []).forEach(function (t) { s += '<text x="' + X(t) + '" y="' + (H - B + 14) + '" font-size="10" text-anchor="middle">' + (o.xfmt ? o.xfmt(t) : t) + '</text>'; });
    if (o.xlabel) s += '<text x="' + ((L + W - R) / 2) + '" y="' + (H - 4) + '" font-size="11" text-anchor="middle">' + o.xlabel + '</text>';
    if (o.ylabel) s += '<text x="12" y="' + (T + (H - T - B) / 2) + '" font-size="11" text-anchor="middle" transform="rotate(-90 12 ' + (T + (H - T - B) / 2) + ')">' + o.ylabel + '</text>';
    o.series.forEach(function (se, k) {
      var pts = [];
      o.xs.forEach(function (x, i) { var y = se.ys[i]; if (isFinite(y)) pts.push(X(x).toFixed(1) + "," + Y(Math.max(ymin, Math.min(ymax, y))).toFixed(1)); });
      s += '<polyline fill="none" stroke="' + (col[se.cls] || se.cls || "#0a84ff") + '" stroke-width="2.2"' + (se.dash ? ' stroke-dasharray="5 4"' : "") + ' points="' + pts.join(" ") + '"/>';
      if (se.label) s += '<text x="' + (W - R - 4) + '" y="' + (T + 14 + 14 * k) + '" font-size="11" text-anchor="end" fill="' + (col[se.cls] || se.cls) + '">' + se.label + '</text>';
    });
    (o.marks || []).forEach(function (m) {
      s += '<line x1="' + X(m.x) + '" y1="' + T + '" x2="' + X(m.x) + '" y2="' + Y(ymin) + '" stroke="#ff453a" stroke-dasharray="3 3"/>';
      if (m.label) s += '<text x="' + (X(m.x) + 4) + '" y="' + (T + 10) + '" font-size="10" fill="#ff453a">' + m.label + '</text>';
    });
    (o.dots || []).forEach(function (d) { s += '<circle cx="' + X(d.x) + '" cy="' + Y(d.y) + '" r="4" fill="' + (col[d.cls] || "#ff453a") + '"/>'; });
    return s + "</svg>";
  };
  U.readMatrix = function (root, name, r, c) {
    var M = [];
    for (var i = 0; i < r; i++) { M.push([]); for (var j = 0; j < c; j++) { var el = root.querySelector('input[data-m="' + name + '"][data-i="' + i + '"][data-j="' + j + '"]'); M[i].push(parseFloat(el.value) || 0); } }
    return M;
  };
  U.matrixInputs = function (name, M, rowLabs) {
    var h = '<table><tr><th>' + name + '</th>' + M[0].map(function (_, j) { return "<th>维 " + (j + 1) + "</th>"; }).join("") + "</tr>";
    M.forEach(function (row, i) {
      h += "<tr><th>" + (rowLabs ? rowLabs[i] : i) + "</th>";
      row.forEach(function (v, j) { h += '<td><input class="cell" type="number" step="0.5" data-m="' + name + '" data-i="' + i + '" data-j="' + j + '" value="' + v + '"></td>'; });
      h += "</tr>";
    });
    return h + "</table>";
  };

  /* ================================================================ */
  /* 第 0 周                                                            */
  /* ================================================================ */

  /* 梯度连乘：sigmoid 与 ReLU */
  RW["w0-grad-chain"] = function (root) {
    var out = U.frame(root, "梯度穿过很多层会剩下多少",
      "反向传播时，梯度每经过一层就乘一次那一层激活函数的导数。选一种激活函数，拖动层数，看最前面那一层还能收到多少梯度。",
      U.slider("L", "层数", 1, 30, 1, 10) +
      U.select("act", "激活", [["0.25", "sigmoid，最好情况（导数 0.25）"], ["0.105", "sigmoid，输入≈2（导数 0.105）"], ["0.0066", "sigmoid，输入≈5（导数 0.0066）"], ["1", "ReLU，正半边（导数 1）"]], "0.25"));
    U.bind(root, function () {
      var L = U.get(root, "L"), a = parseFloat(U.get(root, "act"));
      U.setv(root, "L", L);
      var rows = [];
      for (var l = 1; l <= L; l++) {
        var v = Math.pow(a, l);
        var w = a >= 1 ? 1 : Math.max(0, (Math.log10(v) + 12) / 12);
        if (L <= 12 || l === 1 || l === L || l % Math.ceil(L / 10) === 0)
          rows.push({ lab: "往回第 " + l + " 层", w: w, num: U.f(v, 4), cls: a >= 1 ? "grn" : (v < 1e-3 ? "alt" : "") });
      }
      var fin = Math.pow(a, L);
      out.innerHTML = '<p>最前面那一层收到的梯度 = ' + a + '<sup>' + L + '</sup> = <span class="w-big">' + U.f(fin, 6) + '</span>　' +
        (a >= 1 ? '<span class="w-ok">不缩水，深层网络也能学</span>' : fin < 1e-4 ? '<span class="w-no">几乎是 0：梯度消失，前面的层学不动</span>' : '<span class="w-no">已经明显缩水</span>') + '</p>' +
        U.bars(rows) + '<p class="w-note">条的长度按对数刻度画（最左端约等于 10⁻¹²）。这就是 2025 卷第 1 题、第 0 周小测 1 第 6 题：ReLU 被偏爱的最直接原因是导数不饱和。</p>';
    });
  };

  /* softmax 饱和与 √d_k */
  RW["w0-softmax"] = function (root) {
    var out = U.frame(root, "softmax 什么时候会「赢家通吃」",
      "三个原始分数固定为下面的值。点积的标准差约等于 √d_k，所以 d_k 越大，送进 softmax 的数越大。勾掉「除以 √d_k」，把 d_k 拖大，看权重和梯度怎么变。",
      '<label>分数 <input class="cell" type="number" step="0.5" data-k="z1" value="1"><input class="cell" type="number" step="0.5" data-k="z2" value="0"><input class="cell" type="number" step="0.5" data-k="z3" value="-1"></label>' +
      U.slider("e", "d_k = 4^", 0, 4, 1, 3) + U.check("scale", "除以 √d_k", true));
    U.bind(root, function () {
      var z = [U.get(root, "z1"), U.get(root, "z2"), U.get(root, "z3")];
      var dk = Math.pow(4, U.get(root, "e")), sc = U.get(root, "scale");
      U.setv(root, "e", dk);
      var logits = z.map(function (v) { return sc ? v : v * Math.sqrt(dk); });
      var p = U.softmax(logits);
      var rows = p.map(function (v, i) { return { lab: "词 " + (i + 1) + "（" + U.f(logits[i], 2) + "）", w: v, num: U.f(v, 4) }; });
      var g = p.map(function (v) { return v * (1 - v); });
      var grows = g.map(function (v, i) { return { lab: "词 " + (i + 1), w: v / 0.25, num: U.f(v, 4), cls: v < 0.01 ? "alt" : "grn" }; });
      out.innerHTML = '<div class="w-grid"><div style="flex:1;min-width:260px"><b>softmax 权重</b>' + U.bars(rows) + '</div><div style="flex:1;min-width:260px"><b>自己对自己的梯度 p(1−p)</b>（最大 0.25）' + U.bars(grows) + '</div></div>' +
        '<p>' + (sc ? "除以 √d_k 之后，不管 d_k 多大，分数都保持原来的量级，权重有高有低但不走极端。" :
          (Math.max.apply(null, p) > 0.99 ? '<span class="w-no">没有缩放、d_k = ' + dk + ' 时分数被放大 ' + Math.sqrt(dk) + ' 倍，第一名几乎拿走全部权重，其他词的梯度接近 0。</span>' : "没有缩放，分数被放大了 " + Math.sqrt(dk) + " 倍，已经开始偏向第一名。")) + '</p>' +
        '<p class="w-note">原论文 d_k = 64，也就是 4³，对应滑块的第 3 格。</p>';
    });
  };

  /* 注意力计算器 */
  RW["w0-attn"] = function (root) {
    var toks = ["I", "love", "cats"];
    var Q0 = [[1, 0], [0, 1], [1, 1]], K0 = [[1, 0], [0, 1], [1, 1]], V0 = [[1, 0], [0, 1], [2, 2]];
    root.insertAdjacentHTML("beforeend",
      '<div class="w-title">注意力计算器（“I love cats”，d_k = 2）</div>' +
      '<p class="w-intro">默认数字和上面的手算完全一样。任意改 Q、K、V 里的数，或者勾选缩放、因果 mask，下面四张表会一起重算。点选「看哪一行」可以看某个词的详细计算。</p>' +
      '<div class="w-grid"><div class="w-out">' + U.matrixInputs("Q", Q0, toks) + '</div><div class="w-out">' + U.matrixInputs("K", K0, toks) + '</div><div class="w-out">' + U.matrixInputs("V", V0, toks) + '</div></div>' +
      '<div class="w-controls">' + U.check("scale", "除以 √d_k", true) + U.check("mask", "因果 mask（不许看后面的词）", false) +
      U.select("row", "看哪一行", [["0", "I"], ["1", "love"], ["2", "cats"]], "2") + '</div><div class="w-out" data-o="res"></div>');
    var out = root.querySelector('[data-o="res"]');
    U.bind(root, function () {
      var Q = U.readMatrix(root, "Q", 3, 2), K = U.readMatrix(root, "K", 3, 2), V = U.readMatrix(root, "V", 3, 2);
      var sc = U.get(root, "scale"), mk = U.get(root, "mask"), r = parseInt(U.get(root, "row"), 10);
      var S = Q.map(function (q) { return K.map(function (k) { return q[0] * k[0] + q[1] * k[1]; }); });
      var S2 = S.map(function (row, i) { return row.map(function (v, j) { if (mk && j > i) return -Infinity; return sc ? v / Math.SQRT2 : v; }); });
      var P = S2.map(U.softmax);
      var O = P.map(function (p) { return [0, 1].map(function (c) { return p[0] * V[0][c] + p[1] * V[1][c] + p[2] * V[2][c]; }); });
      function cls(i) { return i === r ? "hl" : ""; }
      var e = S2[r].map(function (v) { return isFinite(v) ? Math.exp(v) : 0; });
      var sum = e.reduce(function (a, b) { return a + b; }, 0);
      out.innerHTML = '<div class="w-grid">' +
        '<div><b>① 分数 S = QKᵀ</b>' + U.table(S, { rows: toks, cols: toks, d: 2, cls: function (i) { return cls(i); } }) + '</div>' +
        '<div><b>② ' + (sc ? "÷√2" : "不缩放") + (mk ? " + mask" : "") + '</b>' + U.table(S2, { rows: toks, cols: toks, d: 3, cls: function (i) { return cls(i); } }) + '</div>' +
        '<div><b>③ 每行 softmax → P</b>' + U.table(P, { rows: toks, cols: toks, d: 3, cls: function (i) { return cls(i); } }) + '</div>' +
        '<div><b>④ 输出 O = PV</b>' + U.table(O, { rows: toks, cols: ["维 1", "维 2"], d: 3, cls: function (i) { return cls(i); } }) + '</div></div>' +
        '<p><b>' + toks[r] + ' 这一行</b>：分数 [' + S[r].map(function (v) { return U.f(v, 2); }).join(", ") + '] → ' + (sc ? "除以 1.414" : "不缩放") + (mk ? "、后面的位置填 −∞" : "") +
        ' 得 [' + S2[r].map(function (v) { return U.f(v, 3); }).join(", ") + '] → 取 e 的幂 [' + e.map(function (v) { return U.f(v, 3); }).join(", ") + ']，加起来 ' + U.f(sum, 3) +
        ' → 各自除以总和得权重 [' + P[r].map(function (v) { return U.f(v, 3); }).join(", ") + ']（加起来 = 1）→ 用权重把三行 V 加起来得 [' + O[r].map(function (v) { return U.f(v, 3); }).join(", ") + ']。</p>';
    });
  };

  /* Adagrad vs RMSProp */
  RW["w0-adagrad"] = function (root) {
    var out = U.frame(root, "Adagrad：常见特征和稀有特征各拧多大",
      "参数 A 对应常见特征，每一步梯度都是 1；参数 B 对应稀有特征，每隔 k 步才出现一次梯度 1，其余步是 0。全局学习率 η = 0.1。看两者的「有效学习率」怎么随步数变化。",
      U.slider("k", "稀有特征每隔几步出现", 2, 10, 1, 5) + U.slider("T", "总步数", 5, 200, 5, 50) +
      U.select("m", "方法", [["ada", "Adagrad（累加平方和）"], ["rms", "RMSProp（移动平均 β = 0.9）"]], "ada"));
    U.bind(root, function () {
      var k = U.get(root, "k"), T = U.get(root, "T"), m = U.get(root, "m");
      U.setv(root, "k", k); U.setv(root, "T", T);
      var eta = 0.1, eps = 1e-8, GA = 0, GB = 0, mvA = 0, mvB = 0;
      var xs = [], la = [], lb = [], tab = [];
      for (var t = 1; t <= T; t++) {
        var gA = 1, gB = (t % k === 0) ? 1 : 0;
        if (m === "ada") { GA += gA * gA; GB += gB * gB; }
        else { GA = 0.9 * GA + 0.1 * gA * gA; GB = 0.9 * GB + 0.1 * gB * gB; }
        var lrA = eta / (Math.sqrt(GA) + eps), lrB = GB > 0 ? eta / (Math.sqrt(GB) + eps) : NaN;
        mvA += lrA * gA; mvB += (gB ? lrB * gB : 0);
        xs.push(t); la.push(lrA); lb.push(lrB);
        if (t <= 3 || t === k || t === 2 * k || t === T) tab.push([t, gA, gB, U.f(GA, 3), U.f(GB, 3), U.f(lrA, 4), gB ? U.f(lrB, 4) : "—"]);
      }
      var ymax = Math.max(0.12, Math.max.apply(null, la.concat(lb.filter(isFinite))) * 1.1);
      out.innerHTML = U.plot({ xs: xs, series: [{ ys: la, cls: "blue", label: "A（常见）的有效学习率" }, { ys: lb.map(function (v, i) { return isFinite(v) ? v : (i > 0 ? lb.slice(0, i).filter(isFinite).pop() : NaN); }), cls: "red", label: "B（稀有）的有效学习率" }],
        xmin: 1, xmax: T, ymin: 0, ymax: ymax, xticks: [1, Math.round(T / 2), T], yticks: [0, 0.05, 0.1].filter(function (v) { return v <= ymax; }), xlabel: "步数", ylabel: "η/√G" }) +
        '<table><tr><th>步</th><th>g_A</th><th>g_B</th><th>G_A</th><th>G_B</th><th>A 的学习率</th><th>B 的学习率</th></tr>' + tab.map(function (r) { return "<tr><td>" + r.join("</td><td>") + "</td></tr>"; }).join("") + '</table>' +
        '<p>' + T + ' 步之后：A 累计移动 ' + U.f(mvA, 3) + '，B 累计移动 ' + U.f(mvB, 3) + '（B 只收到 ' + Math.floor(T / k) + ' 次梯度）。' +
        (m === "ada" ? ' <span class="w-no">Adagrad 的 G 只增不减，A 的学习率一路降到 ' + U.f(la[la.length - 1], 4) + '，步数越多越接近 0，这就是它的弱点。</span>' :
          ' <span class="w-ok">RMSProp 用移动平均，A 的学习率稳定在约 0.1 附近，不会衰减到 0。</span>') + '</p>';
    });
  };

  /* BatchNorm γ β */
  RW["w0-bn"] = function (root) {
    var out = U.frame(root, "BatchNorm：先拉回均值 0 方差 1，再学 γ 和 β",
      "改这一批的 4 个激活值，拖动 γ（缩放）和 β（平移）。点「还原」会把 γ 设成原始标准差、β 设成原始均值，看输出是不是变回原样。",
      '<label>激活值 <input class="cell" type="number" data-k="x1" value="2"><input class="cell" type="number" data-k="x2" value="4"><input class="cell" type="number" data-k="x3" value="6"><input class="cell" type="number" data-k="x4" value="8"></label>' +
      U.slider("g", "γ", 0, 4, 0.01, 1) + U.slider("b", "β", -6, 10, 0.01, 0) + '<button type="button" data-act="undo">还原（γ = σ，β = μ）</button>');
    root.addEventListener("click", function (e) {
      if (!e.target.closest('[data-act="undo"]')) return;
      var x = [1, 2, 3, 4].map(function (i) { return U.get(root, "x" + i); });
      var mu = x.reduce(function (a, b) { return a + b; }, 0) / 4;
      var v = x.reduce(function (a, b) { return a + (b - mu) * (b - mu); }, 0) / 4;
      root.querySelector('[data-k="g"]').value = Math.sqrt(v).toFixed(2);
      root.querySelector('[data-k="b"]').value = mu.toFixed(2);
      root.dispatchEvent(new Event("input"));
    });
    U.bind(root, function () {
      var x = [1, 2, 3, 4].map(function (i) { return U.get(root, "x" + i); });
      var g = U.get(root, "g"), b = U.get(root, "b");
      U.setv(root, "g", g.toFixed(2)); U.setv(root, "b", b.toFixed(2));
      var mu = x.reduce(function (a, c) { return a + c; }, 0) / 4;
      var v = x.reduce(function (a, c) { return a + (c - mu) * (c - mu); }, 0) / 4;
      var xh = x.map(function (c) { return (c - mu) / Math.sqrt(v + 1e-5); });
      var y = xh.map(function (c) { return g * c + b; });
      out.innerHTML = U.table([x, xh, y], { rows: ["原始 x", "归一化 x̂", "输出 y = γx̂ + β"], cols: ["1", "2", "3", "4"], d: 3 }) +
        '<p>这一批的均值 μ = ' + U.f(mu, 3) + '，方差 σ² = ' + U.f(v, 3) + '，标准差 σ = ' + U.f(Math.sqrt(v), 3) + '。归一化之后均值 0、方差 1；γ、β 让网络可以再把分布挪到它想要的地方，甚至完全撤销归一化（小测 1 第 7 题）。</p>';
    });
  };

  /* 正弦位置编码热力图 */
  RW["w0-pe"] = function (root) {
    var out = U.frame(root, "正弦位置编码长什么样",
      "每一行是一个位置的编码向量，每一列是一个维度。颜色：红 = 正，蓝 = 负。左边的维度频率高、变化快（像秒针），右边的维度频率低、变化慢（像时针）。拖动「位置」看那一行的具体数值。",
      U.slider("d", "维度 d", 4, 64, 4, 16) + U.slider("p", "位置", 0, 49, 1, 3));
    U.bind(root, function () {
      var d = U.get(root, "d"), P = U.get(root, "p"), N = 50;
      U.setv(root, "d", d); U.setv(root, "p", P);
      function pe(pos, k) { var i = Math.floor(k / 2), w = pos / Math.pow(10000, 2 * i / d); return k % 2 === 0 ? Math.sin(w) : Math.cos(w); }
      var cw = Math.max(6, Math.floor(480 / d)), ch = 6, W = cw * d + 50, H = ch * N + 26;
      var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" style="max-width:100%;height:auto">';
      for (var pos = 0; pos < N; pos++) for (var k = 0; k < d; k++) {
        var v = pe(pos, k), r = v > 0 ? 255 : Math.round(255 * (1 + v)), bl = v < 0 ? 255 : Math.round(255 * (1 - v)), gr = Math.round(255 * (1 - Math.abs(v)));
        s += '<rect x="' + (40 + k * cw) + '" y="' + (pos * ch) + '" width="' + cw + '" height="' + ch + '" fill="rgb(' + r + "," + gr + "," + bl + ')"/>';
      }
      s += '<rect x="39" y="' + (P * ch - 1) + '" width="' + (cw * d + 2) + '" height="' + (ch + 2) + '" fill="none" stroke="#111" stroke-width="2"/>';
      s += '<text x="34" y="' + (P * ch + 6) + '" font-size="10" text-anchor="end">pos ' + P + '</text>';
      s += '<text x="40" y="' + (N * ch + 14) + '" font-size="10">维度 0（快）</text><text x="' + (40 + cw * d) + '" y="' + (N * ch + 14) + '" font-size="10" text-anchor="end">维度 ' + (d - 1) + '（慢）</text></svg>';
      var vec = []; for (var k2 = 0; k2 < Math.min(d, 8); k2++) vec.push(U.f(pe(P, k2), 3));
      out.innerHTML = s + '<p>位置 ' + P + ' 的前 ' + Math.min(d, 8) + ' 维：[' + vec.join(", ") + (d > 8 ? ", …" : "") + ']。这个向量被<b>加</b>到这个位置的词向量上。每个位置的「条纹组合」都不一样，所以模型能分出谁在前谁在后。</p>';
    });
  };

  /* 复杂度比较 */
  RW["w0-complexity"] = function (root) {
    var out = U.frame(root, "自注意力 vs 循环层：什么时候谁更贵",
      "拖动序列长度 n 和向量维度 d。自注意力每层约 n²·d 次乘加，循环层约 n·d²。",
      U.slider("n", "序列长度 n = 10^", 1, 6, 0.1, 2) + U.slider("d", "维度 d", 64, 8192, 64, 512));
    U.bind(root, function () {
      var n = Math.round(Math.pow(10, U.get(root, "n"))), d = U.get(root, "d");
      U.setv(root, "n", n.toLocaleString()); U.setv(root, "d", d);
      var a = n * n * d, r = n * d * d, mx = Math.max(a, r);
      var mem = n * n * 2;
      out.innerHTML = U.bars([{ lab: "自注意力 n²d", w: Math.log10(a) / Math.log10(mx), num: U.big(a), cls: a > r ? "alt" : "grn" }, { lab: "循环层 nd²", w: Math.log10(r) / Math.log10(mx), num: U.big(r), cls: r > a ? "alt" : "grn" }]) +
        '<p>' + (n > d ? '<span class="w-no">n = ' + n.toLocaleString() + ' > d = ' + d + '，自注意力贵 ' + U.f(a / r, 1) + ' 倍。</span>' : n < d ? '<span class="w-ok">n < d，自注意力反而便宜 ' + U.f(r / a, 1) + ' 倍（2017 年翻译句子短，就是这种情况）。</span>' : "n = d，一样贵。") +
        ' 另外，自注意力要存一张 n×n 的分数表，单个头、fp16 就是 ' + U.bytes(mem) + '。' + (mem > 80e9 ? ' <span class="w-no">比一张 80 GB 的 GPU 还大。</span>' : "") + '</p><p class="w-note">条的长度按对数刻度画。</p>';
    });
  };
})();
