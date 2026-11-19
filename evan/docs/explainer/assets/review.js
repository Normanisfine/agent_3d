/* CIS 6220 复习页公共脚本（HW6 讲解页沿用期中复习版，目录首页链接改成可配置）：目录、主题、选择题、简答题、考试计时 */
(function () {
  "use strict";

  var PAGE = (document.body.getAttribute("data-page") || location.pathname.split("/").pop() || "page").replace(/\W+/g, "_");
  var NS = "cis6220-review:" + PAGE + ":";

  function load(k, dflt) {
    try { var v = localStorage.getItem(NS + k); return v === null ? dflt : JSON.parse(v); } catch (e) { return dflt; }
  }
  function save(k, v) {
    try { localStorage.setItem(NS + k, JSON.stringify(v)); } catch (e) { /* 私密窗口等情况下忽略 */ }
  }
  function drop(k) {
    try { localStorage.removeItem(NS + k); } catch (e) { }
  }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  /* 按 data-week 分组统计每周答对几题（模拟卷用）；answeredOnly 时分母是已判分的题数 */
  function weekLine(qs, answeredOnly) {
    var order = [], st = {};
    qs.forEach(function (q) {
      var w = q.getAttribute("data-week"); if (!w) return;
      if (!st[w]) { st[w] = { n: 0, a: 0, r: 0 }; order.push(w); }
      st[w].n++;
      var p = q.getAttribute("data-picked");
      if (p && (!answeredOnly || q.classList.contains("graded"))) { st[w].a++; if (p === q.getAttribute("data-answer")) st[w].r++; }
    });
    if (answeredOnly) order = order.filter(function (w) { return st[w].a > 0; });
    if (!order.length) return "";
    return '<div style="margin-top:6px">按周：' + order.map(function (w) {
      var s = st[w]; return w + " <b>" + s.r + "</b> / " + (answeredOnly ? s.a : s.n);
    }).join("　") + "</div>";
  }

  /* ---------- 交互组件（先挂载，让里面的静态公式也能被渲染） ---------- */
  (function () {
    var RW = window.RW || {};
    $all("[data-widget]").forEach(function (el) {
      var name = el.getAttribute("data-widget"), f = RW[name];
      if (!el.classList.contains("widget")) el.classList.add("widget");
      if (!f) { el.insertAdjacentHTML("beforeend", '<p class="muted">（交互组件 ' + name + ' 未找到）</p>'); return; }
      try { f(el); } catch (e) { console.error(e); el.insertAdjacentHTML("beforeend", '<p class="muted">交互组件加载失败：' + e.message + "</p>"); }
    });
  })();

  /* ---------- 逐步架构图 ---------- */
  $all(".arch").forEach(function (box) {
    var svg = box.querySelector("svg");
    var list = box.querySelector(".arch-steps");
    if (!svg || !list) return;
    var items = $all(":scope > li", list), n = items.length, k = 0;
    var els = $all("[data-s]", svg);
    var bar = document.createElement("div"); bar.className = "arch-bar";
    bar.innerHTML = '<button type="button" data-a="prev">◀ 上一步</button><span class="arch-pos"></span>' +
      '<button type="button" class="primary" data-a="next">下一步 ▶</button><button type="button" data-a="all">全部显示</button>';
    var now = document.createElement("div"); now.className = "arch-now";
    list.parentNode.insertBefore(bar, list);
    list.parentNode.insertBefore(now, list);
    function steps(el) { return el.getAttribute("data-s").split(/[\s,]+/).map(Number); }
    function render() {
      els.forEach(function (el) {
        el.classList.remove("s-on", "s-seen", "s-off");
        if (k === 0) return;
        var s = steps(el);
        if (s.indexOf(k) >= 0) el.classList.add("s-on");
        else if (s.some(function (x) { return x < k; })) el.classList.add("s-seen");
        else el.classList.add("s-off");
      });
      items.forEach(function (li, i) { li.classList.toggle("cur", i === k - 1); });
      bar.querySelector(".arch-pos").textContent = k === 0 ? "共 " + n + " 步" : "第 " + k + " / " + n + " 步";
      now.innerHTML = k === 0 ? "点「下一步」从第 1 步开始，看数据一步一步怎么流过这个结构。也可以直接点下面任意一步。"
        : "<b>第 " + k + " 步</b>　" + items[k - 1].innerHTML;
    }
    bar.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      var a = b.getAttribute("data-a");
      if (a === "next") k = k >= n ? 1 : k + 1;
      if (a === "prev") k = k <= 1 ? n : k - 1;
      if (a === "all") k = 0;
      render();
    });
    items.forEach(function (li, i) { li.addEventListener("click", function () { k = i + 1; render(); }); });
    render();
  });

  /* ---------- 公式 ---------- */
  if (window.renderMathInElement) {
    try {
      window.renderMathInElement(document.body, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "\\[", right: "\\]", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\(", right: "\\)", display: false }
        ],
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
        throwOnError: false
      });
    } catch (e) { console.warn(e); }
  }

  /* ---------- 主题 ---------- */
  (function () {
    var t = null;
    try { t = localStorage.getItem("cis6220-review:theme"); } catch (e) { }
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  })();
  function toggleTheme() {
    var cur = document.documentElement.getAttribute("data-theme");
    var dark = cur ? cur === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    var next = dark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("cis6220-review:theme", next); } catch (e) { }
  }

  /* ---------- 目录（按节折叠，整栏可收起） ---------- */
  var toc = document.querySelector("nav.toc");
  var content = document.querySelector(".content");
  function tocLabel(h) {
    var label = h.getAttribute("data-toc");
    if (label) return label;
    var c = h.cloneNode(true);
    var num = c.querySelector(".num");
    var numText = num ? num.textContent.trim() : "";
    if (num) num.remove();
    $all(".katex", c).forEach(function (k) {
      var ann = k.querySelector("annotation");
      var tex = ann ? ann.textContent : k.textContent;
      tex = tex.replace(/\\sqrt\{([^}]*)\}/g, "√$1").replace(/\\(left|right|,|;|!)/g, "").replace(/\\([a-zA-Z]+)/g, "$1").replace(/[{}]/g, "");
      k.replaceWith(document.createTextNode(tex));
    });
    var rest = c.textContent.replace(/\s+/g, " ").trim();
    return numText ? numText + "　" + rest : rest;
  }
  function setCollapsed(on) {
    document.body.classList.toggle("toc-collapsed", on);
    try { localStorage.setItem("cis6220-review:toc-collapsed", on ? "1" : "0"); } catch (e) { }
  }
  if (toc && content) {
    try { if (localStorage.getItem("cis6220-review:toc-collapsed") === "1") document.body.classList.add("toc-collapsed"); } catch (e) { }
    var heads = $all("h2[id], h3[id]", content).filter(function (h) { return !h.hasAttribute("data-notoc"); });
    var title = toc.getAttribute("data-title") || "目录";
    var html = '<div class="toc-rail" title="展开目录">» 展开目录</div>';
    html += '<div class="toc-head"><div class="toc-title">' + title + '</div><button type="button" class="toc-collapse" data-act="collapse" title="收起目录">«</button></div>';
    var home = toc.getAttribute("data-home"), homeLabel = toc.getAttribute("data-home-label") || "← 复习总览";
    html += (home === "" ? "" : '<a class="toc-home" href="' + (home || "index.html") + '">' + homeLabel + '</a>') + '<ol class="toc-top">';
    var open = false;
    heads.forEach(function (h, i) {
      var lab = tocLabel(h);
      if (h.tagName === "H2") {
        if (open) html += "</ol></li>";
        var hasSub = heads[i + 1] && heads[i + 1].tagName === "H3";
        html += '<li class="h2"><div class="toc-row"><button type="button" class="toc-caret' + (hasSub ? "" : " empty") + '" aria-label="展开或收起">▶</button><a href="#' + h.id + '">' + lab + '</a></div><ol class="toc-sub">';
        open = true;
      } else {
        if (!open) { html += '<li class="h2"><div class="toc-row"><button type="button" class="toc-caret empty">▶</button><span></span></div><ol class="toc-sub">'; open = true; }
        html += '<li class="h3"><a href="#' + h.id + '">' + lab + "</a></li>";
      }
    });
    if (open) html += "</ol></li>";
    html += '</ol><div class="toc-tools"><button type="button" data-act="expand">全部展开</button><button type="button" data-act="fold">全部收起</button><button type="button" data-act="theme">深色 / 浅色</button><button type="button" data-act="top">回到顶部</button></div>';
    toc.innerHTML = html;
    var groups = $all("li.h2", toc);
    var manual = false;
    toc.addEventListener("click", function (e) {
      if (e.target.closest(".toc-rail")) { setCollapsed(false); return; }
      var cb = e.target.closest(".toc-caret");
      if (cb) { manual = true; cb.closest("li.h2").classList.toggle("open"); return; }
      var b = e.target.closest("button");
      var act = b && b.getAttribute("data-act");
      if (act === "theme") toggleTheme();
      if (act === "top") window.scrollTo(0, 0);
      if (act === "collapse") setCollapsed(true);
      if (act === "expand") { manual = true; groups.forEach(function (g) { g.classList.add("open"); }); }
      if (act === "fold") { manual = true; groups.forEach(function (g) { g.classList.remove("open"); }); }
      if (e.target.closest("a") && window.innerWidth <= 900) toc.classList.remove("open");
    });
    var tbtn = document.createElement("button");
    tbtn.className = "toc-toggle"; tbtn.type = "button"; tbtn.textContent = "目录";
    tbtn.addEventListener("click", function () { toc.classList.toggle("open"); });
    document.body.appendChild(tbtn);

    var links = {};
    $all("a", toc).forEach(function (a) { var id = (a.getAttribute("href") || "").slice(1); if (id) links[id] = a; });
    var current = null;
    function spy() {
      var y = window.scrollY + 90, best = null;
      for (var i = 0; i < heads.length; i++) { if (heads[i].offsetTop <= y) best = heads[i]; else break; }
      var id = best ? best.id : null;
      if (id === current) return;
      if (current && links[current]) links[current].classList.remove("active");
      current = id;
      if (id && links[id]) {
        var a = links[id];
        a.classList.add("active");
        var g = a.closest("li.h2");
        if (!manual) groups.forEach(function (x) { x.classList.toggle("open", x === g); });
        else if (g) g.classList.add("open");
        var r = a.getBoundingClientRect(), tr = toc.getBoundingClientRect();
        if (r.top < tr.top + 40 || r.bottom > tr.bottom - 40) toc.scrollTop += r.top - tr.top - tr.height / 3;
      }
    }
    window.addEventListener("scroll", spy, { passive: true });
    spy();
  }

  /* ---------- 选择题 ---------- */
  function modeOf(el) {
    var m = el.closest("[data-mode]");
    return m ? m.getAttribute("data-mode") : "practice";
  }
  var examSubmitted = load("__submitted", false);

  function grade(q) {
    var ans = (q.getAttribute("data-answer") || "").trim();
    var picked = q.getAttribute("data-picked") || "";
    q.classList.add("graded");
    q.classList.remove("is-right", "is-wrong", "is-blank");
    $all(".opts li", q).forEach(function (li) {
      var k = li.getAttribute("data-k");
      li.classList.toggle("right", k === ans);
      li.classList.toggle("wrong", k === picked && k !== ans);
    });
    var v = q.querySelector(".verdict");
    if (!v) { v = document.createElement("div"); v.className = "verdict"; q.querySelector(".opts").after(v); }
    if (!picked) { q.classList.add("is-blank"); v.textContent = "未作答 · 正确答案 " + ans; }
    else if (picked === ans) { q.classList.add("is-right"); v.textContent = "✓ 答对了 · 答案 " + ans; }
    else { q.classList.add("is-wrong"); v.textContent = "✗ 你选了 " + picked + " · 正确答案 " + ans; }
    updateTally();
    return picked === ans;
  }
  function ungrade(q) {
    q.classList.remove("graded", "is-right", "is-wrong", "is-blank");
    $all(".opts li", q).forEach(function (li) { li.classList.remove("right", "wrong", "picked"); });
    q.removeAttribute("data-picked");
    updateTally();
  }
  function setPick(q, k) {
    q.setAttribute("data-picked", k);
    $all(".opts li", q).forEach(function (li) { li.classList.toggle("picked", li.getAttribute("data-k") === k); });
  }

  var mcqs = $all(".mcq");
  mcqs.forEach(function (q, i) {
    if (!q.id) q.id = "mcq-" + (i + 1);
    var mode = modeOf(q);
    var saved = load("pick:" + q.id, "");
    if (saved) setPick(q, saved);
    if (mode === "practice" && saved) grade(q);
    if (mode === "exam" && examSubmitted) grade(q);

    if (mode === "practice") {
      var acts = document.createElement("div");
      acts.className = "q-actions";
      acts.innerHTML = '<button type="button" data-act="redo">重做这题</button><button type="button" data-act="peek">不做了，直接看答案</button>';
      q.appendChild(acts);
      acts.addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b) return;
        if (b.getAttribute("data-act") === "redo") { ungrade(q); drop("pick:" + q.id); }
        if (b.getAttribute("data-act") === "peek") { grade(q); }
      });
    }
    q.querySelector(".opts").addEventListener("click", function (e) {
      var li = e.target.closest("li[data-k]"); if (!li) return;
      if (q.classList.contains("graded")) return;
      var k = li.getAttribute("data-k");
      setPick(q, k); save("pick:" + q.id, k);
      if (modeOf(q) === "practice") grade(q);
      updateProgress();
    });
  });

  /* ---------- 简答题 ---------- */
  var frqs = $all(".frq");
  frqs.forEach(function (f, i) {
    if (!f.id) f.id = "frq-" + (i + 1);
    var ta = f.querySelector("textarea");
    if (ta) {
      ta.value = load("text:" + f.id, "");
      ta.addEventListener("input", function () { save("text:" + f.id, ta.value); });
    }
    $all(".rubric input[type=checkbox]", f).forEach(function (cb, j) {
      cb.checked = !!load("rub:" + f.id + ":" + j, false);
      cb.addEventListener("change", function () { save("rub:" + f.id + ":" + j, cb.checked); updateScore(); updateTally(); });
    });
    var mode = modeOf(f);
    var btn = f.querySelector("button.reveal");
    if (btn) {
      if (mode === "exam" && !examSubmitted) btn.style.display = "none";
      btn.addEventListener("click", function () { f.classList.toggle("revealed"); btn.textContent = f.classList.contains("revealed") ? "收起参考答案" : "看参考答案"; });
    }
    if (mode === "exam" && examSubmitted) f.classList.add("revealed");
    if (mode === "practice" && load("rev:" + f.id, false)) f.classList.add("revealed");
  });

  /* ---------- 考试条 ---------- */
  var bar = document.querySelector(".exam-bar");
  var card = document.querySelector(".score-card");
  var timerEl = bar ? bar.querySelector(".timer") : null;
  var minutes = bar ? parseFloat(bar.getAttribute("data-minutes") || "90") : 0;
  var tick = null;

  function fmt(sec) {
    var neg = sec < 0; sec = Math.abs(Math.round(sec));
    var m = Math.floor(sec / 60), s = sec % 60;
    return (neg ? "超时 " : "") + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }
  function renderTimer() {
    if (!timerEl) return;
    var start = load("__start", null), elapsed = load("__elapsed", 0);
    var used = elapsed + (start ? (Date.now() - start) / 1000 : 0);
    var left = minutes * 60 - used;
    timerEl.textContent = fmt(left);
    timerEl.classList.toggle("low", left < 300);
    var sb = bar.querySelector("[data-act=start]");
    if (sb) sb.textContent = start ? "暂停" : (used > 0 ? "继续计时" : "开始计时");
  }
  function updateProgress() {
    if (!bar) return;
    var examQs = mcqs.filter(function (q) { return modeOf(q) === "exam"; });
    var done = examQs.filter(function (q) { return q.getAttribute("data-picked"); }).length;
    var p = bar.querySelector(".progress");
    if (p) p.textContent = "已答 " + done + " / " + examQs.length;
  }
  function updateScore() {
    if (!card || !examSubmitted) return;
    var examQs = mcqs.filter(function (q) { return modeOf(q) === "exam"; });
    var got = 0, tot = 0, wrong = [];
    examQs.forEach(function (q) {
      var pts = parseFloat(q.getAttribute("data-pts") || "2");
      tot += pts;
      if (q.getAttribute("data-picked") === q.getAttribute("data-answer")) got += pts;
      else wrong.push(q);
    });
    var fgot = 0, ftot = 0;
    frqs.filter(function (f) { return modeOf(f) === "exam"; }).forEach(function (f) {
      ftot += parseFloat(f.getAttribute("data-points") || "0");
      $all(".rubric input[type=checkbox]", f).forEach(function (cb) { if (cb.checked) fgot += parseFloat(cb.getAttribute("data-pts") || "1"); });
    });
    var h = '<div>选择题 <span class="big">' + got + " / " + tot + "</span>　（" + (examQs.length - wrong.length) + " / " + examQs.length + " 题对）</div>";
    h += weekLine(examQs, false);
    if (ftot > 0) h += '<div style="margin-top:6px">简答题自评 <b>' + fgot + " / " + ftot + "</b>（对照参考答案勾选评分点后自动更新）</div>";
    if (wrong.length) {
      h += '<div class="wrong-list" style="margin-top:8px">错题和空题，点击跳转：';
      wrong.forEach(function (q) { var n = q.querySelector(".q-no"); h += '<a href="#' + q.id + '">' + (n ? n.textContent.replace(/[.．]/, "") : q.id) + "</a>"; });
      h += "</div>";
    } else h += '<div style="margin-top:8px">选择题全对。</div>';
    card.innerHTML = h; card.classList.add("show");
  }
  if (bar) {
    bar.innerHTML = '<span class="timer">--:--</span><button type="button" data-act="start">开始计时</button><span class="progress"></span><span class="spacer"></span>' +
      '<button type="button" class="primary" data-act="submit">交卷并看答案</button><button type="button" data-act="reset">清空重做</button>';
    timerEl = bar.querySelector(".timer");
    renderTimer(); updateProgress();
    if (load("__start", null)) tick = setInterval(renderTimer, 1000);
    bar.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      var act = b.getAttribute("data-act");
      if (act === "start") {
        var start = load("__start", null);
        if (start) { save("__elapsed", load("__elapsed", 0) + (Date.now() - start) / 1000); drop("__start"); clearInterval(tick); }
        else { save("__start", Date.now()); tick = setInterval(renderTimer, 1000); }
        renderTimer();
      }
      if (act === "submit") {
        if (!examSubmitted && !confirm("确定交卷？交卷后显示全部答案和讲解。")) return;
        examSubmitted = true; save("__submitted", true);
        var start2 = load("__start", null);
        if (start2) { save("__elapsed", load("__elapsed", 0) + (Date.now() - start2) / 1000); drop("__start"); clearInterval(tick); renderTimer(); }
        mcqs.forEach(function (q) { if (modeOf(q) === "exam") grade(q); });
        frqs.forEach(function (f) { if (modeOf(f) === "exam") { f.classList.add("revealed"); var rb = f.querySelector("button.reveal"); if (rb) rb.style.display = ""; } });
        updateScore();
        if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      if (act === "reset") {
        if (!confirm("清空这份卷子的全部作答、计时和自评？")) return;
        try {
          Object.keys(localStorage).forEach(function (k) { if (k.indexOf(NS) === 0) localStorage.removeItem(k); });
        } catch (err) { }
        location.reload();
      }
    });
    updateScore();
  }

  /* ---------- 选完即判的整份卷子：实时计分 ----------
     页面放 .tally-bar（顶上的条）和 .tally-card（错题清单）；
     放在 .no-tally 里的题（超纲题）单独计数，不算进主成绩。 */
  var tallyBar = document.querySelector(".tally-bar");
  var tallyCard = document.querySelector(".tally-card");
  function twoStep(b, label) {
    if (b.getAttribute("data-armed") === "1") { b.removeAttribute("data-armed"); b.textContent = b._orig; return true; }
    b._orig = b.textContent; b.setAttribute("data-armed", "1"); b.textContent = label;
    setTimeout(function () { if (b.getAttribute("data-armed") === "1") { b.removeAttribute("data-armed"); b.textContent = b._orig; } }, 4000);
    return false;
  }
  function tallyOf(qs) {
    var s = { n: qs.length, a: 0, r: 0, wrong: [] };
    qs.forEach(function (q) {
      var p = q.getAttribute("data-picked");
      if (!p || !q.classList.contains("graded")) return;
      s.a++;
      if (p === q.getAttribute("data-answer")) s.r++; else s.wrong.push(q);
    });
    return s;
  }
  function updateTally() {
    if (!tallyBar) return;
    var core = tallyOf(mcqs.filter(function (q) { return !q.closest(".no-tally"); }));
    var extra = tallyOf(mcqs.filter(function (q) { return q.closest(".no-tally"); }));
    var fgot = 0, ftot = 0;
    (frqs || []).filter(function (f) { return !f.closest(".no-tally"); }).forEach(function (f) {
      ftot += parseFloat(f.getAttribute("data-points") || "0");
      $all(".rubric input[type=checkbox]", f).forEach(function (cb) { if (cb.checked) fgot += parseFloat(cb.getAttribute("data-pts") || "1"); });
    });
    var lab = tallyBar.getAttribute("data-label") || "范围内";
    var stats = tallyBar.querySelector(".stats");
    if (stats) stats.innerHTML = "<b>" + lab + "</b> 已答 " + core.a + " / " + core.n + " · 对 " + core.r +
      (extra.n ? '<span class="muted">　超纲 已答 ' + extra.a + " / " + extra.n + " · 对 " + extra.r + "</span>" : "");
    if (!tallyCard) return;
    if (!core.a && !extra.a && !fgot) { tallyCard.classList.remove("show"); return; }
    function links(list) {
      return list.map(function (q) { var n = q.querySelector(".q-no"); return '<a href="#' + q.id + '">' + (n ? n.textContent.replace(/[.．]/, "") : q.id) + "</a>"; }).join("");
    }
    var h = '<div>' + lab + '选择题：答对 <span class="big">' + core.r + " / " + core.a + "</span>　（已答 " + core.a + " / " + core.n +
      (core.a ? "，正确率 " + Math.round(core.r / core.a * 100) + "%" : "") + "）</div>";
    h += weekLine(mcqs.filter(function (q) { return !q.closest(".no-tally"); }), true);
    h += core.wrong.length ? '<div class="wrong-list" style="margin-top:8px">错题，点击跳转：' + links(core.wrong) + "</div>" :
      (core.a ? '<div style="margin-top:8px">目前做过的全对。</div>' : "");
    if (extra.a) {
      h += '<div style="margin-top:8px">超纲题：答对 ' + extra.r + " / " + extra.a + "（共 " + extra.n + " 道）" +
        (extra.wrong.length ? '<span class="wrong-list">　错题：' + links(extra.wrong) + "</span>" : "") + "</div>";
    }
    if (ftot > 0) h += '<div style="margin-top:6px">填空和设计题自评 <b>' + fgot + " / " + ftot + "</b>（点开参考答案、勾上答到的评分点后自动更新）</div>";
    tallyCard.innerHTML = h; tallyCard.classList.add("show");
  }
  if (tallyBar) {
    tallyBar.innerHTML = '<span class="stats"></span><span class="spacer"></span><button type="button" data-act="reset">清空重做</button>';
    tallyBar.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-act=reset]"); if (!b) return;
      if (!twoStep(b, "再点一次确认清空")) return;
      try {
        Object.keys(localStorage).forEach(function (k) { if (k.indexOf(NS) === 0) localStorage.removeItem(k); });
      } catch (err) { }
      location.reload();
    });
    updateTally();
  }

  /* ---------- 复习清单勾选 ---------- */
  $all(".todo input[type=checkbox][data-key]").forEach(function (cb) {
    var k = "todo:" + cb.getAttribute("data-key");
    cb.checked = !!load(k, false);
    var li = cb.closest("li"); if (li) li.classList.toggle("done", cb.checked);
    cb.addEventListener("change", function () { save(k, cb.checked); if (li) li.classList.toggle("done", cb.checked); });
  });
})();
