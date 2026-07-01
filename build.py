"""정적 사이트 빌드 CLI — GitHub Actions/로컬에서 실행.

  python build.py morning     # 모닝리포트 + 대시보드
  python build.py news        # 뉴스 센터 + 대시보드
  python build.py trades      # 매매일지 + 대시보드
  python build.py all         # 전체
  python build.py dashboard   # 대시보드만
"""
from __future__ import annotations

import argparse

from config.settings import ensure_dirs
from core.logging import get_logger
from generators.base import copy_static
from generators.dashboard.generate import generate as gen_dashboard
from generators.morning.generate import generate as gen_morning
from generators.news.generate import generate as gen_news
from generators.trades.generate import generate as gen_trades

log = get_logger("build")


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Trading Assistant 정적 사이트 빌드")
    ap.add_argument("target", choices=["morning", "news", "trades", "dashboard", "all"])
    args = ap.parse_args()

    ensure_dirs()
    if args.target in ("morning", "all"):
        gen_morning()
    if args.target in ("news", "all"):
        gen_news()
    if args.target in ("trades", "all"):
        gen_trades()
    # 대시보드는 항상 갱신(모듈 링크/지표 최신화) + 정적 자산 복사
    gen_dashboard()
    copy_static()
    log.info("빌드 완료: %s", args.target)


if __name__ == "__main__":
    main()
