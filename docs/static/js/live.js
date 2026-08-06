// live.js — 라이브 갱신 엔진 + 라이브 표시 유틸(design/00 §7-3·§9-2·§9-4·§10-2). 외부 의존 0.
//
// 이 사이트는 정적 발행물이고 데이터는 크론이 만든 JSON 파일이다. 그런데 그 JSON은 페이지와
// **같은 오리진의 정적 파일**이라, 페이지가 스스로 다시 받아올 수 있다. 서버도 소켓도 없이
// 값이 실제로 갱신된다 — 여기서 "라이브처럼 보이게" 하는 게 아니라 **정말 라이브로 만든다**.
//
// 정직성 계약(design/00 §9-2 S2 — 실제 사고에서 나온 규칙이다):
//   · 라이브 점·펄스는 **데이터가 FRESH일 때만** 켠다. 판정 기준은 내려받은 시각이 아니라
//     데이터 자신의 as_of다. 1시간 묵은 값을 방금 받았다고 라이브라 부르면 그게 거짓말이다.
//   · 폴링이 실패하거나 탭이 숨겨져 실제로 안 받아오는 동안에는 라이브 표시를 끈다.
//   · 다음 갱신 시각은 "예정"으로만 말한다 — CI는 지연될 수 있고 우리가 보장하지 못한다.
//
// 마크업 계약:
//   <div data-live-src="../data/macro/market_strip.json" data-live-kind="macro-strip"
//        data-live-interval="60" data-live-cadence-min="60" data-fresh-max-min="120"
//        data-stale-min-min="180">
//   <span data-live-since="<ISO>">      ← "12분 전 갱신"으로 매 15초 갱신
//   <span data-live-next>               ← "다음 수집 예정 ~18분 후"
//   루트에 data-live="on|off"가 부여된다 — CSS가 이 값으로 펄스를 켜고 끈다.
(function (global) {
  "use strict";

  var doc = global.document;
  var TICK_MS = 15000;          // 상대시각 갱신 주기. 1초 틱은 정보량 없이 시선만 끈다.
  var MIN_INTERVAL_MS = 30000;  // 정적 파일 폴링이라도 30초보다 자주 두드릴 이유가 없다
  var MAX_FAILS = 5;            // 연속 실패가 이만큼이면 폴링을 접는다(무한 재시도 금지)

  var appliers = {};            // kind → apply(data, root) — 페이지별 모듈이 등록한다
  var feeds = [];

  function now() {
    // 시계 보정은 freshness.js가 이미 1회 측정해 둔다 — 두 곳에서 중복 구현하지 않는다.
    return global.TAFreshness ? global.TAFreshness.correctedNow() : new Date();
  }

  function num(el, attr, dflt) {
    var v = el.getAttribute(attr);
    return v == null || v === "" ? dflt : Number(v);
  }

  // ── 상대 시각 ─────────────────────────────────────────────────────────────
  function relText(iso) {
    if (!iso) return "";
    var t = new Date(iso);
    if (isNaN(t.getTime())) return "";
    var min = Math.floor((now().getTime() - t.getTime()) / 60000);
    if (min < 0) return "방금 갱신";      // 시계 편차로 미래가 나올 수 있다 — 음수를 노출하지 않는다
    if (min < 1) return "방금 갱신";
    if (min < 60) return min + "분 전 갱신";
    var h = Math.floor(min / 60);
    var m = min % 60;
    if (h < 24) return h + "시간" + (m ? " " + m + "분" : "") + " 전 갱신";
    return Math.floor(h / 24) + "일 전 갱신";
  }

  /** 다음 수집 "예정" 시각까지 남은 분. cadence=60이면 매시 정각이 기준이다. */
  function nextText(cadenceMin) {
    if (!cadenceMin) return "";
    var n = now();
    var mins = n.getMinutes() + n.getSeconds() / 60;
    var left = Math.ceil(cadenceMin - (mins % cadenceMin));
    if (left <= 0) left = cadenceMin;
    // "예정"을 뺀 단정형은 쓰지 않는다 — CI 지연을 우리가 보장할 수 없다.
    return "다음 수집 예정 ~" + left + "분 후";
  }

  function tickLabels(root) {
    var scope = root || doc;
    Array.prototype.forEach.call(scope.querySelectorAll("[data-live-since]"), function (el) {
      el.textContent = relText(el.getAttribute("data-live-since"));
    });
    Array.prototype.forEach.call(scope.querySelectorAll("[data-live-next]"), function (el) {
      var feed = el.closest ? el.closest("[data-live-cadence-min]") : null;
      el.textContent = nextText(feed ? num(feed, "data-live-cadence-min", 0) : 0);
    });
  }

  // ── 라이브 상태 판정 ──────────────────────────────────────────────────────
  /** 데이터 as_of가 FRESH이고, 실제로 폴링이 살아 있을 때만 "on". 그 외는 전부 "off". */
  function setLiveState(feed, asOfIso) {
    var live = false;
    if (feed.polling && asOfIso && global.TAFreshness) {
      var r = global.TAFreshness.judge(asOfIso, feed.freshMaxMin, feed.staleMinMin);
      live = r.state === "fresh";
    }
    feed.root.setAttribute("data-live", live ? "on" : "off");
    return live;
  }

  // ── 값 변경 플래시 ────────────────────────────────────────────────────────
  /** 값이 **실제로 바뀌었을 때만** 짧게 번쩍인다. 폴링할 때마다 번쩍이면 그건 장식이다. */
  function flash(el, dir) {
    if (!el || prefersReducedMotion()) return;
    var cls = dir > 0 ? "v2-flash--up" : dir < 0 ? "v2-flash--down" : "v2-flash--flat";
    el.classList.remove("v2-flash--up", "v2-flash--down", "v2-flash--flat");
    // 리플로우를 강제해야 같은 클래스를 다시 붙일 때 애니메이션이 재생된다.
    void el.offsetWidth;
    el.classList.add(cls);
    global.setTimeout(function () { el.classList.remove(cls); }, 1200);
  }

  function prefersReducedMotion() {
    if (doc.documentElement.getAttribute("data-reduce-motion") === "1") return true;
    return !!(global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  // ── 폴링 ──────────────────────────────────────────────────────────────────
  function fetchOnce(feed) {
    // no-cache = 매번 서버에 재검증(ETag). 변경이 없으면 304로 끝나 낭비가 없다.
    // 그냥 fetch하면 GitHub Pages의 Cache-Control 때문에 몇 분간 옛 파일을 돌려받는다.
    return global.fetch(feed.url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function poll(feed) {
    if (doc.visibilityState === "hidden") return;   // 안 보는 화면을 갱신하려 두드리지 않는다
    fetchOnce(feed).then(function (data) {
      feed.fails = 0;
      feed.polling = true;
      var applier = appliers[feed.kind];
      var asOf = applier && applier.asOf ? applier.asOf(data) : null;
      // 내용이 그대로면 DOM을 건드리지 않는다 — 매분 통째로 다시 그리면 호버가 끊긴다.
      var stamp = JSON.stringify(data).length + "|" + (asOf || "");
      if (stamp !== feed.stamp) {
        feed.stamp = stamp;
        if (applier) applier.apply(data, feed.root, { flash: flash, first: feed.firstDone !== true });
        feed.firstDone = true;
      }
      if (asOf) {
        Array.prototype.forEach.call(feed.root.querySelectorAll("[data-live-since]"), function (el) {
          el.setAttribute("data-live-since", asOf);
        });
      }
      feed.asOf = asOf;
      setLiveState(feed, asOf || feed.asOf);
      tickLabels(feed.root);
    }).catch(function () {
      feed.fails += 1;
      if (feed.fails >= MAX_FAILS) {
        feed.polling = false;
        stop(feed);
      }
      // 못 받아오는 동안 라이브 표시를 유지하면 그것도 거짓말이다.
      setLiveState(feed, feed.asOf);
    });
  }

  function start(feed) {
    if (feed.timer) return;
    feed.timer = global.setInterval(function () { poll(feed); }, feed.intervalMs);
    poll(feed);
  }

  function stop(feed) {
    if (!feed.timer) return;
    global.clearInterval(feed.timer);
    feed.timer = null;
  }

  // ── 등록 ──────────────────────────────────────────────────────────────────
  /** 페이지별 적용기 등록. {apply(data, root, ctx), asOf(data)} */
  function registerApplier(kind, applier) {
    appliers[kind] = applier;
  }

  function initFeeds(root) {
    var scope = root || doc;
    Array.prototype.forEach.call(scope.querySelectorAll("[data-live-src]"), function (el) {
      if (el.__liveFeed) return;
      var feed = {
        root: el,
        url: el.getAttribute("data-live-src"),
        kind: el.getAttribute("data-live-kind") || "",
        intervalMs: Math.max(MIN_INTERVAL_MS, num(el, "data-live-interval", 60) * 1000),
        freshMaxMin: el.getAttribute("data-fresh-max-min"),
        staleMinMin: el.getAttribute("data-stale-min-min"),
        fails: 0, polling: false, timer: null, stamp: null, asOf: null
      };
      el.__liveFeed = feed;
      feeds.push(feed);
      // 첫 판정은 발행 시점 as_of로 — 폴링 결과를 기다리는 동안 상태를 비워 두지 않는다.
      var since = el.querySelector("[data-live-since]");
      feed.asOf = since ? since.getAttribute("data-live-since") : null;
      feed.polling = true;
      setLiveState(feed, feed.asOf);
      start(feed);
    });
    tickLabels(scope);
  }

  function init(root) {
    initFeeds(root);
    if (!global.__taLiveTicker) {
      global.__taLiveTicker = global.setInterval(function () { tickLabels(doc); }, TICK_MS);
      doc.addEventListener("visibilitychange", function () {
        // 탭으로 돌아오면 즉시 한 번 받아온다 — 돌아왔는데 옛 값이 남아 있는 게 최악이다.
        if (doc.visibilityState !== "visible") return;
        tickLabels(doc);
        feeds.forEach(function (f) { if (f.timer) poll(f); });
      });
    }
  }

  global.TALive = {
    init: init,
    registerApplier: registerApplier,
    flash: flash,
    relText: relText,
    now: now
  };

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", function () { init(doc); });
  } else {
    init(doc);
  }
})(window);
