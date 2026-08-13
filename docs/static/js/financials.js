// financials.js — Financial Statements 상태 A(검색)/상태 B(분석) 전환(design/06, Phase 7).
// #code=<종목코드> 해시로 상태를 전환한다(페이지 이동 없이, design/06 §1-1). 유니버스에는 있지만
// 재무 데이터가 없는 종목은 "준비되지 않음" 빈 상태를 보여준다(design/06 §3-8). 외부 라이브러리 0.
//
// 상태 A는 유니버스 전체를 나열하지 않는다(design/06 §1-1·§2-1) — 서버가 렌더한 표 행을 초기에
// 전부 감추고, 검색어에 맞는 행만 드러낸다. 검색 전 빈 화면을 막는 것은 "최근 조회" 칩이다(§9-3).
(function (global) {
  "use strict";

  var doc = global.document;
  var browseEl, detailEl;
  var searchEl, resultsEl, hintEl, noResultEl, recentEl, recentChipsEl;
  var rows = [];

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

  // 원화 BPS는 174,319.29처럼 소수부가 노이즈고, 달러 EPS는 7.46처럼 소수부가 정보다.
  // 자릿수를 값 크기로 가른다 — 1,000 이상이면 정수, 미만이면 소수 2자리.
  function num(v) {
    if (v == null) return "—";
    return v.toLocaleString("ko-KR", { maximumFractionDigits: Math.abs(v) >= 1000 ? 0 : 2 });
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

  // ── 재무 삼각형(ROE·PER·PBR) ──
  // 꼭짓점 = 원천값(주가·EPS·BPS), 변 = 그 비율. 세 지표는 독립이 아니라 한 항등식이다:
  //   좌변 PBR = 주가÷BPS · 우변 PER = 주가÷EPS · 밑변 ROE = EPS÷BPS  ⇒  PBR = PER × ROE
  // 외부 차트 라이브러리를 쓰지 않고 인라인 SVG로 그린다(이 페이지의 라이브러리 0 원칙).
  var TRI_P = [230, 96], TRI_B = [74, 316], TRI_E = [386, 316];

  function fmtPct(v) { return v == null ? "—" : v.toFixed(2) + "%"; }
  function fmtX(v) { return v == null ? "—" : v.toFixed(2) + "배"; }

  function triLine(a, b, mod) {
    return '<line class="v2-fs-tri__edge v2-fs-tri__edge--' + mod + '" x1="' + a[0] + '" y1="' + a[1]
      + '" x2="' + b[0] + '" y2="' + b[1] + '" />';
  }

  function triDot(p) {
    return '<circle class="v2-fs-tri__dot" cx="' + p[0] + '" cy="' + p[1] + '" r="5" />';
  }

  function triText(x, y, cls, anchor, text) {
    return '<text class="' + cls + '" x="' + x + '" y="' + y + '" text-anchor="' + anchor + '">'
      + escapeHtml(text) + "</text>";
  }

  function triangleSvg(t) {
    return '<svg class="v2-fs-tri__chart" viewBox="0 0 460 380" role="img" '
      + 'aria-label="재무 삼각형 — ROE ' + fmtPct(t.roe) + ", PER " + fmtX(t.per) + ", PBR " + fmtX(t.pbr) + '">'
      + triLine(TRI_P, TRI_B, "pbr") + triLine(TRI_P, TRI_E, "per") + triLine(TRI_B, TRI_E, "roe")
      + triDot(TRI_P) + triDot(TRI_B) + triDot(TRI_E)
      + triText(TRI_P[0], 56, "v2-fs-tri__vlabel", "middle", "주가")
      + triText(TRI_P[0], 78, "v2-fs-tri__vvalue", "middle", num(t.price))
      + triText(TRI_B[0], 342, "v2-fs-tri__vlabel", "middle", "BPS")
      + triText(TRI_B[0], 364, "v2-fs-tri__vvalue", "middle", num(t.bps))
      + triText(TRI_E[0], 342, "v2-fs-tri__vlabel", "middle", "EPS")
      + triText(TRI_E[0], 364, "v2-fs-tri__vvalue", "middle", num(t.eps))
      + triText(108, 186, "v2-fs-tri__elabel", "end", "PBR")
      + triText(108, 212, "v2-fs-tri__evalue v2-fs-tri__evalue--pbr", "end", fmtX(t.pbr))
      + triText(352, 186, "v2-fs-tri__elabel", "start", "PER")
      + triText(352, 212, "v2-fs-tri__evalue v2-fs-tri__evalue--per", "start", fmtX(t.per))
      + triText(TRI_P[0], 240, "v2-fs-tri__elabel", "middle", "ROE")
      + triText(TRI_P[0], 266, "v2-fs-tri__evalue v2-fs-tri__evalue--roe", "middle", fmtPct(t.roe))
      + "</svg>";
  }

  function triRow(mod, name, formula, value) {
    return '<div class="v2-fs-tri__row">'
      + '<span class="v2-fs-tri__swatch v2-fs-tri__swatch--' + mod + '"></span>'
      + '<span class="v2-fs-tri__name">' + name + "</span>"
      + '<span class="v2-fs-tri__formula">' + formula + "</span>"
      + '<span class="v2-fs-tri__num">' + value + "</span></div>";
  }

  function triHistory(series) {
    if (!series || series.length < 2) return "";
    var cells = series.map(function (r) {
      return '<span class="v2-fs-tri__hist-cell"><span class="v2-fs-tri__hist-year">' + escapeHtml(r.year)
        + '</span><span class="v2-fs-tri__hist-val">' + fmtPct(r.value) + "</span></span>";
    }).join("");
    return '<div class="v2-fs-tri__hist"><span class="v2-fs-tri__hist-title">ROE 추이</span>' + cells + "</div>";
  }

  function triangleCardHtml(t) {
    var header = '<div class="v2-card__header"><h3 class="v2-card__title">재무 삼각형 · ROE · PER · PBR</h3>'
      + (t ? '<span class="v2-card__meta">' + escapeHtml(t.latest_year) + "년</span>" : "") + "</div>";
    if (!t) {
      return '<div class="v2-card v2-card--standard v2-span-12">' + header
        + '<div class="v2-card__body"><p class="v2-hub-empty">순이익·자본총계가 없어 삼각형을 그릴 수 없습니다.</p></div></div>';
    }
    var legend = '<div class="v2-fs-tri__legend">'
      + triRow("roe", "ROE", "EPS ÷ BPS", fmtPct(t.roe))
      + triRow("per", "PER", "주가 ÷ EPS", fmtX(t.per))
      + triRow("pbr", "PBR", "주가 ÷ BPS", fmtX(t.pbr))
      + '<div class="v2-fs-tri__identity">PBR = PER × ROE</div>'
      + triHistory(t.roe_series)
      + "</div>";
    var caption = "꼭짓점은 원천값(주가·EPS·BPS), 변은 그 비율입니다. BPS는 발행주식수를 수집하지 않고 "
      + "EPS×(자본총계÷순이익)으로 유도한 근사값이라 비지배지분이 큰 기업일수록 오차가 있습니다. "
      + "밸류에이션이므로 양호/주의 판정은 붙이지 않습니다.";
    return '<div class="v2-card v2-card--standard v2-span-12">' + header
      + '<div class="v2-card__body"><div class="v2-fs-tri">' + triangleSvg(t) + legend + "</div>"
      + (t.note ? '<p class="v2-body v2-fs-sub v2-fs-tri__note">' + escapeHtml(t.note) + "</p>" : "")
      + '<p class="v2-body v2-fs-sub">' + caption + "</p></div></div>";
  }

  function detailHtml(data) {
    var strip = '<div class="v2-fs-strip"><span class="v2-fs-strip__name">' + escapeHtml(data.name) + "</span>"
      + '<span class="v2-fs-strip__meta">' + escapeHtml(data.code) + " · " + escapeHtml(data.market) + "</span>"
      + '<button type="button" class="v2-fs-back" data-fs-back>← 목록으로</button></div>';

    var g = data.growth, p = data.profitability, s = data.stability, c = data.cashflow, v = data.valuation;
    var cards = '<div class="v2-fs-groups">'
      + triangleCardHtml(data.triangle)
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
