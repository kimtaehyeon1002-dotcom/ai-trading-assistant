// asset-format.js — Asset·Portfolio 공용 표기 규칙(design/08 §3-3·§1-3, design/21 §6-2).
// 두 페이지가 각자 포맷 함수를 복제하던 동안 표기가 갈라졌다(가림 상태에서 통화기호가
// 바뀌고, USD가 원화식 정수로 반올림되는 등) — 규칙은 여기 한 곳에만 둔다. 외부 라이브러리 0.
(function (global) {
  "use strict";

  var SYMBOL = { KRW: "₩", USD: "$", USDT: "$" };

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function symbolOf(currency) {
    return SYMBOL[currency] || "₩";
  }

  /** 통화별 금액 문자열. 원화는 원 단위 정수, 외화는 소수 2자리(design/08 §3-3). */
  function money(value, currency) {
    if (value == null) return "—";
    var symbol = symbolOf(currency);
    if (symbol === "₩") return "₩" + Math.round(value).toLocaleString("ko-KR");
    return "$" + value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  /** 수량 — 주식은 정수, 코인은 소수가 유의미하므로 최대 8자리까지 살린다. */
  function quantity(value) {
    if (value == null) return "—";
    return value.toLocaleString("en-US", { maximumFractionDigits: 8 });
  }

  function price(value, currency) {
    return value == null ? "—" : money(value, currency);
  }

  function pct(value, digits) {
    if (value == null) return "—";
    var d = digits == null ? 2 : digits;
    return (value >= 0 ? "+" : "−") + Math.abs(value).toFixed(d) + "%";
  }

  function signClass(value) {
    return value == null ? "flat" : value >= 0 ? "up" : "down";
  }

  function arrow(value) {
    return value == null ? "" : value >= 0 ? "▲ " : "▼ ";
  }

  /**
   * 절대 금액 1개를 실제값 + 마스킹값 두 겹으로 그린다.
   * 마스킹은 고정 6도트·콤마 없음·공백 없음이며 **통화기호는 실제값과 동일**해야 한다
   * (design/08 §1-3). 기호가 달라지면 가림을 켜고 끌 때마다 통화가 바뀌는 것처럼 보인다.
   * 자릿수를 살리면 자산 규모가 유출되므로 도트 개수는 항상 6개로 고정한다.
   */
  function amount(value, currency) {
    var symbol = symbolOf(currency);
    return '<span class="v2-amount"><span class="v2-amount__real">' + escapeHtml(money(value, currency))
      + '</span><span class="v2-amount__masked">' + symbol + "••••••</span></span>";
  }

  /**
   * 손익처럼 방향이 있는 금액(design/08 §3-2 총수익, §3-4 평가손익)은 부호를 병행한다 —
   * 등락색만으로 방향을 전달하지 않는다(R4: 색 + 기호 이중 채널).
   */
  function signedAmount(value, currency) {
    if (value == null) return amount(null, currency);
    var symbol = symbolOf(currency);
    var sign = value >= 0 ? "+" : "−";
    return '<span class="v2-amount"><span class="v2-amount__real">' + sign
      + escapeHtml(money(Math.abs(value), currency))
      + '</span><span class="v2-amount__masked">' + sign + symbol + "••••••</span></span>";
  }

  /** ISO(UTC) → "07/10 07:12 KST 기준"(design/08 §3-8: 타임스탬프 없는 금액 렌더링 금지). */
  function asOf(iso) {
    var d = iso ? new Date(iso) : null;
    if (!d || isNaN(d.getTime())) return "";
    var kst = new Date(d.getTime() + (9 * 60 + d.getTimezoneOffset()) * 60000);
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return p(kst.getMonth() + 1) + "/" + p(kst.getDate()) + " " + p(kst.getHours()) + ":" + p(kst.getMinutes()) + " KST 기준";
  }

  // 자산 신선도 — T=24h 단일 규칙(design/21 §6-2: FRESH ≤26h, DELAYED ≤50h, 그 외 STALE).
  // 판정·시계 보정은 전역 freshness.js가 이미 하므로(data-asof를 읽어 data-freshness를 부여)
  // 여기서는 그 계약에 필요한 속성과 배지 마크업만 만든다 — 판정 로직을 두 벌로 만들지 않는다.
  var FRESH_MAX_MIN = 26 * 60;
  var STALE_MIN_MIN = 50 * 60;

  /** 카드 루트에 붙일 속성 문자열. 이게 있어야 freshness.js가 그 카드를 강등시킨다. */
  function freshnessAttrs(iso) {
    if (!iso) return "";
    return ' data-asof="' + escapeHtml(iso) + '" data-fresh-max-min="' + FRESH_MAX_MIN
      + '" data-stale-min-min="' + STALE_MIN_MIN + '"';
  }

  /** DELAYED/STALE일 때만 CSS가 보여주는 배지 2종(FRESH면 아무것도 안 보인다). */
  function freshnessBadges() {
    return '<span class="v2-badge v2-freshness-badge v2-freshness-badge--delayed">지연</span>'
      + '<span class="v2-badge v2-freshness-badge v2-freshness-badge--stale">오래된 데이터</span>';
  }

  global.TAAssetFormat = {
    escapeHtml: escapeHtml,
    symbolOf: symbolOf,
    money: money,
    quantity: quantity,
    price: price,
    pct: pct,
    signClass: signClass,
    arrow: arrow,
    amount: amount,
    signedAmount: signedAmount,
    asOf: asOf,
    freshnessAttrs: freshnessAttrs,
    freshnessBadges: freshnessBadges,
  };
})(window);
