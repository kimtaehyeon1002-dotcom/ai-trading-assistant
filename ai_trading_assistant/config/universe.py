"""종목 유니버스 정의(design/21 §8) — TOP30×2 ∪ 테마 종목(config/themes.py) ∪ Notion watchlist.

미국은 전종목 무료 스냅샷이 없어(design/21 §225 "미국 전시장 TOP30 무료 불가") FinanceDataReader의
'S&P500' 구성종목을 랭킹 후보 유니버스로 채택하고, 모집단 캡션("유니버스 N종목 중")으로 정직하게
축소를 고지한다(design/20 Phase 7 DoD). 실제 병합(TOP30 ∪ 테마 ∪ watchlist)은
repositories/stock_repository.build_universe()가 수행한다 — config는 선언적 데이터만 갖는다.
"""
from __future__ import annotations

US_CANDIDATE_LISTING = "S&P500"  # FinanceDataReader.StockListing() 인자
RANKING_TOP_N = 30

# Notion watchlist DB(NOTION_DB_WATCHLIST) row는 사용자가 자유롭게 명명하므로 다중 후보 키를 시도한다.
WATCHLIST_TICKER_KEYS: tuple[str, ...] = ("티커", "종목코드", "Ticker", "Symbol", "코드")
WATCHLIST_MARKET_KEYS: tuple[str, ...] = ("시장", "Market")
