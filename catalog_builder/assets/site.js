/* IECC digital catalog: year switcher, edition banner, search, course filters, addenda, mobile menu. No dependencies. */
(function () {
  "use strict";
  var ED = window.IECC_EDITION || {};
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var page = location.pathname.split("/").pop() || "index.html";

  /* ---- year switcher (catalog-years.js lives at the publish root, so old editions see new years) */
  function years() {
    var sel = $("#year-switch"), list = window.IECC_YEARS;
    if (!sel || !list || !list.length) { if (sel) sel.closest("label").hidden = true; return; }
    sel.innerHTML = list.map(function (y) {
      return '<option value="' + y.slug + '"' + (y.slug === (ED.kind === "current" ? "current" : ED.slug) ? " selected" : "") + ">" + esc(y.label) + "</option>";
    }).join("");
    sel.addEventListener("change", function () { location.href = "../" + sel.value + "/" + page + location.hash; });
  }

  /* ---- banner: which edition is this? */
  function banner() {
    var b = $("#edition-banner"); if (!b) return;
    var add = window.IECC_ADDENDA || [];
    var addTxt = add.length ? ' · <a href="addenda.html">' + add.length + " addend" + (add.length === 1 ? "um" : "a") + "</a>" : "";
    if (ED.kind === "current") {
      b.innerHTML = "This is the current catalog, updated " + esc(ED.built) + ". Students follow the catalog for the year they entered (Board Policy 500.36)" +
        (ED.record ? ': <a href="../' + esc(ED.record) + "/" + page + '">see the ' + esc(ED.year) + " edition of record</a>" : "") + "." + addTxt;
    } else {
      b.className = "banner record";
      b.innerHTML = "<b>" + esc(ED.year) + " edition of record</b>, published " + esc(ED.built) + ". It applies to students who entered in " + esc(ED.year) +
        ' (Board Policy 500.36). <a href="../current/' + page + '">View the current catalog</a>' + addTxt;
    }
  }

  /* ---- search */
  function norm(s) { return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9 ]+/g, " "); }
  var idx = null;
  function index() {
    if (idx) return idx;
    idx = (window.IECC_SEARCH || []).map(function (e) { return { e: e, t: norm(e.t), x: norm(e.x || ""), k: norm(e.k || "") }; });
    return idx;
  }
  function find(q) {
    var words = norm(q).split(" ").filter(Boolean); if (!words.length) return [];
    var joined = words.join("");
    var out = [];
    index().forEach(function (r) {
      var s = 0, ok = true;
      words.forEach(function (w) {
        var i = r.t.indexOf(w);
        if (i === 0) s += 6; else if (i > 0) s += (r.t.charAt(i - 1) === " " ? 4 : 2);
        else if (r.k.indexOf(w) >= 0) s += 1;
        else if (r.x.indexOf(w) >= 0) s += 1;
        else ok = false;
      });
      if (!ok && r.t.replace(/ /g, "").indexOf(joined) === 0) { ok = true; s = 8; } /* "eng101" → "ENG 1111" */
      if (ok) { if (r.e.k.indexOf("Program") === 0) s += 3; if (r.e.k === "Section") s += 2; out.push({ s: s - r.t.length / 200, e: r.e }); }
    });
    return out.sort(function (a, b) { return b.s - a.s; }).slice(0, 12).map(function (r) { return r.e; });
  }
  function hl(t, q) {
    var h = esc(t);
    norm(q).split(" ").filter(function (w) { return w.length > 1; }).forEach(function (w) {
      h = h.replace(new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"), "<mark>$1</mark>");
    });
    return h;
  }
  function wireSearch(input, box) {
    var sel = -1;
    function render() {
      var q = input.value.trim(), res = q.length > 1 ? find(q) : [];
      sel = -1;
      if (!q || q.length < 2) { box.hidden = true; input.setAttribute("aria-expanded", "false"); return; }
      box.innerHTML = res.length ? res.map(function (e, i) {
        return '<a role="option" id="r' + i + '" href="' + e.u + '"><small>' + esc(e.k) + "</small><b>" + hl(e.t, q) + "</b>" + (e.x ? "<span>" + esc(e.x) + "</span>" : "") + "</a>";
      }).join("") : '<div class="none">No matches. Try a program name, a course code like ENG 1111, or a topic like “refund”.</div>';
      box.hidden = false; input.setAttribute("aria-expanded", "true");
    }
    function move(d) {
      var a = $$("a", box); if (!a.length) return;
      sel = (sel + d + a.length) % a.length;
      a.forEach(function (x, i) { x.setAttribute("aria-selected", i === sel ? "true" : "false"); });
      input.setAttribute("aria-activedescendant", a[sel].id); a[sel].scrollIntoView({ block: "nearest" });
    }
    input.addEventListener("input", render);
    input.addEventListener("focus", render);
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") { var a = $$("a", box)[Math.max(sel, 0)]; if (a) { e.preventDefault(); location.href = a.href; } }
      else if (e.key === "Escape") { box.hidden = true; input.blur(); }
    });
    document.addEventListener("click", function (e) { if (!box.contains(e.target) && e.target !== input) box.hidden = true; });
  }
  function search() {
    var q = $("#q"), box = $("#results");
    if (q && box) wireSearch(q, box);
    var q2 = $("#q2");
    if (q2 && box) { /* hero search drives the same results panel, placed under the hero box */
      var box2 = box.cloneNode(); box2.id = "results2"; box2.style.position = "absolute"; box2.style.left = "0"; box2.style.right = "auto";
      q2.parentNode.style.position = "relative"; q2.parentNode.appendChild(box2); wireSearch(q2, box2);
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && !/input|select|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); (q2 || q).focus(); }
    });
  }

  /* ---- course filters */
  function filters() {
    var list = $("#course-list"); if (!list) return;
    var subj = $("#f-subj"), text = $("#f-text"), count = $("#f-count"), boxes = $$(".filters input[type=checkbox]");
    var courses = $$(".course", list).map(function (el) {
      return { el: el, sec: el.parentNode, t: norm(el.textContent), camps: $$(".camp i.on", el).map(function (i) { return i.className.split(" ")[1]; }) };
    });
    function apply() {
      var s = subj.value, words = norm(text.value).split(" ").filter(Boolean), joined = words.join(""),
        camps = boxes.filter(function (b) { return b.checked; }).map(function (b) { return b.value; }), n = 0;
      courses.forEach(function (c) {
        var ok = (!s || c.sec.getAttribute("data-p") === s) &&
          (!camps.length || camps.some(function (x) { return c.camps.indexOf(x) >= 0; })) &&
          (!words.length || words.every(function (w) { return c.t.indexOf(w) >= 0; }) || c.t.replace(/ /g, "").indexOf(joined) >= 0);
        c.el.hidden = !ok; if (ok) n++;
      });
      $$(".subject", list).forEach(function (sec) { sec.hidden = !$(".course:not([hidden])", sec); });
      count.textContent = n.toLocaleString() + " course" + (n === 1 ? "" : "s");
    }
    [subj, text].forEach(function (el) { el.addEventListener("input", apply); });
    boxes.forEach(function (b) { b.addEventListener("change", apply); });
    var m = location.hash.match(/^#s-([A-Z]{3})$/); if (m) subj.value = m[1];
    apply();
    window.addEventListener("hashchange", function () { /* a search result for a hidden course: clear filters */
      var t = location.hash && document.getElementById(location.hash.slice(1));
      if (t && (t.hidden || (t.parentNode && t.parentNode.hidden))) { subj.value = ""; text.value = ""; boxes.forEach(function (b) { b.checked = false; }); apply(); t.scrollIntoView(); }
    });
  }

  /* ---- addenda page */
  function addenda() {
    var el = $("#addenda-list"); if (!el) return;
    var a = (window.IECC_ADDENDA || []).slice().sort(function (x, y) { return (y.effective || "").localeCompare(x.effective || ""); });
    el.innerHTML = a.length ? a.map(function (d) {
      return "<article><p class=eff>Addendum " + esc(d.number) + " · Effective " + esc(d.effective) + "</p><h2>" + esc(d.title) + "</h2><p>" + esc(d.summary || "") + "</p>" +
        (d.pdf ? '<p><a href="' + esc(d.pdf) + '">Download addendum (PDF)</a></p>' : "") + "</article>";
    }).join("") : "<p>No addenda have been issued for this catalog.</p>";
  }

  /* ---- mobile menu + highlight the heading you're reading */
  function menu() {
    var b = $(".menu"), side = $("#side"); if (!b || !side) { if (b) b.hidden = true; return; }
    b.addEventListener("click", function () { var o = side.classList.toggle("open"); b.setAttribute("aria-expanded", o); });
    side.addEventListener("click", function (e) { if (e.target.tagName === "A") side.classList.remove("open"); });
    var links = $$(".side li.cur ul a"); if (!links.length || !("IntersectionObserver" in window)) return;
    var map = {}; links.forEach(function (a) { map[a.getAttribute("href").slice(1)] = a; });
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) { if (en.isIntersecting && map[en.target.id]) { links.forEach(function (a) { a.classList.remove("on"); }); map[en.target.id].classList.add("on"); } });
    }, { rootMargin: "-90px 0px -70% 0px" });
    Object.keys(map).forEach(function (id) { var t = document.getElementById(id); if (t) io.observe(t); });
  }

  function init() { years(); banner(); search(); filters(); addenda(); menu(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
