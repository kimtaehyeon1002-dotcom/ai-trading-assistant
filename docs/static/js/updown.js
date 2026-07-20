// updown.js — 등락색 모드 전환 API (design/22 §5-3, design/20 Phase 4 최초 구현).
// 저장된 모드는 base_v2.html의 인라인 부트 스니펫이 이미 [data-updown]에 반영한다(FOUC 방지).
// 이 모듈은 그 값을 재확인하고, 토글 UI(Settings, Phase 9)가 호출할 공개 API를 제공한다.
(function (global) {
  "use strict";

  function apply(mode) {
    document.documentElement.setAttribute("data-updown", mode);
  }

  function setMode(mode) {
    if (mode !== "kr" && mode !== "global") return;
    if (global.TAStore) global.TAStore.setUpdownMode(mode);
    apply(mode);
  }

  function getMode() {
    return document.documentElement.getAttribute("data-updown") || "kr";
  }

  global.TAUpdown = { setMode: setMode, getMode: getMode, apply: apply };
})(window);
