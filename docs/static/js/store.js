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
  };
})(window);
