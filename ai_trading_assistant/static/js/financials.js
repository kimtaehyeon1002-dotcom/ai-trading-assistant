// financials.js — Financial Statements 상태 A(목록)/상태 B(분석) 전환(design/06, Phase 7).
// #code=<종목코드> 해시로 상태를 전환한다(페이지 이동 없이, design/06 §1-1). 유니버스에는 있지만
// 재무 데이터가 없는 종목은 "준비되지 않음" 빈 상태를 보여준다(design/06 §3-8). 외부 라이브러리 0.
(function (global) {
  "use strict";

  var doc = global.document;
  var browseEl, detailEl;

  var JUDGMENT_LABEL = { good: "양호", neutral: "중립", caution: "주의" };

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function siteRoot() {
    return doc.body.getAttribute("data-root") || ".";
  }

  function hashCode() {
    var m = /(?:^|[#&])code=([^&]+)/.exec(global.location.hash);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function clearHash() {
    var rest = global.location.hash.replace(/(?:^|[#&])code=[^&]*/, "").replace(/^&/, "#");
    global.history.replaceState(null, "", global.location.pathname + global.location.search + (rest && rest !== "#" ? rest : ""));
  }

  function badge(j) {
    if (!j) return "";
    return '<span class="v2-fs-badge v2-fs-badge--' + j + '">' + JUDGMENT_LABEL[j] + "</span>";
  }

  function pct(v) {
    if (v == null) return "—";
    return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2) + "%";
  }

  function num(v) {
    return v == null ? "—" : v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
  }

  function cardHtml(title, item, valueHtml, subText) {
    if (!item) {
      return '<div class="v2-card v2-card--standard v2-span-4"><div class="v2-card__header"><h3 class="v2-card__title">' + title + "</h3></div>"
        + '<div class="v2-card__body"><p class="v2-hub-empty">데이터가 없습니다.</p></div></div>';
    }
    return '<div class="v2-card v2-card--standard v2-span-4">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">' + title + '</h3><span class="v2-card__meta">' + escapeHtml(item.latest_year) + "년</span></div>"
      + '<div class="v2-card__body"><div class="v2-fs-value">' + valueHtml + "" + badge(item.judgment) + "</div>"
      + '<p class="v2-body v2-fs-sub">' + subText + "</p></div></div>";
  }

  function detailHtml(data) {
    var strip = '<div class="v2-fs-strip"><span class="v2-fs-strip__name">' + escapeHtml(data.name) + "</span>"
      + '<span class="v2-fs-strip__meta">' + escapeHtml(data.code) + " · " + escapeHtml(data.market) + "</span>"
      + '<button type="button" class="v2-fs-back" data-fs-back>← 목록으로</button></div>';

    var g = data.growth, p = data.profitability, s = data.stability, c = data.cashflow, v = data.valuation;
    var cards = '<div class="v2-fs-groups">'
      + cardHtml("매출액 성장", g, pct(g && g.value), g ? ("3y CAGR " + pct(g.cagr_pct)) : "")
      + cardHtml("영업이익률", p, p ? p.value.toFixed(2) + "%" : "", p ? ("자사 5y 평균 " + p.own_5y_avg.toFixed(2) + "% 대비") : "")
      + cardHtml("부채비율", s, s ? s.value.toFixed(2) + "%" : "", "100% 미만 양호 · 100~200% 중립 · 200% 초과 주의")
      + cardHtml("잉여현금흐름(FCF)", c, c ? num(c.value) : "", "FCF = 영업CF − CAPEX")
      + (v
        ? '<div class="v2-card v2-card--standard v2-span-4"><div class="v2-card__header"><h3 class="v2-card__title">밸류에이션(PER)</h3><span class="v2-card__meta">' + escapeHtml(v.latest_year) + "년</span></div>"
          + '<div class="v2-card__body"><div class="v2-fs-value">' + (v.per != null ? v.per.toFixed(2) + "배" : "—") + "</div>"
          + '<p class="v2-body v2-fs-sub">' + (v.note || "종가 ÷ 최근 EPS(" + num(v.eps) + ") — 5년 밴드는 미제공(판정 미적용)") + "</p></div></div>"
        : cardHtml("밸류에이션(PER)", null, "", ""))
      + "</div>";

    return strip + cards;
  }

  function noDataHtml(code) {
    return '<div class="v2-fs-strip"><span class="v2-fs-strip__name">' + escapeHtml(code) + "</span>"
      + '<button type="button" class="v2-fs-back" data-fs-back>← 목록으로</button></div>'
      + '<p class="v2-hub-empty">이 종목의 재무 데이터가 아직 준비되지 않았습니다.</p>';
  }

  function showDetail(html) {
    browseEl.hidden = true;
    detailEl.hidden = false;
    detailEl.innerHTML = html;
    var back = detailEl.querySelector("[data-fs-back]");
    if (back) back.addEventListener("click", function () { clearHash(); showBrowse(); });
  }

  function showBrowse() {
    browseEl.hidden = false;
    detailEl.hidden = true;
    detailEl.innerHTML = "";
  }

  function open(code) {
    var url = siteRoot() + "/data/financials/" + encodeURIComponent(code) + ".json";
    global.fetch(url).then(function (res) {
      if (!res.ok) throw new Error("not found");
      return res.json();
    }).then(function (data) {
      showDetail(detailHtml(data));
    }).catch(function () {
      showDetail(noDataHtml(code));
    });
  }

  function onHashChange() {
    var code = hashCode();
    if (code) open(code);
    else showBrowse();
  }

  function init() {
    browseEl = doc.getElementById("fs-browse");
    detailEl = doc.getElementById("fs-detail");
    if (!browseEl || !detailEl) return;

    doc.addEventListener("click", function (e) {
      var trigger = e.target.closest("[data-fs-trigger]");
      if (!trigger) return;
      global.location.hash = "code=" + encodeURIComponent(trigger.getAttribute("data-fs-code"));
    });
    global.addEventListener("hashchange", onHashChange);

    var initial = hashCode();
    if (initial) open(initial);
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
