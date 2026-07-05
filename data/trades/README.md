# 매매 원장 (trades.json)

카테고리는 **증권사(broker)로 결정**된다 (운용 원칙):

| broker 값 | 증권사 | 카테고리 |
|---|---|---|
| `kiwoom` | 키움증권 | 단타 (자동 동기화) |
| `kb` | KB증권 | 스윙 (수동 입력) |
| `hantoo` | 한국투자증권 | 장기 (수동 입력) |

- 키움 거래는 `run_desktop.bat` 동기화가 자동으로 추가한다 (건드릴 필요 없음).
- KB/한투 거래는 `trades.json` 배열에 아래 형식으로 직접 추가:

```json
{
  "date": "2026-07-10",
  "ticker": "005930",
  "name": "삼성전자",
  "buy_price": 60000,
  "sell_price": 65000,
  "quantity": 10,
  "holding_days": 15,
  "broker": "kb",
  "memo": "실적 발표 후 익절"
}
```

- `category`/`pnl`/`profit_pct`는 자동 계산되므로 **적지 않아도 된다** (broker가 카테고리를 결정).
- 중복 판정 키: (date, ticker, sell_price, quantity) — 같은 키는 동기화 시 추가되지 않는다.
- 추가 후 `run_desktop.bat` 실행(또는 `python build.py trades`)하면 대시보드에 반영된다.
