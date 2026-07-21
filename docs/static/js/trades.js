// trades.js — 매매일지 카테고리 필터(design/20 Phase 8 /trades v2). tabs.js와 동일한 단순 토글
// 패턴(빌드 타임에 전 행을 렌더한 뒤 표시만 전환) — 외부 라이브러리 0.
(function (global) {
  "use strict";

  function init() {
    var bar = global.document.querySelector("[data-trade-filter]");
    var table = global.document.querySelector("[data-trade-table]");
    if (!bar || !table) return;

    bar.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-cat]");
      if (!btn) return;
      var cat = btn.getAttribute("data-cat");

      bar.querySelectorAll("[data-cat]").forEach(function (c) {
        c.setAttribute("aria-pressed", c === btn ? "true" : "false");
      });
      table.querySelectorAll("tbody tr[data-cat]").forEach(function (row) {
        row.style.display = cat === "all" || row.getAttribute("data-cat") === cat ? "" : "none";
      });
    });
  }

  if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
