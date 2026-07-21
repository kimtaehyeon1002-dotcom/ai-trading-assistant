// search.js — 글로벌 검색(design/00 §7-2, design/20 Phase 7). Ctrl/⌘+K 또는 검색창 클릭으로
// 결과 드롭다운을 연다. 그룹 3종(종목/뉴스/페이지) 각 최대 5건, ↑↓ 탐색, Enter 이동(종목은
// Stock Hub 해시 오픈 — stockhub.js와 동일한 #hub=<code> 계약, design/05 §1-1), Esc 닫기.
// 외부 라이브러리 0.
(function (global) {
  "use strict";

  var doc = global.document;
  var indexPromise = null;
  var input, resultsEl, wrap;
  var items = [];
  var activeIndex = -1;

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function siteRoot() {
    return doc.body.getAttribute("data-root") || ".";
  }

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = global.fetch(siteRoot() + "/data/search-index.json")
        .then(function (r) { return r.ok ? r.json() : { stocks: [], news: [], pages: [] }; })
        .catch(function () { return { stocks: [], news: [], pages: [] }; });
    }
    return indexPromise;
  }

  function matches(text, q) {
    return String(text || "").toLowerCase().indexOf(q) !== -1;
  }

  function filterGroup(list, q, textFields, limit) {
    var out = [];
    for (var i = 0; i < list.length && out.length < limit; i++) {
      var row = list[i];
      for (var j = 0; j < textFields.length; j++) {
        if (matches(row[textFields[j]], q)) { out.push(row); break; }
      }
    }
    return out;
  }

  function itemHtml(kind, r) {
    if (kind === "stock") {
      return '<div class="v2-search-item" data-kind="stock" data-code="' + escapeHtml(r.code) + '" role="option">'
        + '<span class="v2-search-item__main"><span class="v2-search-item__title">' + escapeHtml(r.name) + "</span>"
        + '<span class="v2-search-item__sub">' + escapeHtml(r.code) + "</span></span>"
        + '<span class="v2-search-item__sub">' + escapeHtml(r.market) + "</span></div>";
    }
    if (kind === "news") {
      return '<div class="v2-search-item" data-kind="news" data-link="' + escapeHtml(r.link) + '" role="option">'
        + '<span class="v2-search-item__main"><span class="v2-search-item__title">' + escapeHtml(r.title) + "</span></span>"
        + '<span class="v2-search-item__sub">' + escapeHtml(r.source) + "</span></div>";
    }
    return '<div class="v2-search-item" data-kind="page" data-href="' + escapeHtml(r.href) + '" role="option">'
      + '<span class="v2-search-item__main"><span class="v2-search-item__title">' + escapeHtml(r.label) + "</span></span></div>";
  }

  function groupHtml(title, rows, kind) {
    if (!rows.length) return "";
    return '<div class="v2-search-group"><div class="v2-search-group__title">' + title + "</div>"
      + rows.map(function (r) { return itemHtml(kind, r); }).join("") + "</div>";
  }

  function render(index, q) {
    var stocks = filterGroup(index.stocks || [], q, ["name", "code"], 5);
    var news = filterGroup(index.news || [], q, ["title"], 5);
    var pages = filterGroup(index.pages || [], q, ["label"], 5);
    var html = groupHtml("종목", stocks, "stock") + groupHtml("뉴스", news, "news") + groupHtml("페이지", pages, "page");
    resultsEl.innerHTML = html || '<p class="v2-search-empty">검색 결과가 없습니다.</p>';
    items = Array.prototype.slice.call(resultsEl.querySelectorAll(".v2-search-item"));
    activeIndex = -1;
    resultsEl.hidden = false;
  }

  function setActive(i) {
    items.forEach(function (el) { el.removeAttribute("aria-selected"); });
    activeIndex = Math.max(-1, Math.min(i, items.length - 1));
    if (activeIndex >= 0) {
      items[activeIndex].setAttribute("aria-selected", "true");
      items[activeIndex].scrollIntoView({ block: "nearest" });
    }
  }

  function activate(el) {
    if (!el) return;
    var kind = el.getAttribute("data-kind");
    if (kind === "stock") {
      global.location.hash = "hub=" + encodeURIComponent(el.getAttribute("data-code"));
    } else if (kind === "news") {
      global.open(el.getAttribute("data-link"), "_blank", "noopener,noreferrer");
    } else if (kind === "page") {
      global.location.href = siteRoot() + el.getAttribute("data-href");
    }
    close();
  }

  function close() {
    resultsEl.hidden = true;
    resultsEl.innerHTML = "";
    items = [];
    activeIndex = -1;
  }

  function onInput() {
    var q = input.value.trim().toLowerCase();
    if (!q) { close(); return; }
    loadIndex().then(function (idx) { render(idx, q); });
  }

  function openPalette() {
    input.focus();
    if (input.value.trim()) onInput();
  }

  function onKeydown(e) {
    if (e.key === "Escape") { close(); input.blur(); return; }
    if (resultsEl.hidden) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive(activeIndex + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive(activeIndex - 1); }
    else if (e.key === "Enter") {
      e.preventDefault();
      activate(activeIndex >= 0 ? items[activeIndex] : items[0]);
    }
  }

  function init() {
    wrap = doc.querySelector(".v2-header__search");
    input = doc.querySelector("[data-search-input]");
    resultsEl = doc.querySelector("[data-search-results]");
    if (!wrap || !input || !resultsEl) return;

    input.addEventListener("input", onInput);
    input.addEventListener("keydown", onKeydown);
    resultsEl.addEventListener("click", function (e) {
      activate(e.target.closest(".v2-search-item"));
    });
    doc.addEventListener("click", function (e) {
      if (!wrap.contains(e.target)) close();
    });
    global.addEventListener("keydown", function (e) {
      var isK = e.key === "k" || e.key === "K";
      if (isK && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        openPalette();
      }
    });
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
