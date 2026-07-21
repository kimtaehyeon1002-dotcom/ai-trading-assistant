"""YAML frontmatter 경량 파서 — 외부 의존성 없이 스칼라 key: value만 지원.

vault 노트 계약(워치리스트 등)은 중첩 리스트/맵 없는 평평한 키만 쓰므로 이걸로 충분하다.
전체 YAML 스펙을 구현하지 않는다(과설계 금지) — PyYAML을 새 의존성으로 들이지 않기 위한
의도적 축소 구현.
"""
from __future__ import annotations

_DELIM = "---"


def parse(text: str) -> tuple[dict, str]:
    """(frontmatter dict, body) 반환. frontmatter 없으면 ({}, text 그대로)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _DELIM:
        return {}, text

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            end = i
            break
    if end is None:
        return {}, text

    fm: dict = {}
    for line in lines[1:end]:
        if not line.strip() or line.strip().startswith("#") or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        fm[key.strip()] = _coerce(raw.strip())

    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return fm, body


def _coerce(raw: str):
    if raw == "":
        return ""
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw
