"""Obsidian vault(TH_DATA 별도 저장소) 저널 write-back — 봇 전용 10_Journal/ 자동 생성.

이미 계산되는 파이프라인 결과를 재사용해 vault 노트로 렌더한다(collectors는 실행당
메모이즈되므로 pipelines 재호출에 추가 API 비용이 없다 — generators/pipelines.py 참고).
20_Memory/ 종목·테마 스텁은 **파일이 없을 때만** 생성하고 기존 파일은 절대
덮어쓰지 않는다(사용자 가필 보호, TH_DATA/README.md 계약).

호출부(build.py)가 target별로 morning/news/trades 각각 호출한다 — 이 모듈 자체는 어떤
target이 실행 중인지 모른다.
"""
from __future__ import annotations

from pathlib import Path

from calculators import news_rank, themes as themes_calc
from config.keywords import CATEGORY_ORDER
from config.settings import VAULT_DIR
from generators import pipelines
from models.trade import CATEGORY_LABELS
from repositories import trade_repository
from utils.dates import today_str
from utils.logging import get_logger

log = get_logger("gen.vault_journal")

_JOURNAL = VAULT_DIR / "10_Journal"
_MEMORY_STOCKS = VAULT_DIR / "20_Memory" / "stocks"
_MEMORY_THEMES = VAULT_DIR / "20_Memory" / "themes"

_MARKET_KEYS = ("kospi_night", "kosdaq_night", "usdkrw", "wti", "nasdaq", "sp500", "dow", "sox")

_NEWS_TOP_N = 3  # 뉴스 저널은 그날 최중요 3건만 — 전체 기사는 웹 아카이브(docs/news/)가 보존

# 스텁에 내장하는 Dataview 자동 조회 — TH_DATA/README.md 스키마 계약(tickers/themes)을 소비.
# 생성 시 1회 내장이므로 기존 파일 불가침 계약과 충돌하지 않는다.
_STOCK_QUERY = '''
## 매매 기록 (자동)

```dataview
TABLE pnl AS "그날 손익", file.link AS 저널
FROM "10_Journal/trades"
WHERE contains(tickers, this.티커)
SORT date DESC
```
'''

_THEME_QUERY = '''
## 테마로 뜬 날 (자동)

```dataview
LIST
FROM "10_Journal/morning"
WHERE contains(themes, this.테마)
SORT date DESC
LIMIT 30
```
'''


