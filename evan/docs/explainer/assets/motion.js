/* CIS 6220 复习页 · 动效（Apple 风格版，2026-10-12）
   在 review.js 之后加载。只加 class 和少量元素，不改页面内容和 review.js 的逻辑。
   页首的入场动画由 <head> 里的一行脚本给 <html> 加 ap-anim 后用纯 CSS 触发。 */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduce) root.classList.add("ap-anim");
  var main = document.querySelector("main");
  var content = document.querySelector(".content");
  if (!main || !content) return;
  function $all(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }

  /* ---------- 章号眉标：数字默认「第 N 章」；<body data-num-unit="周"> 换单位；
     汉字序号（模拟卷的「一、二」）显示成「第二部分」；其他符号（✓）不显示 ---------- */
  var unit = document.body.getAttribute("data-num-unit") || "章";
  $all("h2 > .num", content).forEach(function (n) {
    var t = n.textContent.trim();
    if (/^\d+$/.test(t)) { if (unit !== "章") n.setAttribute("data-label", "第 " + t + " " + unit); }
    else if (/^[一二三四五六七八九十]+$/.test(t)) n.setAttribute("data-label", "第" + t + "部分");
    else n.setAttribute("data-label", "");
  });

  /* ---------- 顶栏：页名 › 当前章，阅读进度条 ---------- */
  var heads = $all("h2[id]", content);
  var bar = document.createElement("div");
  bar.className = "ap-topbar";
  var crumb = (document.title || "").replace(/\s+/g, " ");
  bar.innerHTML = '<div class="ap-topbar-inner"><span class="ap-crumb"></span>' +
    (heads.length ? '<span class="ap-sep">›</span><span class="ap-chapter"></span>' : "") +
    '<button type="button" class="ap-top-btn">回到顶部</button></div><div class="ap-progress"><i></i></div>';
  bar.querySelector(".ap-crumb").textContent = crumb;
  main.insertBefore(bar, main.firstChild);
  var chapEl = bar.querySelector(".ap-chapter");
  var progEl = bar.querySelector(".ap-progress > i");
  bar.querySelector(".ap-top-btn").addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  });
  function chapterLabel(h) {
    var num = h.querySelector(".num");
    var c = h.cloneNode(true), n = c.querySelector(".num");
    if (n) n.remove();
    $all(".katex", c).forEach(function (k) { var a = k.querySelector("annotation"); k.replaceWith(document.createTextNode(a ? a.textContent : k.textContent)); });
    var t = c.textContent.replace(/\s+/g, " ").trim();
    if (!num) return t;
    var lab = num.getAttribute("data-label");
    if (lab === null) lab = "第 " + num.textContent.trim() + " 章";
    return lab ? lab + " · " + t : t;
  }
  var labels = heads.map(chapterLabel);
  var curChap = -2, ticking = false;
  function onScroll() {
    ticking = false;
    var y = window.scrollY, max = document.documentElement.scrollHeight - window.innerHeight;
    progEl.style.transform = "scaleX(" + (max > 0 ? Math.min(1, Math.max(0, y / max)) : 0) + ")";
    bar.classList.toggle("ap-scrolled", y > 120);
    if (chapEl) {
      var k = -1;
      for (var i = 0; i < heads.length; i++) { if (heads[i].getBoundingClientRect().top <= 90) k = i; else break; }
      if (k !== curChap) { curChap = k; chapEl.textContent = k >= 0 ? labels[k] : ""; }
    }
  }
  window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();

  /* ---------- 滚动进入视野时淡入上浮 ---------- */
  var SEL = ".box, .arch, .widget, figure, .table-wrap, .mcq, .frq, details, .pager, h2, pre, .grid2, .grid3, blockquote";
  if (!reduce && "IntersectionObserver" in window) {
    var vh = window.innerHeight;
    var targets = $all(SEL, content).filter(function (el) {
      var p = el.parentElement && el.parentElement.closest(SEL);
      if (p && content.contains(p)) return false;
      if (el.closest(".tally-bar, .exam-bar")) return false;
      return el.getBoundingClientRect().top > vh * 0.92;   /* 已经在首屏里的不藏 */
    });
    var io = new IntersectionObserver(function (entries) {
      var shown = entries.filter(function (e) { return e.isIntersecting; }).map(function (e) { return e.target; });
      shown.sort(function (a, b) { return a.getBoundingClientRect().top - b.getBoundingClientRect().top; });
      shown.forEach(function (el, i) {
        io.unobserve(el);
        el.style.setProperty("--ap-delay", Math.min(i * 70, 280) + "ms");
        el.classList.add("ap-shown");
        setTimeout(function () {
          el.classList.remove("ap-in", "ap-shown");
          el.style.removeProperty("--ap-delay");
        }, 1300 + Math.min(i * 70, 280));
      });
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0 });
    targets.forEach(function (el) { el.classList.add("ap-in"); io.observe(el); });
    window.addEventListener("beforeprint", function () {
      $all(".ap-in", content).forEach(function (el) { el.classList.remove("ap-in", "ap-shown"); });
    });
  }

  /* ---------- 逐步架构图：说明文字切换时淡入 ---------- */
  $all(".arch-now").forEach(function (now) {
    new MutationObserver(function () {
      now.classList.remove("ap-swap");
      void now.offsetWidth;
      now.classList.add("ap-swap");
    }).observe(now, { childList: true, characterData: true, subtree: true });
  });

  /* ---------- 选择题：刚作答时回弹、答错时抖动、讲解滑出 ---------- */
  var before = null;
  document.addEventListener("click", function (e) {
    var q = e.target.closest && e.target.closest(".mcq, .frq");
    before = q ? { q: q, graded: q.classList.contains("graded"), revealed: q.classList.contains("revealed") } : null;
  }, true);
  document.addEventListener("click", function () {
    if (!before) return;
    var q = before.q;
    var changed = (!before.graded && q.classList.contains("graded")) || (!before.revealed && q.classList.contains("revealed"));
    before = null;
    if (!changed) return;
    q.classList.remove("ap-just");
    void q.offsetWidth;
    q.classList.add("ap-just");
    setTimeout(function () { q.classList.remove("ap-just"); }, 900);
  });

  /* ---------- 滑块：已拖过的一段填成蓝色 ---------- */
  function fill(r) {
    var min = parseFloat(r.min || 0), max = parseFloat(r.max || 100), v = parseFloat(r.value);
    r.style.setProperty("--p", (max > min ? (v - min) / (max - min) * 100 : 0) + "%");
  }
  function fillAll(scope) { $all('input[type="range"]', scope).forEach(fill); }
  fillAll(document);
  document.addEventListener("input", function (e) { if (e.target.type === "range") fill(e.target); });
  document.addEventListener("change", function (e) { if (e.target.type === "range") fill(e.target); });
  document.addEventListener("click", function (e) {
    var w = e.target.closest && e.target.closest(".widget");
    if (w) setTimeout(function () { fillAll(w); }, 0);
  });

  /* ---------- 图片点开放大 ---------- */
  var box = null, src = null;
  function rectOf(el) { return el.getBoundingClientRect(); }
  function fromTo(big, small) {
    var a = rectOf(small), b = rectOf(big);
    var s = a.width / (b.width || 1);
    var dx = (a.left + a.width / 2) - (b.left + b.width / 2);
    var dy = (a.top + a.height / 2) - (b.top + b.height / 2);
    return "translate(" + dx + "px," + dy + "px) scale(" + s + ")";
  }
  function closeBox() {
    if (!box) return;
    var b = box, img = b.querySelector("img"), s = src;
    box = null; src = null;
    b.classList.remove("ap-open");
    if (!reduce && s && rectOf(s).bottom > 0 && rectOf(s).top < window.innerHeight) img.style.transform = fromTo(img, s);
    else img.style.opacity = "0";
    setTimeout(function () { if (s) s.style.visibility = ""; b.remove(); }, reduce ? 0 : 480);
  }
  content.addEventListener("click", function (e) {
    var img = e.target.closest && e.target.closest("figure img");
    if (!img || !content.contains(img)) return;
    e.preventDefault();
    src = img;
    box = document.createElement("div");
    box.className = "ap-lightbox";
    var big = new Image();
    big.src = img.currentSrc || img.src;
    big.alt = img.alt || "";
    box.appendChild(big);
    var cap = img.closest("figure").querySelector("figcaption");
    if (cap) {
      var c = document.createElement("div");
      c.className = "ap-cap";
      var cc = cap.cloneNode(true);
      $all(".katex-mathml", cc).forEach(function (m) { m.remove(); });
      var t = cc.textContent.replace(/\s+/g, " ").trim();
      c.textContent = t.length > 160 ? t.slice(0, 158) + "…" : t;
      box.appendChild(c);
    }
    document.body.appendChild(box);
    box.addEventListener("click", closeBox);
    function go() {
      if (!reduce) {
        big.style.transition = "none";
        big.style.transform = fromTo(big, img);
        void big.offsetWidth;
        big.style.transition = "";
      }
      img.style.visibility = "hidden";
      requestAnimationFrame(function () {
        big.style.transform = "none";
        box.classList.add("ap-open");
      });
    }
    if (big.complete) go(); else big.onload = go;
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeBox(); });
  window.addEventListener("scroll", function () { if (box) closeBox(); }, { passive: true });
})();
