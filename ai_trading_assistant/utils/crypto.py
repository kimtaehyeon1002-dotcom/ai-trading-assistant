"""자산 데이터 암호화 — PBKDF2(SHA-256) + AES-256-GCM(design/20 Phase 8 A안).

브라우저 WebCrypto(SubtleCrypto)가 PBKDF2·AES-GCM을 네이티브로 지원하므로(외부 JS 라이브러리
불필요) 빌드 시점 암호화(여기, Python)와 열람 시점 복호화(static/js/asset-gate.js, WebCrypto)가
동일한 원시 알고리즘·파라미터로 왕복한다. 평문 원장(로컬 전용, data/snapshots/)은 반드시 이
모듈을 거쳐야만 공개 채널(docs/data/asset/assets.enc.json)에 실린다 — 평문 그대로 발행 금지.
"""
from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# OWASP 2023 PBKDF2-HMAC-SHA256 권장 하한. WebCrypto deriveKey에도 동일 값을 넘겨야 한다
# (static/js/asset-gate.js와 파라미터가 어긋나면 절대 복호화되지 않는다 — 이 상수가 유일 진실원).
PBKDF2_ITERATIONS = 210_000
_SALT_LEN = 16
_IV_LEN = 12
_KEY_LEN_BITS = 256


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=_KEY_LEN_BITS // 8, salt=salt, iterations=iterations)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(payload: dict, passphrase: str) -> dict:
    """평문 dict → {"salt","iv","iterations","ciphertext"}(전부 base64/int). 호출마다 salt·iv 재생성."""
    import os

    salt = os.urandom(_SALT_LEN)
    iv = os.urandom(_IV_LEN)
    key = _derive_key(passphrase, salt, PBKDF2_ITERATIONS)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(iv, plaintext, None)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "iterations": PBKDF2_ITERATIONS,
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt(envelope: dict, passphrase: str) -> dict:
    """왕복 검증·테스트 전용(브라우저는 WebCrypto로 동일 로직을 독립 수행한다). 실패 시 예외 발생."""
    salt = base64.b64decode(envelope["salt"])
    iv = base64.b64decode(envelope["iv"])
    key = _derive_key(passphrase, salt, envelope["iterations"])
    ciphertext = base64.b64decode(envelope["ciphertext"])
    plaintext = AESGCM(key).decrypt(iv, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))
