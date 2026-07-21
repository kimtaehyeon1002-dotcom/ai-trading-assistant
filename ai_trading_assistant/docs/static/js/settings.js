// settings.js — Settings 6섹션 즉시 적용(design/10, design/20 Phase 9). 저장 버튼 없음.
// ①표시(등락모드·모션줄이기)는 이미 존재하는 전역 API(updown.js·store.js)를 그대로 호출해
// 실제 전 페이지 효과를 낸다. 외부 라이브러리 0.
(function (global) {
  "use strict";

  var doc = global.document;

  function flashSaved(el) {
    if (!el) return;
    el.hidden = false;
    global.setTimeout(function () { el.hidden = true; }, 2000);
  }

  // ── ① 표시: 등락 모드 ──
  function initUpdownRadio() {
    var buttons = doc.querySelectorAll("[data-updown-radio] .v2-radio-preview");
    if (!buttons.length || !global.TAUpdown) return;

    function paint() {
      var current = global.TAUpdown.getMode();
      buttons.forEach(function (b) {
        var selected = b.getAttribute("data-mode") === current;
        b.classList.toggle("v2-radio-preview--selected", selected);
        var checkSlot = b.querySelector(current === "kr" ? "[data-check-kr]" : "[data-check-global]");
        b.querySelectorAll("[data-check-kr],[data-check-global]").forEach(function (s) { s.textContent = ""; });
        if (selected && checkSlot) checkSlot.textContent = " ✓";
      });
    }

    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        global.TAUpdown.setMode(b.getAttribute("data-mode"));
        paint();
        flashSaved(doc.getElementById("updown-saved"));
      });
    });
    paint();
  }

  // ── ① 표시: 금액 가리기 기본값 ──
  function initMaskDefaultToggle() {
    var toggle = doc.getElementById("mask-default-toggle");
    if (!toggle || !global.TAStore) return;
    function paint() { toggle.setAttribute("aria-checked", global.TAStore.maskDefault() ? "true" : "false"); }
    toggle.addEventListener("click", function () {
      global.TAStore.setMaskDefault(!global.TAStore.maskDefault());
      paint();
    });
    paint();
  }

  // ── ① 표시: 모션 줄이기 ──
  function initReduceMotionSegmented() {
    var seg = doc.querySelector("[data-reduce-motion-segmented]");
    if (!seg || !global.TAStore) return;
    var opts = seg.querySelectorAll("[data-value]");
    function paint() {
      var on = global.TAStore.reduceMotion();
      opts.forEach(function (o) { o.setAttribute("aria-pressed", o.getAttribute("data-value") === (on ? "1" : "0") ? "true" : "false"); });
      doc.documentElement.toggleAttribute("data-reduce-motion", on);
      if (!on) doc.documentElement.removeAttribute("data-reduce-motion");
      else doc.documentElement.setAttribute("data-reduce-motion", "1");
    }
    opts.forEach(function (o) {
      o.addEventListener("click", function () {
        global.TAStore.setReduceMotion(o.getAttribute("data-value") === "1");
        paint();
      });
    });
    paint();
  }

  // ── (준비 중) 시계 표기 세그먼트 — 저장만, 소비처 미구현 ──
  function initGenericSegmented(selector, storeKey, defaultValue) {
    var seg = doc.querySelector(selector);
    if (!seg) return;
    var opts = seg.querySelectorAll("[data-value]");
    function current() {
      try { return global.localStorage.getItem("ta:" + storeKey) || defaultValue; } catch (e) { return defaultValue; }
    }
    function paint() {
      var v = current();
      opts.forEach(function (o) { o.setAttribute("aria-pressed", o.getAttribute("data-value") === v ? "true" : "false"); });
    }
    opts.forEach(function (o) {
      o.addEventListener("click", function () {
        try { global.localStorage.setItem("ta:" + storeKey, o.getAttribute("data-value")); } catch (e) { /* noop */ }
        paint();
      });
    });
    paint();
  }

  // ── ③ 보안 ──
  function initSecurity() {
    var caption = doc.getElementById("gate-status-caption");
    var lockBtn = doc.getElementById("lock-now-btn");
    if (caption && global.TAAssetGate) {
      try {
        caption.textContent = global.sessionStorage.getItem("ta:assetPassphrase") ? "잠금 해제됨(이 세션 동안)" : "잠김";
      } catch (e) { caption.textContent = "확인 불가"; }
    }
    if (lockBtn && global.TAAssetGate) {
      lockBtn.addEventListener("click", function () {
        global.TAAssetGate.lock();
        if (caption) caption.textContent = "잠김";
        flashSaved(lockBtn.parentElement.querySelector(".v2-setting-saved"));
      });
    }
    initGenericSegmented("[data-idle-lock-segmented]", "idleLockMinutes", "30");
  }

  // ── ④ 데이터 갱신 안내 ──
  function siteRoot() { return doc.body.getAttribute("data-root") || "."; }

  function renderFreshness(data) {
    var sources = data.sources || {};
    var names = Object.keys(sources);
    var anyWarn = names.some(function (n) { return sources[n].status !== "completed"; });
    var summary = doc.getElementById("freshness-summary");
    if (summary) {
      summary.textContent = anyWarn ? "일부 소스 확인 필요" : "전체 소스 정상 · 데이터 생성 " + (data.generated_at || "");
      summary.className = anyWarn ? "v2-accordion-status--warn" : "v2-accordion-status--ok";
    }
    var tbody = doc.getElementById("freshness-tbody");
    if (tbody) {
      tbody.innerHTML = names.map(function (n) {
        var s = sources[n];
        return "<tr><td>" + n + "</td><td>" + s.status + '</td><td class="num">' + (s.items != null ? s.items : "—")
          + '</td><td class="num">' + (s.last_built ? s.last_built.slice(0, 16).replace("T", " ") : "—") + "</td></tr>";
      }).join("");
    }
  }

  function initFreshnessAccordion() {
    var accordion = doc.getElementById("freshness-accordion");
    var header = accordion && accordion.querySelector("[data-accordion-toggle]");
    if (!accordion || !header) return;

    var SESSION_KEY = "ta:settingsDataOpen";
    function setOpen(open) {
      accordion.classList.toggle("v2-accordion--open", open);
      try { global.sessionStorage.setItem(SESSION_KEY, open ? "1" : "0"); } catch (e) { /* noop */ }
    }
    header.addEventListener("click", function () {
      setOpen(!accordion.classList.contains("v2-accordion--open"));
    });
    var deepLink = global.location.hash === "#data";
    var wasOpen = false;
    try { wasOpen = global.sessionStorage.getItem(SESSION_KEY) === "1"; } catch (e) { /* noop */ }
    setOpen(deepLink || wasOpen);

    global.fetch(siteRoot() + "/data/meta/freshness.json").then(function (r) {
      return r.ok ? r.json() : null;
    }).then(function (data) {
      if (data) renderFreshness(data);
    }).catch(function () {
      var summary = doc.getElementById("freshness-summary");
      if (summary) summary.textContent = "불러오지 못했습니다";
    });
  }

  // ── ⑤ 관심 테마 ──
  function initThemes() {
    var chipsEl = doc.getElementById("themes-chips");
    var countEl = doc.getElementById("themes-count");
    var form = doc.getElementById("theme-add-form");
    var input = doc.getElementById("theme-input");
    if (!chipsEl || !global.TAStore) return;

    function paint() {
      var themes = global.TAStore.themes();
      countEl.textContent = themes.length + "개 등록됨";
      chipsEl.innerHTML = themes.map(function (t, i) {
        return '<button type="button" class="v2-theme-chip" data-idx="' + i + '">' + t + ' <span class="v2-theme-chip__remove">×</span></button>';
      }).join("");
    }
    chipsEl.addEventListener("click", function (e) {
      var chip = e.target.closest("[data-idx]");
      if (!chip) return;
      var themes = global.TAStore.themes();
      themes.splice(parseInt(chip.getAttribute("data-idx"), 10), 1);
      global.TAStore.setThemes(themes);
      paint();
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = input.value.trim();
      if (!v) return;
      var themes = global.TAStore.themes();
      if (themes.indexOf(v) === -1) themes.push(v);
      global.TAStore.setThemes(themes);
      input.value = "";
      paint();
    });
    paint();
  }

  // ── ⑥ 초기화 ──
  function initReset() {
    var btn = doc.getElementById("reset-btn");
    if (!btn || !global.TAStore) return;
    btn.addEventListener("click", function () {
      global.TAStore.resetAll();
      global.location.reload();
    });
  }

  // ── 앵커 내비 스크롤 스파이(간단 버전: 클릭 시 활성 표시) ──
  function initAnchorNav() {
    var items = doc.querySelectorAll(".v2-settings-nav__item");
    items.forEach(function (a) {
      a.addEventListener("click", function () {
        items.forEach(function (i) { i.classList.remove("v2-settings-nav__item--active"); });
        a.classList.add("v2-settings-nav__item--active");
      });
    });
  }

  function init() {
    initUpdownRadio();
    initMaskDefaultToggle();
    initReduceMotionSegmented();
    initGenericSegmented("[data-clock-format-segmented]", "clockFormat", "24");
    initSecurity();
    initFreshnessAccordion();
    initThemes();
    initReset();
    initAnchorNav();
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
