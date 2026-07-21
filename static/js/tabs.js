// tabs.js — 범용 탭/필터 전환 (design/22 §5-4). 전 행을 빌드 타임에 렌더한 뒤 data-속성으로
// display만 토글한다(현행 v1 app.js 패턴 계승). 외부 라이브러리 0.
//
// 마크업 계약:
//   <div data-tabbar="news">
//     <button data-tab-btn="us_market" aria-current="page">미국시장</button> ...
//   </div>
//   <div data-tab-panel="news" data-tab="us_market">...</div>  ← data-tab === 버튼 값일 때만 표시
//
// 탭 상태는 URL 해시(#tab=us_market)로 유지한다(딥링크·뒤로가기 보존, design/22 §5-4).
(function (global) {
  "use strict";

  function activate(group, tabKey) {
    var buttons = global.document.querySelectorAll('[data-tab-btn][data-tabbar-of="' + group + '"]');
    var panels = global.document.querySelectorAll('[data-tab-panel="' + group + '"]');
    buttons.forEach(function (btn) {
      var match = btn.getAttribute("data-tab-btn") === tabKey;
      if (match) btn.setAttribute("aria-current", "page");
      else btn.removeAttribute("aria-current");
    });
    panels.forEach(function (p) {
      p.style.display = p.getAttribute("data-tab") === tabKey ? "" : "none";
    });
  }

  function hashTab() {
    var m = /(?:^|[#&])tab=([^&]+)/.exec(global.location.hash);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function init(group, defaultTab) {
    var bar = global.document.querySelector('[data-tabbar="' + group + '"]');
    if (!bar) return;
    activate(group, hashTab() || defaultTab);

    bar.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-tab-btn]");
      if (!btn) return;
      var key = btn.getAttribute("data-tab-btn");
      activate(group, key);
      global.history.replaceState(null, "", "#tab=" + encodeURIComponent(key));
    });

    // 해시만 바뀌는 네비게이션(주소창 직접 입력, 헤더 검색 딥링크 등)은 문서를 다시 로드하지
    // 않고 hashchange만 발생시킨다 — DOMContentLoaded 1회만으로는 그 갱신을 반영할 수 없다.
    global.addEventListener("hashchange", function () {
      var key = hashTab();
      if (key) activate(group, key);
    });
  }

  global.TATabs = { init: init, activate: activate };
})(window);
