"""Provider 공통 에러 — 소스별 차단/장애를 통일해 폴백(무료↔유료)을 가능하게 한다."""
from __future__ import annotations


class ProviderError(Exception):
    """모든 provider 에러의 베이스."""


class RateLimitError(ProviderError):
    """소스 레이트리밋/429 → 다음 우선순위 provider로 폴백."""


class SourceUnavailable(ProviderError):
    """소스 장애/미지원/데이터 없음 → 다음 provider로 폴백, 전부 실패 시 503."""
