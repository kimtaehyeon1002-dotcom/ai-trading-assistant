# 10_Journal — 봇 전용 (자동 생성)

빌드가 매일 아래 노트를 생성한다. **사용자는 이 폴더의 파일을 수정하지 않는다**
(다음 빌드가 덮어쓸 수 있음). 코멘트를 달고 싶으면 `20_Memory/` 노트에서
`[[10_Journal/trades/2026-07-21]]`처럼 링크를 걸어 작성한다.

```
morning/YYYY-MM-DD.md   모닝리포트 요약 (docs/morning HTML의 md 버전)
news/YYYY-MM-DD.md      뉴스 상위 랭크 + 테마
trades/YYYY-MM-DD.md    매매일지 (당일 체결 기준)
```

노트 frontmatter 계약(봇 생성 시):

```yaml
---
date: 2026-07-21
type: morning-report | news-digest | trade-journal
tickers: [삼성전자, SK하이닉스]   # 본문에서 [[20_Memory/stocks/...]] 위키링크 병행
---
```
