---
type: home
---
# 📈 Trading Memory Home

> 이 노트는 Obsidian 안에서 보는 요약 대시보드다. Dataview 플러그인 설치 시 아래 쿼리가 동작한다.
> (플러그인 없이도 링크는 전부 동작 — Dataview는 선택 사항)

## 워치리스트

```dataview
TABLE 티커, 시장, 목표가, 메모
FROM "00_Watchlist"
SORT file.name ASC
```

## 최근 매매일지

```dataview
LIST
FROM "10_Journal/trades"
SORT file.name DESC
LIMIT 10
```

## 최근 모닝리포트

```dataview
LIST
FROM "10_Journal/morning"
SORT file.name DESC
LIMIT 7
```

## 종목 메모리

- [[20_Memory/README|메모리 사용법]] — 종목/테마 노트를 열면 백링크 패널에 관련 매매·뉴스가 자동으로 모인다.
