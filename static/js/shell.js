// shell.js — 셸 인터랙션(모바일 서랍) + 등장 모션. 외부 의존 0.
//
// design/00 §5-2 반응형 개편과 §10 모션 규칙을 함께 구현한다. 세 가지 일을 한다:
//   1) 1024px 미만에서 사이드바 서랍 열기/닫기(포커스 가둠·Esc·스크롤 잠금 포함)
//   2) 카드 등장 스태거 — 한 번만, 240ms. 스크롤 연동이 아니라 첫 렌더 1회다.
//   3) 핵심 수치 카운트업 — 화면 최상위 숫자 1개에만. 나머지는 정적이다.
//
// 왜 스크롤 연동을 안 쓰는가: 스크롤할 때마다 요소가 나타나는 화면은 처음엔 화려하지만
// 매일 보는 도구에서는 값을 읽으려 할 때마다 기다리게 만든다. 등장은 첫 진입 1회로 끝낸다.
(function (global) {
  "use strict";

  var doc = global.document;
  var MOBILE_MAX = 1023;          // base_v2.css의 서랍 브레이크포인트와 같은 값
  var STAGGER_MS = 40;            // 카드 간 지연
  var STAGGER_CAP = 10;           // 이 개수를 넘으면 지연을 더 주지 않는다(마지막 카드가 늦게 뜨는 것 방지)
  var COUNT_MS = 520;

  function reduceMotion() {
    if (doc.documentElement.getAttribute("data-reduce-motion") === "1") return true;
    return !!(global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  function isMobile() {
    return global.innerWidth <= MOBILE_MAX;
  }

  // ── 1) 모바일 서랍 ────────────────────────────────────────────────────────
  var lastFocus = null;

  function openNav() {
    doc.body.setAttribute("data-nav", "open");
    var scrim = doc.querySelector(".v2-nav-scrim");
    if (scrim) scrim.hidden = false;
    setToggle(true);
    // 배경이 스크롤되면 서랍이 열린 채 본문만 움직여 방향 감각이 깨진다.
    doc.body.style.overflow = "hidden";
    lastFocus = doc.activeElement;
    var first = doc.querySelector(".v2-sidebar .v2-nav__item");
    if (first) first.focus();
  }

  function closeNav() {
    if (doc.body.getAttribute("data-nav") !== "open") return;
    doc.body.removeAttribute("data-nav");
    setToggle(false);
    doc.body.style.overflow = "";
    var scrim = doc.querySelector(".v2-nav-scrim");
    // 스크림은 페이드가 끝난 뒤에 숨긴다 — 즉시 hidden이면 전환이 안 보인다.
    if (scrim) {
      if (reduceMotion()) scrim.hidden = true;
      else global.setTimeout(function () {
        if (doc.body.getAttribute("data-nav") !== "open") scrim.hidden = true;
      }, 250);
    }
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    lastFocus = null;
  }

  function setToggle(open) {
    Array.prototype.forEach.call(doc.querySelectorAll("[data-nav-toggle]"), function (b) {
      b.setAttribute("aria-expanded", open ? "true" : "false");
      b.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    });
  }

  function bindNav() {
    Array.prototype.forEach.call(doc.querySelectorAll("[data-nav-toggle]"), function (b) {
      b.addEventListener("click", function () {
        if (doc.body.getAttribute("data-nav") === "open") closeNav(); else openNav();
      });
    });
    Array.prototype.forEach.call(doc.querySelectorAll("[data-nav-close]"), function (el) {
      el.addEventListener("click", closeNav);
    });
    // 메뉴를 고르면 닫는다 — 같은 페이지 앵커일 수도 있으므로 이동 여부와 무관하게 닫는다.
    var side = doc.querySelector(".v2-sidebar");
    if (side) {
      side.addEventListener("click", function (e) {
        var link = e.target.closest ? e.target.closest(".v2-nav__item") : null;
        if (link && isMobile()) closeNav();
      });
    }
    doc.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeNav();
    });
    // 서랍이 열린 채 데스크톱 폭으로 넓어지면 상태가 남아 스크롤 잠금이 풀리지 않는다.
    global.addEventListener("resize", function () {
      if (!isMobile()) closeNav();
    });
  }

  // ── 2) 카드 등장 스태거 ───────────────────────────────────────────────────
  /** 등장 연출은 CSS가 하고(components.css) 여기서는 **켤지 말지**와 순서 지연만 정한다.
   *
   *  기본값이 "보이는 상태"이고 애니메이션이 옵트인인 이유는 실측 결함 두 개 때문이다:
   *  JS 클래스 토글은 백그라운드 탭에서 rAF가 멈춰 영영 안 켜졌고, CSS fill-mode:both는
   *  애니메이션이 시작되기 전에도 투명 상태를 적용했다. 둘 다 결과가 **빈 화면**이었다.
   *  그래서 "돌 수 있다고 확인된 경우에만" 켠다. */
  function revealCards() {
    if (reduceMotion()) return;
    if (doc.visibilityState === "hidden") return;  // 숨은 탭에서는 애니메이션이 시작되지 않는다
    var cards = doc.querySelectorAll(".v2-content > .v2-card, .v2-content > .v2-rail > .v2-card");
    if (!cards.length) return;
    Array.prototype.forEach.call(cards, function (c, i) {
      c.style.setProperty("--reveal-delay", Math.min(i, STAGGER_CAP) * STAGGER_MS + "ms");
    });
    doc.documentElement.setAttribute("data-anim", "on");
  }

  // ── 3) 핵심 수치 카운트업 ─────────────────────────────────────────────────
  /** 문자열에서 숫자만 뽑아 올린다. 통화기호·콤마·단위는 그대로 두고 자리만 바꿔 끼운다. */
  function countUp(el) {
    if (reduceMotion()) return;
    if (el.closest('[data-masked="1"]')) return;   // 가려진 금액을 세어 보여주면 마스킹이 무의미하다
    var text = el.textContent;
    var m = text.match(/-?[\d,]+(\.\d+)?/);
    if (!m) return;
    var raw = m[0];
    var target = parseFloat(raw.replace(/,/g, ""));
    if (!isFinite(target) || Math.abs(target) < 10) return;  // 작은 값은 세는 맛도 없고 산만하다
    var decimals = (raw.split(".")[1] || "").length;
    var prefix = text.slice(0, m.index);
    var suffix = text.slice(m.index + raw.length);
    var start = global.performance.now();

    function frame(now) {
      var t = Math.min(1, (now - start) / COUNT_MS);
      // 감속 곡선 — 마지막에 부드럽게 멈춰야 "확정된 값"으로 읽힌다.
      var eased = 1 - Math.pow(1 - t, 3);
      var v = target * eased;
      el.textContent = prefix + v.toLocaleString("ko-KR", {
        minimumFractionDigits: decimals, maximumFractionDigits: decimals
      }) + suffix;
      if (t < 1) global.requestAnimationFrame(frame);
      else el.textContent = text;   // 마지막은 원문 그대로 — 반올림 오차가 남지 않게 한다
    }
    global.requestAnimationFrame(frame);
  }

  function animateHeroNumbers(root) {
    var scope = root || doc;
    // 화면 최상위 수치 1개에만 건다(design/00 §10-2) — 모든 숫자가 굴러가면 그건 정보가 아니라 소음이다.
    var el = scope.querySelector(".v2-stat__value--display");
    if (el && !el.__counted) { el.__counted = true; countUp(el); }
  }

  function init() {
    bindNav();
    revealCards();
    animateHeroNumbers(doc);
  }

  global.TAShell = { openNav: openNav, closeNav: closeNav, reveal: revealCards, countUp: animateHeroNumbers };

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
