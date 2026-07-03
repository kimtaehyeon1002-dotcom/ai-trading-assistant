"""뉴스 RSS 소스. 저작권 안전: 제목+요약+링크만 사용, 본문 미저장. 키워드는 config/keywords.py."""
from __future__ import annotations

SOURCES: list[dict] = [
    {"url": "https://www.hankyung.com/feed/finance", "source": "한국경제", "region": "KR", "lang": "ko"},
    {"url": "https://www.mk.co.kr/rss/30100041/", "source": "매일경제·증권", "region": "KR", "lang": "ko"},
    {"url": "https://www.yna.co.kr/rss/economy.xml", "source": "연합뉴스·경제", "region": "KR", "lang": "ko"},
    {"url": "https://news.google.com/rss/search?q=%EC%A6%9D%EC%8B%9C&hl=ko&gl=KR&ceid=KR:ko", "source": "Google News", "region": "KR", "lang": "ko"},
    {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "source": "WSJ Markets", "region": "US", "lang": "en"},
    {"url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "source": "MarketWatch", "region": "US", "lang": "en"},
    {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "source": "CNBC Finance", "region": "US", "lang": "en"},
]
