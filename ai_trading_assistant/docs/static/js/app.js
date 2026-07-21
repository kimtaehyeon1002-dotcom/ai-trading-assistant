// 정적 페이지 상호작용 — 뉴스/매매 카테고리 필터(순수 JS, 의존성 0).
(function () {
  "use strict";

  // 뉴스: 카테고리 섹션 토글
  const newsFilter = document.getElementById("newsFilter");
  if (newsFilter) {
    const sections = document.querySelectorAll(".news-section");
    newsFilter.addEventListener("click", function (e) {
      const btn = e.target.closest(".chip");
      if (!btn) return;
      const cat = btn.dataset.cat;
      newsFilter.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === btn));
      sections.forEach((s) => {
        s.style.display = cat === "all" || s.dataset.cat === cat ? "" : "none";
      });
    });
  }

  // 매매일지: 행 필터
  const tradeFilter = document.getElementById("tradeFilter");
  const tradeTable = document.getElementById("tradeTable");
  if (tradeFilter && tradeTable) {
    const rows = tradeTable.querySelectorAll("tbody tr[data-cat]");
    tradeFilter.addEventListener("click", function (e) {
      const btn = e.target.closest(".chip");
      if (!btn) return;
      const cat = btn.dataset.cat;
      tradeFilter.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === btn));
      rows.forEach((r) => {
        r.style.display = cat === "all" || r.dataset.cat === cat ? "" : "none";
      });
    });
  }
})();
