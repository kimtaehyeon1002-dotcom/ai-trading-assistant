// macro-live.js — Macro "금융시장" 스트립의 라이브 적용기(design/02, design/25 §10).
// 폴링·라이브 판정·플래시는 live.js가 하고, 여기는 market_strip.json을 타일 DOM에
// 반영하는 일만 한다(엔진과 페이지 지식의 분리).
//
// 표기는 서버 Jinja 필터(price/pctv2/arrow/signclass)와 **같은 규칙**이어야 한다 —
// 갱신 전후로 소수 자릿수나 부호 기호가 달라지면 값이 바뀐 것처럼 보인다.
(function (global) {
  "use strict";

  var doc = global.document;

  // generators/base.py의 _price와 동일 규칙: 1000 미만은 소수 2자리, 이상은 정수.
  function price(v) {
    if (v == null) return "—";
    return Math.abs(v) < 1000
      ? v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
  }

  // _pctv2와 동일: 진짜 마이너스 U+2212(design/00 §3-3).
  function pctv2(v) {
    if (v == null) return "—";
    return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2) + "%";
  }

  function arrow(v) { return v == null ? "" : v >= 0 ? "▲" : "▼"; }
  function signClass(v) { return v == null ? "flat" : v >= 0 ? "up" : "down"; }

  function setUpdown(el, v) {
    if (!el) return false;
    var next = (arrow(v) + " " + pctv2(v)).trim();
    if (el.textContent.trim() === next) return false;
    el.textContent = next;
    el.classList.remove("up", "down", "flat");
    el.classList.add(signClass(v));
    return true;
  }

  function tilesOf(data) {
    var out = {};
    (data || []).forEach(function (g) {
      (g.tiles || []).forEach(function (t) { out[t.key] = t; });
    });
    return out;
  }

  /** 페이로드 전체의 기준시각 = 타일들 중 가장 최신 as_of_iso.
   *  가장 오래된 값을 쓰면 한 심볼의 결측이 페이지 전체를 STALE로 끌어내린다. */
  function asOf(data) {
    var best = null;
    (data || []).forEach(function (g) {
      (g.tiles || []).forEach(function (t) {
        if (!t.as_of_iso) return;
        if (!best || t.as_of_iso > best) best = t.as_of_iso;
      });
    });
    return best;
  }

  function apply(data, root, ctx) {
    var byKey = tilesOf(data);
    Array.prototype.forEach.call(root.querySelectorAll("[data-live-key]"), function (tile) {
      var t = byKey[tile.getAttribute("data-live-key")];
      if (!t) return;

      var valueEl = tile.querySelector(".v2-macro-tile__value");
      if (valueEl && t.price != null) {
        var unit = tile.getAttribute("data-live-unit") === "%" ? "%" : "";
        var next = price(t.price) + unit;
        if (valueEl.textContent.trim() !== next) {
          var prev = parseFloat(valueEl.textContent.replace(/[^\d.\-]/g, ""));
          valueEl.textContent = next;
          // 첫 적용(발행값과 동일 확인)에서는 번쩍이지 않는다 — 바뀐 게 없기 때문이다.
          if (!ctx.first && !isNaN(prev)) ctx.flash(valueEl, t.price - prev);
        }
      }

      setUpdown(tile.querySelector(".v2-macro-tile__rates > .v2-updown"), t.change_pct);
      setUpdown(tile.querySelector(".v2-macro-tile__period .v2-updown"), t.period_change_pct);

      var chart = tile.querySelector(".v2-chart");
      if (chart && global.TAChart && t.closes && t.closes.length > 1) {
        global.TAChart.setData(chart, t.closes, t.dates && t.dates.length === t.closes.length ? t.dates : null);
      }
    });
  }

  function boot() {
    if (!global.TALive) return;
    global.TALive.registerApplier("macro-strip", { apply: apply, asOf: asOf });
    global.TALive.init(doc);
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", boot);
  else boot();
})(window);
