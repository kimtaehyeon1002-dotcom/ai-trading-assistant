// store.js — local/sessionStorage 단일 접근점 (design/22 §5-7)
// localStorage: 등락모드·테마·마스킹 기본값·관심테마·모션줄이기(기기 귀속·저민감).
// sessionStorage: 게이트 세션·마스킹 현재상태·아코디언 등(Phase 8+에서 사용 시작).
// 키는 "ta:" 네임스페이스로 통일 — base_v2.html의 인라인 부트 스니펫과 동일 규약을 공유한다.
(function (global) {
  "use strict";

  var NS = "ta:";

  function safeGet(storage, key, fallback) {
    try {
      var v = storage.getItem(NS + key);
      return v === null ? fallback : v;
    } catch (e) {
      return fallback;
    }
  }

  function safeSet(storage, key, value) {
    try {
      storage.setItem(NS + key, value);
    } catch (e) {
      // 프라이빗 모드 등 저장 불가 환경 — 조용히 무시(기능 저하만, 오류 없음)
    }
  }

  function safeRemove(storage, key) {
    try {
      storage.removeItem(NS + key);
    } catch (e) {
      /* noop */
    }
  }

  function scope(storage) {
    return {
      get: function (key, fallback) { return safeGet(storage, key, fallback); },
      set: function (key, value) { safeSet(storage, key, value); },
      remove: function (key) { safeRemove(storage, key); },
    };
  }

  var local = scope(global.localStorage);
  var session = scope(global.sessionStorage);

  global.TAStore = {
    local: local,
    session: session,
    theme: function () { return local.get("theme", "dark"); },
    setTheme: function (v) { local.set("theme", v); },
    updownMode: function () { return local.get("updownMode", "kr"); },
    setUpdownMode: function (v) { local.set("updownMode", v); },
    reduceMotion: function () { return local.get("reduceMotion", "0") === "1"; },
    setReduceMotion: function (v) { local.set("reduceMotion", v ? "1" : "0"); },
    maskDefault: function () { return local.get("maskDefault", "0") === "1"; },
    setMaskDefault: function (v) { local.set("maskDefault", v ? "1" : "0"); },
    themes: function () {
      try { return JSON.parse(local.get("themes", "[]")); } catch (e) { return []; }
    },
    setThemes: function (arr) { local.set("themes", JSON.stringify(arr || [])); },
    idleLockMinutes: function () { return parseInt(local.get("idleLockMinutes", "30"), 10); },
    setIdleLockMinutes: function (v) { local.set("idleLockMinutes", String(v)); },
    resetAll: function () {
      // 비밀번호(passphrase는 애초에 저장하지 않음, sessionStorage뿐)와 매매일지(서버 데이터)는
      // 애초에 이 스토어가 다루지 않으므로 "유지"가 자동으로 성립한다(design/10 §2-2 ⑥).
      ["theme", "updownMode", "reduceMotion", "maskDefault", "themes", "idleLockMinutes"].forEach(local.remove);
    },
  };
})(window);
