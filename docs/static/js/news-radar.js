// news-radar.js — 키워드 레이더 클릭 → 리스트 필터(design/03 §3-5).
// tabs.js와 같은 방식: 전 행을 빌드 타임에 렌더해 두고 display만 토글한다(외부 라이브러리 0).
//
// 마크업 계약:
//   <button data-kw-pick="반도체">          ← 레이더 행(키워드 선택)
//   <div class="v2-news-list-row" data-kw="반도체|AI|실적">   ← 기사 행(빌드 타임 부여)
//   <button data-kw-clear><span data-kw-label></span></button> ← 해제 칩
//   <p data-kw-empty>                       ← 필터 결과 0건 안내
//
// 필터 상태는 URL 해시(#kw=반도체)로 유지한다 — 탭(#tab=)과 같은 해시에 공존하므로
// 한쪽을 쓸 때 다른 쪽을 지우지 않도록 파라미터 단위로 읽고 쓴다.
(function (global) {
  "use strict";

  var doc = global.document;

  function readHash() {
    var out = {};
    (global.location.hash || "").replace(/^#/, "").split("&").forEach(function (pair) {
      if (!pair) return;
      var i = pair.indexOf("=");
      if (i > 0) out[pair.slice(0, i)] = decodeURIComponent(pair.slice(i + 1));
    });
    return out;
  }

  function writeHash(params) {
    var parts = Object.keys(params)
      .filter(function (k) { return params[k]; })
      .map(function (k) { return k + "=" + encodeURIComponent(params[k]); });
    global.history.replaceState(null, "", parts.length ? "#" + parts.join("&") : " ");
  }

  function rows() {
    return doc.querySelectorAll(".v2-news-list-row[data-kw]");
  }

  // 필터는 '표시 중인 탭 안에서' 적용된다. 탭 패널 자체의 display는 tabs.js 소관이므로
  // 여기서는 행만 건드리고, 빈 상태는 활성 패널 기준으로 판정한다.
  function activePanelHasVisibleRow() {
    var panels = doc.querySelectorAll('[data-tab-panel="news"]');
    for (var i = 0; i < panels.length; i++) {
      if (panels[i].style.display === "none") continue;
      var visible = panels[i].querySelectorAll(".v2-news-list-row:not([hidden])");
      if (visible.length) return true;
    }
    return false;
  }

  function apply(keyword) {
    rows().forEach(function (row) {
      var labels = (row.getAttribute("data-kw") || "").split("|");
      var match = !keyword || labels.indexOf(keyword) !== -1;
      if (match) row.removeAttribute("hidden");
      else row.setAttribute("hidden", "");
    });

    doc.querySelectorAll("[data-kw-pick]").forEach(function (btn) {
      if (btn.getAttribute("data-kw-pick") === keyword) btn.setAttribute("aria-pressed", "true");
      else btn.removeAttribute("aria-pressed");
    });

    var chip = doc.querySelector("[data-kw-clear]");
    if (chip) {
      var label = chip.querySelector("[data-kw-label]");
      if (label) label.textContent = keyword || "";
      if (keyword) chip.removeAttribute("hidden");
      else chip.setAttribute("hidden", "");
    }

    var empty = doc.querySelector("[data-kw-empty]");
    if (empty) {
      if (keyword && !activePanelHasVisibleRow()) empty.removeAttribute("hidden");
      else empty.setAttribute("hidden", "");
    }
  }

  // 레이더는 4탭 전체를 합산하므로, 지금 보는 탭에 그 키워드 기사가 한 건도 없을 수 있다
  // (실측: "환율" 6건이 전부 거시경제 탭 — 미국시장 탭에서 누르면 빈 화면만 나온다).
  // 그럴 때 매칭이 가장 많은 탭으로 옮겨 줘야 클릭이 헛돌지 않는다.
  function bestTabFor(keyword) {
    var best = null;
    var bestCount = 0;
    doc.querySelectorAll('[data-tab-panel="news"]').forEach(function (panel) {
      var n = 0;
      panel.querySelectorAll(".v2-news-list-row[data-kw]").forEach(function (row) {
        if ((row.getAttribute("data-kw") || "").split("|").indexOf(keyword) !== -1) n++;
      });
      if (n > bestCount) {
        bestCount = n;
        best = panel.getAttribute("data-tab");
      }
    });
    return best;
  }

  function select(keyword) {
    var params = readHash();
    params.kw = keyword || "";
    apply(keyword);

    if (keyword && !activePanelHasVisibleRow()) {
      var tab = bestTabFor(keyword);
      if (tab && global.TATabs) {
        global.TATabs.activate("news", tab);
        params.tab = tab;
        apply(keyword);  // 탭이 바뀌었으니 빈 상태 판정을 다시 한다
      }
    }
    writeHash(params);
  }

  function init() {
    if (!doc.querySelector("[data-kw-pick]")) return;

    doc.addEventListener("click", function (e) {
      var pick = e.target.closest("[data-kw-pick]");
      if (pick) {
        var key = pick.getAttribute("data-kw-pick");
        // 같은 키워드를 다시 누르면 해제 — 별도 버튼을 찾지 않아도 원상복귀된다
        select(readHash().kw === key ? "" : key);
        return;
      }
      if (e.target.closest("[data-kw-clear]")) select("");
    });

    // 탭을 바꾸면 활성 패널이 달라지므로 빈 상태 판정을 다시 한다(행 표시 자체는 유지).
    global.addEventListener("hashchange", function () { apply(readHash().kw || ""); });

    apply(readHash().kw || "");
  }

  global.TANewsRadar = { init: init, apply: apply };
})(window);