def enabled() -> bool:
    return VAULT_DIR.is_dir()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _yaml_str(s: str) -> str:
    """YAML 큰따옴표 문자열 — 뉴스 제목 등 임의 텍스트용 최소 이스케이프."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _stub(path: Path, frontmatter: str, heading: str, extra: str = "") -> None:
    """파일이 없을 때만 스텁 생성 — 있으면 사용자 가필로 간주해 건드리지 않는다."""
    if path.exists():
        return
    _write(path, f"---\n{frontmatter}\n---\n# {heading}\n\n(자동 생성 스텁 — 자유롭게 기록)\n{extra}")


def write_morning() -> Path | None:
    """오늘 시장 스냅샷 + TOP7 뉴스 + 테마 → 10_Journal/morning/{date}.md."""
    if not enabled():
        return None
    market = pipelines.get_market()
    news = pipelines.get_news()
    top7 = news_rank.top(news, 7)
    themes = themes_calc.extract_themes(news, top_n=3)
    date = today_str()

    theme_names = [t.get("name", "") for t in themes if t.get("name")]
    lines = ["---", f"date: {date}", "type: morning-report"]
    if theme_names:
        lines.append(f"themes: [{', '.join(theme_names)}]")  # 스키마 계약: 테마 조회축
    lines += ["---", f"# {date} 모닝리포트", "", "## 시장"]
    for key in _MARKET_KEYS:
        q = market.get(key)
        if not q or q.price is None:
            continue
        pct = f" ({q.change_pct:+.2f}%)" if q.change_pct is not None else ""
        lines.append(f"- {q.name or key}: {q.price:,.2f}{pct}")

    lines += ["", "## 주목 뉴스"]
    for a in top7:
        lines.append(f"- [{a.title}]({a.link}) — {a.source}")

    if themes:
        lines += ["", "## 테마"]
        for t in themes:
            name = t.get("name", "")
            lines.append(f"- [[20_Memory/themes/{name}|{name}]] ({t.get('count', 0)}건)")
            _stub(_MEMORY_THEMES / f"{name}.md", f"type: theme-memory\n테마: {name}", name, extra=_THEME_QUERY)

    path = _JOURNAL / "morning" / f"{date}.md"
    _write(path, "\n".join(lines) + "\n")
    log.info("모닝 저널 기록: %s", path)
    return path


def write_news() -> Path | None:
    """오늘 최중요 뉴스 TOP3 → 10_Journal/news/{date}.md (DB 조회용 headlines frontmatter 포함).

    랭킹은 모닝리포트와 동일 기준(calculators/news_rank: 속보/매크로/반도체·AI 가중).
    전체 기사 보존본은 웹 아카이브(docs/news/YYYY-MM-DD/)가 담당 — vault는 그날의 기억만.
    """
    if not enabled():
        return None
    articles = pipelines.get_news()
    top = news_rank.top(articles, _NEWS_TOP_N)
    date = today_str()
    labels = dict(CATEGORY_ORDER)

    lines = ["---", f"date: {date}", "type: news-digest"]
    if top:
        lines.append("headlines:")
        lines += [f"  - {_yaml_str(a.title)}" for a in top]
    lines += ["---", f"# {date} 뉴스 TOP {_NEWS_TOP_N}"]
    for i, a in enumerate(top, 1):
        cats = " · ".join(labels[c] for c in a.categories if c in labels)
        line = f"{i}. [{a.title}]({a.link}) — {a.source}"
        if cats:
            line += f" · {cats}"
        lines.append(line)
    if not top:
        lines.append("(수집된 뉴스 없음)")

    path = _JOURNAL / "news" / f"{date}.md"
    _write(path, "\n".join(lines) + "\n")
    log.info("뉴스 저널 기록: %s (TOP %d)", path, len(top))
    return path


def write_trades() -> list[Path]:
    """원장 전체를 날짜별로 묶어 10_Journal/trades/{date}.md 재생성(멱등 — 내용 불변이면 git diff 없음).

    종목별 20_Memory 스텁도 함께 생성한다(이미 있으면 건드리지 않음).
    """
    if not enabled():
        return []
    trades = trade_repository.load_trades()
    by_date: dict[str, list] = {}
    for t in trades:
        by_date.setdefault(t.date, []).append(t)

    written: list[Path] = []
    for date, day_trades in by_date.items():
        day_pnl = round(sum(t.pnl for t in day_trades), 2)
        tickers = list(dict.fromkeys(t.ticker for t in day_trades if t.ticker))  # 중복 제거·순서 유지
        lines = ["---", f"date: {date}", "type: trade-journal", f"pnl: {day_pnl}"]
        if tickers:
            # 스키마 계약: 종목 조회축 — 20_Memory 스텁의 매매기록 자동 표가 이 키로 조회한다
            lines.append(f"tickers: [{', '.join(_yaml_str(c) for c in tickers)}]")
        lines += ["---", f"# {date} 매매일지"]
        for t in day_trades:
            label = CATEGORY_LABELS.get(t.category, t.category)
            sign = "+" if t.pnl >= 0 else ""
            line = f"- [[20_Memory/stocks/{t.name}|{t.name}]]({t.ticker}) {label} · {sign}{t.pnl:,.0f}원"
            if t.profit_pct is not None:
                line += f" ({t.profit_pct:+.2f}%)"
            if t.memo:
                line += f" — {t.memo}"
            lines.append(line)
            _stub(
                _MEMORY_STOCKS / f"{t.name}.md",
                f"type: stock-memory\n종목명: {t.name}\n티커: \"{t.ticker}\"\nstatus: 관심",
                t.name,
                extra=_STOCK_QUERY,
            )

        path = _JOURNAL / "trades" / f"{date}.md"
        _write(path, "\n".join(lines) + "\n")
        written.append(path)

    log.info("매매 저널 기록: %d일치", len(written))
    return written
