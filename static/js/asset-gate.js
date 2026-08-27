// asset-gate.js — 비밀번호 게이트 + WebCrypto 복호화(design/08 §6-3, design/20 Phase 8).
// "올바른 passphrase로 복호화 성공 = 인증"이며 서버 인증이 아니다 — 열람을 가리는 로컬
// 프라이버시 가드다(design/08 §5-1 정직한 고지, 보안 수단이라 과신하지 않는다).
// Asset·Portfolio는 이 모듈이 공유하는 sessionStorage로 게이트 세션을 공유한다(design/08 §1
// "Asset·Portfolio는 동일 게이트 세션을 공유한다") — 한쪽에서 해제하면 다른 쪽도 재인증 없이 열린다.
// 게이트 UI 동작(포커스 트랩·Esc·마스킹·유휴 잠금)도 두 페이지가 같아야 하므로 여기 모은다.
// 외부 라이브러리 0(WebCrypto SubtleCrypto 네이티브 API만 사용).
(function (global) {
  "use strict";

  var doc = global.document;
  var SESSION_KEY = "ta:assetPassphrase";
  var MASK_KEY = "ta:assetMasked";

  function siteRoot() {
    return doc.body.getAttribute("data-root") || ".";
  }

  function b64ToBytes(b64) {
    var bin = global.atob(b64);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }

  function deriveKey(passphrase, saltB64, iterations) {
    var enc = new TextEncoder();
    return global.crypto.subtle.importKey("raw", enc.encode(passphrase), "PBKDF2", false, ["deriveKey"])
      .then(function (baseKey) {
        return global.crypto.subtle.deriveKey(
          { name: "PBKDF2", salt: b64ToBytes(saltB64), iterations: iterations, hash: "SHA-256" },
          baseKey,
          { name: "AES-GCM", length: 256 },
          false,
          ["decrypt"]
        );
      });
  }

  function decryptEnvelope(envelope, passphrase) {
    return deriveKey(passphrase, envelope.salt, envelope.iterations).then(function (key) {
      return global.crypto.subtle.decrypt(
        { name: "AES-GCM", iv: b64ToBytes(envelope.iv) },
        key,
        b64ToBytes(envelope.ciphertext)
      );
    }).then(function (buf) {
      return JSON.parse(new TextDecoder().decode(buf));
    });
  }

  function fetchEnvelope() {
    // cache:"no-cache" = 매번 서버에 재검증(ETag). GitHub Pages가 이 파일에
    // Cache-Control: max-age=600을 붙이므로, 그냥 fetch하면 데스크톱이 방금 발행한 잔고를
    // 두고도 브라우저가 최대 10분간 옛 암호문을 돌려준다 — 그 결과 화면의 금액·환율이
    // 갱신되지 않고 신선도 배지만 "지연"으로 뜬다(실제 사고 2026-08-03).
    // no-store가 아니라 no-cache인 이유: 변경이 없으면 304로 끝나 낭비가 없다.
    return global.fetch(siteRoot() + "/data/asset/assets.enc.json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("envelope fetch failed");
      return r.json();
    });
  }

  function unlock(passphrase) {
    return fetchEnvelope().then(function (envelope) {
      return decryptEnvelope(envelope, passphrase);
    }).then(function (data) {
      try { global.sessionStorage.setItem(SESSION_KEY, passphrase); } catch (e) { /* 프라이빗 모드 등 — 무시 */ }
      return data;
    });
  }

  function cachedPassphrase() {
    try { return global.sessionStorage.getItem(SESSION_KEY); } catch (e) { return null; }
  }

  function tryAutoUnlock() {
    var pass = cachedPassphrase();
    if (!pass) return global.Promise.resolve(null);
    // 캐시된 passphrase가 더 이상 맞지 않으면(재암호화 등) 조용히 실패 처리 — 게이트로 되돌아간다.
    return unlock(pass).catch(function () { return null; });
  }

  function lock() {
    try { global.sessionStorage.removeItem(SESSION_KEY); } catch (e) { /* noop */ }
  }

  // ── 마스킹 상태 ──
  // 세션에 명시 선택이 없으면 Settings의 "금액 가리기 기본값"(localStorage, TAStore)을 따른다.
  // 이 폴백이 없던 동안 Settings 스위치는 아무 효과가 없었다 — 켜져 있다고 안내하면서
  // 실제로는 동작하지 않는 스위치를 두지 않는다.
  function masked() {
    var v = null;
    try { v = global.sessionStorage.getItem(MASK_KEY); } catch (e) { /* noop */ }
    if (v === "1") return true;
    if (v === "0") return false;
    return !!(global.TAStore && global.TAStore.maskDefault && global.TAStore.maskDefault());
  }

  function setMasked(on) {
    try { global.sessionStorage.setItem(MASK_KEY, on ? "1" : "0"); } catch (e) { /* noop */ }
  }

  // ── 사이드바 자물쇠(design/08 §1: 인증 후 열린 자물쇠로 교체) ──
  function paintNavLocks(unlocked) {
    var locks = doc.querySelectorAll(".v2-nav__lock");
    for (var i = 0; i < locks.length; i++) {
      locks[i].textContent = unlocked ? "🔓" : "🔒";
      locks[i].setAttribute("title", unlocked ? "잠금 해제됨 · 이 세션 동안 유지" : "비밀번호 잠금");
    }
  }

  // ── 게이트 모달 UI 배선(포커스 트랩·Esc·자동 포커스, design/08 §2-1) ──
  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function bindModal(overlay, input, onEscape) {
    function focusables() {
      return Array.prototype.filter.call(overlay.querySelectorAll(FOCUSABLE), function (el) {
        return el.offsetParent !== null;
      });
    }
    overlay.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { if (onEscape) onEscape(); return; }
      if (e.key !== "Tab") return;
      var items = focusables();
      if (!items.length) return;
      var first = items[0], last = items[items.length - 1];
      if (e.shiftKey && doc.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && doc.activeElement === last) { e.preventDefault(); first.focus(); }
    });
    if (input && !overlay.hidden) input.focus();
  }

  // ── 유휴 자동 잠금(Settings "유휴 자동 잠금", design/08 §7-2) ──
  function startIdleLock(onLock) {
    var minutes = (global.TAStore && global.TAStore.idleLockMinutes) ? global.TAStore.idleLockMinutes() : 0;
    if (!minutes || minutes <= 0) return function () {};
    var timer = null;
    function reset() {
      if (timer) global.clearTimeout(timer);
      timer = global.setTimeout(onLock, minutes * 60 * 1000);
    }
    var events = ["mousemove", "keydown", "click", "scroll", "touchstart"];
    events.forEach(function (evt) {
      doc.addEventListener(evt, reset, { passive: true });
    });
    reset();
    return function () {
      if (timer) global.clearTimeout(timer);
      events.forEach(function (evt) { doc.removeEventListener(evt, reset, { passive: true }); });
    };
  }

  global.TAAssetGate = {
    unlock: unlock,
    tryAutoUnlock: tryAutoUnlock,
    lock: lock,
    fetchEnvelope: fetchEnvelope,
    masked: masked,
    setMasked: setMasked,
    paintNavLocks: paintNavLocks,
    bindModal: bindModal,
    startIdleLock: startIdleLock,
  };
})(window);
