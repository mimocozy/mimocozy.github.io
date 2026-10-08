/* Mimocozy shared script (homepage + /books/<slug>/ pages). No dependencies.
   - remembers PT/EN choice in localStorage (shared by every page)
   - swaps any element carrying data-pt / data-en
   - book pages: header toggle, menu, "Take a Peek Inside" gallery + lightbox (zoom, prev/next, keyboard, swipe) */
(function () {
  "use strict";
  var KEY = "mimocozy-lang";
  var Mimo = window.Mimo = {
    getLang: function () {
      try { var v = localStorage.getItem(KEY); if (v === "pt" || v === "en") return v; } catch (e) {}
      return "pt";
    },
    setLang: function (l) { try { localStorage.setItem(KEY, l); } catch (e) {} },
    applyBilingual: function (lang, root) {
      (root || document).querySelectorAll("[data-pt][data-en]").forEach(function (el) {
        var v = el.getAttribute("data-" + lang);
        var attr = el.getAttribute("data-i18n-attr");
        if (attr) el.setAttribute(attr, v); else el.textContent = v;
      });
    }
  };

  if (!document.body || document.body.getAttribute("data-page") !== "book") return;

  /* ---------- book page ---------- */
  var lang = Mimo.getLang();
  var ptBtn = document.getElementById("pt"), enBtn = document.getElementById("en");
  function setLang(l) {
    lang = l; Mimo.setLang(l); Mimo.applyBilingual(l);
    document.documentElement.lang = l;
    ptBtn.classList.toggle("on", l === "pt"); enBtn.classList.toggle("on", l === "en");
    ptBtn.setAttribute("aria-pressed", String(l === "pt")); enBtn.setAttribute("aria-pressed", String(l === "en"));
  }
  ptBtn.addEventListener("click", function () { setLang("pt"); });
  enBtn.addEventListener("click", function () { setLang("en"); });
  setLang(lang);
  var burger = document.getElementById("burger"), menu = document.getElementById("menu");
  burger.addEventListener("click", function () {
    var open = menu.classList.toggle("open"); burger.setAttribute("aria-expanded", String(open));
  });

  /* gallery items come from the thumbnail buttons (real repo images only) */
  var thumbs = Array.prototype.slice.call(document.querySelectorAll("[data-gallery-index]"));
  var items = thumbs.map(function (b) { var t = b.querySelector("img"); return { src: b.getAttribute("data-full"), get alt() { return t.getAttribute("alt") || ""; } }; });
  var mainBtn = document.getElementById("g-main-btn"), mainImg = document.getElementById("g-main-img");
  var current = 0;
  function select(i) {
    current = (i + items.length) % items.length;
    if (mainImg) {
      var t = thumbs[current].querySelector("img");
      mainImg.src = items[current].src; mainImg.alt = items[current].alt;
      if (t.getAttribute("width")) { mainImg.width = +t.getAttribute("width"); mainImg.height = +t.getAttribute("height"); }
    }
    thumbs.forEach(function (b, n) { b.setAttribute("aria-current", String(n === current)); });
  }
  thumbs.forEach(function (b, n) { b.addEventListener("click", function () { select(n); }); });
  if (mainBtn) mainBtn.addEventListener("click", function () { openLb(current, mainBtn); });
  var coverBtn = document.getElementById("cover-btn");
  if (coverBtn) coverBtn.addEventListener("click", function () { openLb(0, coverBtn); });

  /* lightbox */
  var lb = document.getElementById("light");
  if (!lb || !items.length) return;
  var stage = lb.querySelector(".lb-stage"), img = stage.querySelector("img");
  var count = lb.querySelector(".lb-count"), zoomBtn = lb.querySelector(".lb-zoom");
  var idx = 0, opener = null, zoomed = false;
  var L = { pt: { zin: "Ampliar +", zout: "Reduzir −" }, en: { zin: "Zoom in +", zout: "Zoom out −" } };
  function setZoom(z, ev) {
    zoomed = z; stage.classList.toggle("zoomed", z);
    zoomBtn.textContent = z ? L[lang].zout : L[lang].zin;
    zoomBtn.setAttribute("aria-pressed", String(z));
    if (z) {
      var w = Math.min(img.naturalWidth || 1600, Math.max(stage.clientWidth * 2, 900));
      img.style.width = w + "px";
      var rx = 0.5, ry = 0.5;
      if (ev && ev.target === img) { var r = img.getBoundingClientRect(); rx = (ev.clientX - r.left) / r.width; ry = (ev.clientY - r.top) / r.height; }
      requestAnimationFrame(function () {
        stage.scrollLeft = img.offsetWidth * rx - stage.clientWidth / 2;
        stage.scrollTop = img.offsetHeight * ry - stage.clientHeight / 2;
      });
    } else { img.style.width = ""; stage.scrollTop = 0; stage.scrollLeft = 0; }
  }
  function show(i) {
    idx = (i + items.length) % items.length;
    setZoom(false);
    img.src = items[idx].src; img.alt = items[idx].alt;
    count.textContent = (idx + 1) + " / " + items.length;
  }
  function openLb(i, from) {
    opener = from || document.activeElement;
    show(i); lb.hidden = false; lb.classList.add("open");
    document.body.style.overflow = "hidden";
    lb.querySelector(".lb-close").focus();
  }
  function closeLb() {
    lb.classList.remove("open"); lb.hidden = true; setZoom(false);
    document.body.style.overflow = "";
    if (opener && opener.focus) opener.focus();
  }
  lb.querySelector(".lb-close").addEventListener("click", closeLb);
  lb.querySelector(".lb-prev").addEventListener("click", function () { show(idx - 1); });
  lb.querySelector(".lb-next").addEventListener("click", function () { show(idx + 1); });
  zoomBtn.addEventListener("click", function () { setZoom(!zoomed); });
  img.addEventListener("click", function (e) { e.stopPropagation(); setZoom(!zoomed, e); });
  stage.addEventListener("click", function (e) { if (e.target === stage && !zoomed) closeLb(); });
  lb.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { e.preventDefault(); closeLb(); }
    else if (e.key === "ArrowLeft" && !zoomed) { e.preventDefault(); show(idx - 1); }
    else if (e.key === "ArrowRight" && !zoomed) { e.preventDefault(); show(idx + 1); }
    else if (e.key === "+" || e.key === "=" || e.key === "z") { setZoom(true); }
    else if (e.key === "-" || e.key === "0") { setZoom(false); }
    else if (e.key === "Tab") { /* keep focus inside the dialog */
      var f = Array.prototype.slice.call(lb.querySelectorAll("button"));
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  var sx = null, sy = null;
  stage.addEventListener("touchstart", function (e) { if (zoomed || e.touches.length > 1) { sx = null; return; } sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, { passive: true });
  stage.addEventListener("touchend", function (e) {
    if (sx === null) return;
    var dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.3) show(idx + (dx < 0 ? 1 : -1));
    sx = null;
  }, { passive: true });
})();
