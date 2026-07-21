// freshness.js — 신선도/세션 단일 모듈 (design/22 §5-2, design/21 §6).
// 입력: 카드 루트 요소의 [data-asof](UTC ISO) · [data-fresh-max-min] · [data-stale-min-min] ·
//       [data-session](분/키 값은 파이썬 측이 design/21 §6-2 실측표를 기준으로 미리 계산해 넣는다 —
//       이 모듈은 문턱 공식을 스스로 유도하지 않는다, design/21 §6-1 "행별 명시값을 입력받는다").
// 출력: 요소에 data-freshness="fresh|delayed|stale" 부여 — CSS(components.css)가 그 값을 소비한다.
// 테스트 훅: ?now=<ISO> 쿼리 파라미터가 있으면 그 값을 "지금"으로 취급한다(design/20 Phase 2 DoD).
(function (global) {
  "use strict";

  function testNowOverride() {
    try {
      var params = new URLSearchParams(global.location.search);
      var v = params.get("now");
      if (!v) return null;
      var d = new Date(v);
      return isNaN(d.getTime()) ? null : d;
    } catch (e) {
      return null;
    }
  }

  var _skewMs = 0;
  var _skewCorrectable = true;

  // 1) 열람 시각 보정 — 페이지 응답의 HTTP Date 헤더와 클라이언트 시계 편차를 1회 측정한다.
  // (design/22 §5-2 흐름 1) 테스트 모드(?now=)에서는 주입값이 곧 기준이므로 건너뛴다.
  function measureClockSkew(callback) {
    if (testNowOverride()) {
      callback();
      return;
    }
    try {
      var xhr = new XMLHttpRequest();
      xhr.open("HEAD", global.location.pathname, true);
      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4) return;
        var dateHeader = xhr.getResponseHeader("Date");
        if (dateHeader) {
          var serverMs = Date.parse(dateHeader);
          if (!isNaN(serverMs)) {
            _skewMs = serverMs - Date.now();
            _skewCorrectable = true;
          }
        } else {
          _skewCorrectable = false; // Date 헤더 부재 — 보정 불가(§5-2 "기기 시계 확인" 안내 대상)
        }
        callback();
      };
      xhr.onerror = function () {
        _skewCorrectable = false;
        callback();
      };
      xhr.send();
    } catch (e) {
      _skewCorrectable = false;
      callback();
    }
  }

  function correctedNow() {
    var override = testNowOverride();
    if (override) return override;
    return new Date(Date.now() + _skewMs);
  }

  // 2~4) 신선도 판정 — 세션 우선(CLOSED-SNAPSHOT)은 실제 캘린더 연동이 필요한 kr_regular 등에서
  // Phase 4+에 추가 예정(design/20). session_key="none"(배치 데이터, 예: TA)은 age 기반 4상태만
  // 적용하며, 현재 다른 session_key 값도 캘린더 데이터가 아직 없어 동일하게 age 기반으로 폴백한다
  // — 오판정보다 정직한 생략을 택한다.
  function judge(asOfIso, freshMaxMin, staleMinMin) {
    if (!asOfIso || freshMaxMin == null || staleMinMin == null) return { state: "unknown" };
    var asOf = new Date(asOfIso);
    if (isNaN(asOf.getTime())) return { state: "unknown" };
    var now = correctedNow();
    var ageMs = now.getTime() - asOf.getTime();
    var freshMaxMs = Number(freshMaxMin) * 60000;
    var staleMinMs = Number(staleMinMin) * 60000;

    var state;
    if (ageMs <= freshMaxMs) state = "fresh";
    else if (ageMs <= staleMinMs) state = "delayed";
    else state = "stale";

    return { state: state, ageMs: ageMs, clockSkewUnknown: !_skewCorrectable };
  }

  function applyToElement(el) {
    var result = judge(
      el.getAttribute("data-asof"),
      el.getAttribute("data-fresh-max-min"),
      el.getAttribute("data-stale-min-min")
    );
    el.setAttribute("data-freshness", result.state);
    if (result.clockSkewUnknown) el.setAttribute("data-clock-skew-unknown", "1");
    return result;
  }

  function applyAll(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll("[data-asof]");
    for (var i = 0; i < nodes.length; i++) applyToElement(nodes[i]);
  }

  // 캘린더 이벤트 발표 전→후 전환(design/20 Phase 6 DoD 3) — 신선도 배지와 별개 개념이지만
  // "보정된 지금 시각"이 필요한 건 동일하므로 이 모듈의 시계 보정 결과(correctedNow)를 그대로
  // 재사용한다(클럭 스큐 로직을 두 곳에서 중복 구현하지 않는다).
  function applyEventState(el) {
    var at = el.getAttribute("data-event-at");
    if (!at) return { state: "unknown" };
    var eventTime = new Date(at);
    if (isNaN(eventTime.getTime())) return { state: "unknown" };
    var state = correctedNow().getTime() >= eventTime.getTime() ? "post" : "pre";
    el.setAttribute("data-event-state", state);
    return { state: state };
  }

  function applyAllEvents(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll("[data-event-at]");
    for (var i = 0; i < nodes.length; i++) applyEventState(nodes[i]);
  }

  function init(root) {
    measureClockSkew(function () {
      applyAll(root);
      applyAllEvents(root);
    });
  }

  global.TAFreshness = {
    init: init,
    judge: judge,
    applyToElement: applyToElement,
    applyEventState: applyEventState,
    correctedNow: correctedNow,
  };

  if (global.document) {
    if (global.document.readyState !== "loading") init();
    else global.document.addEventListener("DOMContentLoaded", function () { init(); });
  }
})(window);
