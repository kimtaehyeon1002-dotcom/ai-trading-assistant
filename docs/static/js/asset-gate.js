// asset-gate.js — 비밀번호 게이트 + WebCrypto 복호화(design/08 §6-3, design/20 Phase 8).
// "올바른 passphrase로 복호화 성공 = 인증"이며 서버 인증이 아니다 — 열람을 가리는 로컬
// 프라이버시 가드다(design/08 §5-1 정직한 고지, 보안 수단이라 과신하지 않는다).
// Asset·Portfolio는 이 모듈이 공유하는 sessionStorage로 게이트 세션을 공유한다(design/08 §1
// "Asset·Portfolio는 동일 게이트 세션을 공유한다") — 한쪽에서 해제하면 다른 쪽도 재인증 없이 열린다.
// 외부 라이브러리 0(WebCrypto SubtleCrypto 네이티브 API만 사용).
(function (global) {
  "use strict";

  var doc = global.document;
  var SESSION_KEY = "ta:assetPassphrase";

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
    return global.fetch(siteRoot() + "/data/asset/assets.enc.json").then(function (r) {
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

  global.TAAssetGate = { unlock: unlock, tryAutoUnlock: tryAutoUnlock, lock: lock, fetchEnvelope: fetchEnvelope };
})(window);
