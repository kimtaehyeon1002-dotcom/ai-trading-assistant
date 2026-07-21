// stockhub.js — Stock Hub 전역 오버레이 패널(design/05, design/20 Phase 7).
// 트리거 계약: [data-hub-trigger][data-hub-code]. 딥링크: URL 해시 #hub=<code>(tabs.js와 동일한
// 해시 라우팅 패턴 — design/22 §5-4). 유니버스 밖 종목(hub/<code>.json 404)은 빈 상태로 표시한다
// (design/21 §8). 스크림 없는 비모달 패널이라 배경 클릭은 그대로 통과시키고, 패널 바깥 클릭만
// 닫기로 처리한다(design/05 §1-4). 외부 라이브러리 0.
(function (global) {
  "use strict";

  var doc = global.document;
  var slot = null;
  var lastTrigger = null;

  var KR_MARKETS = ["KOSPI", "KOSDAQ", "KONEX", "KOSDAQ GLOBAL", "KRX"];

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function siteRoot() {
    return doc.body.getAttribute("data-root") || ".";
  }

  function hashCode() {
    var m = /(?:^|[#&])hub=([^&]+)/.exec(global.location.hash);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function clearHashParam() {
    var rest = global.location.hash.replace(/(?:^|[#&])hub=[^&]*/, "").replace(/^&/, "#");
    var clean = rest && rest !== "#" ? rest : "";
    global.history.replaceState(null, "", global.location.pathname + global.location.search + clean);
  }

  function priceFmt(v) {
    return v == null ? "—" : v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
  }

  function pctFmt(v) {
    if (v == null) return "—";
    return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2) + "%";
  }

  function amountFmt(v, market) {
    if (v == null) return "—";
    if (KR_MARKETS.indexOf(market) !== -1) {
      return (v / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 0 }) + "억";
    }
    return v >= 1e9 ? "$" + (v / 1e9).toFixed(1) + "B" : "$" + (v / 1e6).toFixed(0) + "M";
  }

  function panelHtml(data) {
    var q = data.quote;
    var changeClass = q && q.change_pct != null ? (q.change_pct >= 0 ? "up" : "down") : "flat";
    var arrow = q && q.change_pct != null ? (q.change_pct >= 0 ? "▲" : "▼") : "";
    var priceBlock = q
      ? '<div class="v2-hub-panel__price">' + priceFmt(q.close) + "</div>"
        + '<div class="v2-updown ' + changeClass + '">' + arrow + " " + pctFmt(q.change_pct) + "</div>"
        + '<div class="v2-hub-panel__asof">' + escapeHtml(q.as_of_iso) + "</div>"
        + '<div class="v2-hub-stats">'
        + '<div><div class="v2-hub-stat__label">거래대금</div><div class="v2-hub-stat__value">' + amountFmt(q.amount, data.market) + "</div></div>"
        + '<div><div class="v2-hub-stat__label">거래량</div><div class="v2-hub-stat__value">' + (q.volume != null ? q.volume.toLocaleString("ko-KR") : "—") + "</div></div>"
        + '<div><div class="v2-hub-stat__label">시가총액</div><div class="v2-hub-stat__value">' + amountFmt(q.marcap, data.market) + "</div></div>"
        + "</div>"
      : '<p class="v2-hub-empty">시세 정보가 없습니다.</p>';

    var tvHref = data.tradingview_symbol
      ? "https://www.tradingview.com/chart/?symbol=" + encodeURIComponent(data.tradingview_symbol)
      : null;
    var actions = '<div class="v2-hub-actions">'
      + (tvHref ? '<a class="v2-btn v2-btn--primary" href="' + tvHref + '" target="_blank" rel="noopener noreferrer">TradingView 차트 ↗</a>' : "")
      + '<a class="v2-btn v2-btn--ghost" href="' + siteRoot() + "/financials/index.html#code=" + encodeURIComponent(data.code) + '">재무제표 분석 →</a>'
      + "</div>";

    var newsRows = (data.related_news || []).map(function (a) {
      return '<a class="v2-hub-news-row" href="' + escapeHtml(a.link) + '" target="_blank" rel="noopener noreferrer">'
        + '<span class="v2-hub-news-row__title">' + escapeHtml(a.title) + "</span>"
        + '<span class="v2-hub-news-row__meta">' + escapeHtml(a.source) + "</span></a>";
    }).join("");
    var newsBlock = newsRows || '<p class="v2-hub-empty">최근 관련 뉴스가 없습니다.</p>';

    return '<div class="v2-hub-panel" role="dialog" aria-modal="false" aria-label="' + escapeHtml(data.name) + ' 종목 패널">'
      + '<div class="v2-hub-panel__header">'
      + '<div><span class="v2-hub-panel__name" tabindex="-1">' + escapeHtml(data.name) + "</span>"
      + '<span class="v2-hub-panel__meta">' + escapeHtml(data.code) + " · " + escapeHtml(data.market) + "</span></div>"
      + '<button type="button" class="v2-hub-panel__close" data-hub-close aria-label="패널 닫기">✕</button>'
      + "</div>"
      + '<div class="v2-hub-panel__body">' + priceBlock + actions + "</div>"
      + '<div class="v2-hub-section"><h3 class="v2-hub-section__title">다가오는 일정</h3>'
      + '<p class="v2-hub-empty">등록된 일정이 없습니다.</p></div>'
      + '<div class="v2-hub-section"><h3 class="v2-hub-section__title">관련 뉴스</h3>' + newsBlock + "</div>"
      + "</div>";
  }

  function emptyHtml(code) {
    return '<div class="v2-hub-panel" role="dialog" aria-modal="false" aria-label="종목 정보 없음">'
      + '<div class="v2-hub-panel__header"><span class="v2-hub-panel__name" tabindex="-1">' + escapeHtml(code) + "</span>"
      + '<button type="button" class="v2-hub-panel__close" data-hub-close aria-label="패널 닫기">✕</button></div>'
      + '<div class="v2-hub-panel__body"><p class="v2-hub-empty">유니버스 밖 종목입니다 — 상세 정보를 제공하지 않습니다.</p></div>'
      + "</div>";
  }

  function focusables(panel) {
    return Array.prototype.slice.call(
      panel.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')
    );
  }

  function trapKeydown(e) {
    if (!slot.firstElementChild) return;
    if (e.key === "Escape") { close(); return; }
    if (e.key !== "Tab") return;
    var items = focusables(slot.firstElementChild);
    if (!items.length) return;
    var first = items[0], last = items[items.length - 1];
    if (e.shiftKey && doc.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && doc.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  function outsideClick(e) {
    if (!slot.firstElementChild) return;
    if (e.target.closest("[data-hub-trigger]")) return; // 트리거 클릭은 open()이 교체로 처리
    if (slot.contains(e.target)) return;
    close();
  }

  function render(code, html) {
    slot.innerHTML = html;
    var panel = slot.firstElementChild;
    panel.querySelectorAll("[data-hub-close]").forEach(function (btn) {
      btn.addEventListener("click", close);
    });
    var nameEl = panel.querySelector(".v2-hub-panel__name");
    if (nameEl) nameEl.focus();
  }

  function open(code) {
    if (slot.firstElementChild && slot.getAttribute("data-hub-open") === code) return; // 동일 종목 재클릭 무동작
    slot.setAttribute("data-hub-open", code);
    var url = siteRoot() + "/data/stock/hub/" + encodeURIComponent(code) + ".json";
    global.fetch(url).then(function (res) {
      if (!res.ok) throw new Error("not found");
      return res.json();
    }).then(function (data) {
      if (slot.getAttribute("data-hub-open") !== code) return; // 응답 도착 전 다른 종목으로 교체됨
      render(code, panelHtml(data));
    }).catch(function () {
      if (slot.getAttribute("data-hub-open") !== code) return;
      render(code, emptyHtml(code));
    });
  }

  function close() {
    if (!slot.firstElementChild) return;
    slot.removeAttribute("data-hub-open");
    slot.innerHTML = "";
    clearHashParam();
    if (lastTrigger && lastTrigger.focus) lastTrigger.focus();
    lastTrigger = null;
  }

  function onHashChange() {
    var code = hashCode();
    if (code) open(code);
    else if (slot.firstElementChild) close();
  }

  function init() {
    slot = doc.getElementById("panel-slot");
    if (!slot) return;

    doc.addEventListener("click", function (e) {
      var trigger = e.target.closest("[data-hub-trigger]");
      if (!trigger) return;
      var code = trigger.getAttribute("data-hub-code");
      if (!code) return;
      lastTrigger = trigger;
      if (global.location.hash.indexOf("hub=" + encodeURIComponent(code)) !== -1) {
        open(code); // 이미 같은 해시 상태 → hashchange 미발생분 직접 처리(예: 닫힌 뒤 같은 종목 재오픈)
      } else {
        global.location.hash = "hub=" + encodeURIComponent(code);
      }
    });
    doc.addEventListener("keydown", trapKeydown);
    doc.addEventListener("click", outsideClick, true);
    global.addEventListener("hashchange", onHashChange);

    var initial = hashCode();
    if (initial) open(initial);
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();

  global.TAStockHub = { open: open, close: close };
})(window);
