"""JSON 로드/저장(원자적 쓰기)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any, compact: bool = False) -> None:
    """compact=True는 사람이 읽지 않는 대용량 파일 전용(design/28 §3-4).

    히스토리 원장(300행×2시장×매일)과 스크리너 발행물(3,300행)은 indent=2로 저장하면 용량이
    2~3배가 된다. 기본값은 종전과 같으므로 기존 호출부는 전부 무변경이다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if compact:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"), default=str)
            else:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
