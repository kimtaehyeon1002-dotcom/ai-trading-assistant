"""루프 기준값(SLO) — "정상"의 단일 정의. design/26 §3-1.

이 표가 존재하는 이유: 정상/이상 판정을 LLM에 맡기면 실행마다 기준이 흔들린다(design/26 §1-2 B-3).
판정은 여기 선언된 설정점과 scripts/health_probe.py(결정론적)가 하고, LLM은 이미 확정된 이슈만 고친다.

**설계서는 ops/slo.yml을 제안했으나 파이썬 모듈로 구현한다** — config/themes.py·config/economic_calendar.py가
이미 "주석 달린 파이썬 상수 테이블"이라는 이 저장소의 설정 관례이고, YAML 파서(PyYAML)를 이 한 파일
때문에 requirements에 추가할 이유가 없다.

각 값의 근거는 .github/workflows/*.yml의 실제 cron이다. 임계값은 **"정상 운영 중 절대 넘지 않는 최댓값"**
으로 잡는다 — 오탐 1건이 나오면 이 루프 전체의 신뢰가 무너지므로, 민감도보다 정확도를 우선한다
(design/26 Phase A DoD "오탐 0").
"""
from __future__ import annotations

from dataclasses import dataclass

# 티어 — 이 워커를 클라우드 루틴이 고칠 수 있는가(design/26 §3-7).
# desktop = Kiwoom OCX/32bit Windows 의존. 클라우드는 관측만 하고 절대 수정하지 않는다.
TIER_CLOUD = "cloud"
TIER_DESKTOP = "desktop"


@dataclass(frozen=True)
class WorkerSLO:
    """워커 1종의 설정점.

    cadence_min : 기대 갱신 주기(분). None=on-demand(스케줄 기대 없음) → 신선도 규칙을 적용하지 않는다.
    max_age_h   : 평일 허용 최대 경과시간. cadence_min이 None이면 무시된다.
    max_age_weekend_h : 구간에 토·일이 낀 경우의 상한. None이면 주말에도 평일 값을 쓴다(24/7 워커).
                        평일/주말 이원화는 야간선물 만료(config/settings.py NIGHT_FUTURES_*)와 같은 패턴이다.
    status_ok   : 허용 상태 집합. skipped가 정상인 워커가 있다(키 미설정 등) — 사실대로 선언한다.
    min_items   : status=completed일 때 요구되는 최소 처리 건수. 수집이 "성공했지만 0건"인
                  조용한 실패를 잡는 유일한 규칙이다.
    """

    owner: str                       # 담당 워크플로/실행 주체
    cadence_min: int | None
    max_age_h: float | None = None
    max_age_weekend_h: float | None = None
    status_ok: tuple[str, ...] = ("completed",)
    min_items: int | None = None
    tier: str = TIER_CLOUD
    note: str = ""


_H_DAY = 26.0        # 일1회 워커의 평일 상한(24h + 유예 2h — Actions 스케줄 지연 흡수)
# 금요일 실행 → 월요일 실행(72h) + 유예 8h. 유예가 큰 이유: GitHub Actions의 schedule은
# best-effort라 피크에 1~2시간씩 밀린다. 76h로 잡았더니 월요일 아침 여유가 1.1h밖에 안 남아
# 지연 한 번이면 가짜 위반이 났다(주말 정책 도입 시 실측). 민감도보다 오탐 0이 우선이다.
_H_DAY_WEEKEND = 80.0
_H_30MIN = 3.0       # 30~60분 주기 워커의 상한(연속 몇 회 실패까지는 자가복구를 기다린다)

# ── 주말 상한 (design/26 §8-6) ────────────────────────────────────────────────
# 2026-07-31부터 시세성 워크플로가 주말에 정지한다. **크론을 바꾸면 여기도 같이 바꿔야 한다** —
# 안 그러면 토·일 내내 워커 12종이 "안 돌았다"는 가짜 위반을 낸다(오탐 0 원칙 붕괴).
# KST 토 09:00 = UTC 토 00:00이라 주말은 UTC 요일 0,6과 정확히 일치한다.
_H_WEEKEND_STOP = 52.0    # 주말 완전 정지: 금 23:00 UTC → 월 00:00 UTC = 49h + 유예 3h
_H_WEEKEND_SLOW = 6.0     # 주말 감속(뉴스 2시간 주기): 2회 연속 실패까지 흡수

# ── 워커 설정점 ────────────────────────────────────────────────────────────────
# runlog.json의 워커명을 **그대로** 키로 쓴다(utils/runlog.py에 기록되는 문자열).
# 여기 선언됐는데 runlog에 없는 워커는 그 자체가 위반이다(missing) — 조용히 실행되지 않는
# 워커를 잡는 유일한 규칙이므로, 신규 워커를 추가하면 반드시 이 표에도 등재한다.
WORKERS: dict[str, WorkerSLO] = {
    # 모든 빌드의 공통 단계(build.py) — 가장 잦은 news.yml이 실효 주기를 정한다
    # (평일 30분 / 주말 2시간)
    "Vault Sync": WorkerSLO(
        owner="build.py(전 타깃)", cadence_min=30, max_age_h=_H_30MIN,
        max_age_weekend_h=_H_WEEKEND_SLOW, status_ok=("completed", "skipped"),
        note="TH_DATA_TOKEN 미설정/폴더 없음이면 skipped가 정상(build.py _sync_vault)",
    ),
    "Vault Journal": WorkerSLO(
        owner="build.py(morning·news·trades)", cadence_min=30, max_age_h=_H_30MIN,
        max_age_weekend_h=_H_WEEKEND_SLOW,
        note="vault_journal.enabled()가 False면 기록 자체가 남지 않는다 — missing이 곧 신호",
    ),
    "Publisher": WorkerSLO(
        owner="build.py(전 타깃)", cadence_min=30, max_age_h=_H_30MIN,
        max_age_weekend_h=_H_WEEKEND_SLOW,
    ),
    "Loop Ledger": WorkerSLO(
        owner="build.py(전 타깃)", cadence_min=30, max_age_h=_H_30MIN,
        max_age_weekend_h=_H_WEEKEND_SLOW, status_ok=("completed", "skipped"),
        note="ops/ledger.jsonl → vault 50_Ops/ 투영. TH_DATA 없으면 skipped가 정상",
    ),

    # news.yml — 평일 */30, 주말 2시간(정지하지 않고 감속만 — 속보는 주말에도 난다)
    "News Research": WorkerSLO(
        owner="news.yml", cadence_min=30, max_age_h=_H_30MIN,
        max_age_weekend_h=_H_WEEKEND_SLOW, min_items=20,
        note="RSS 전량 실패 시 0건으로 completed 될 수 있어 min_items가 실질 게이트",
    ),
    "Translator": WorkerSLO(
        owner="news.yml", cadence_min=30, max_age_h=_H_30MIN,
        max_age_weekend_h=_H_WEEKEND_SLOW,
        note="번역 대상이 없으면 items=기사수 그대로 — 건수 하한 의미 없음",
    ),

    # pipelines.get_market()의 최다 호출부는 dashboard_v2다 — 대시보드는 build.py 공통 마무리라
    # **모든 타깃**이 지나간다. 따라서 실효 주기는 morning(일1회)이 아니라 news.yml(30분)이다.
    "Data Officer": WorkerSLO(
        owner="build.py 공통 마무리(dashboard_v2) — 실효 주기는 news.yml", cadence_min=30,
        max_age_h=_H_30MIN, max_age_weekend_h=_H_WEEKEND_SLOW,
        note="morning·macro·asset·vault_journal도 호출하지만 주기를 정하는 건 30분짜리 news.yml이다",
    ),

    # morning.yml — 06:30 KST 월~금(+ data/cache push). 아래 둘은 morning 타깃에서만 호출된다
    "Theme Analyst": WorkerSLO(
        owner="morning.yml", cadence_min=24 * 60, max_age_h=_H_DAY, max_age_weekend_h=_H_DAY_WEEKEND,
        note="generators/morning/generate.py:40이 유일 호출부",
    ),
    "TA Analyst": WorkerSLO(
        owner="morning.yml", cadence_min=24 * 60, max_age_h=_H_DAY, max_age_weekend_h=_H_DAY_WEEKEND,
        note="registry._morning()이 morning 타깃에 편입 실행(design/21 §5-2)",
    ),

    # macro.yml — 매시 정각, **월~금(UTC)만**. 주말 정지(FRED·ECOS 주말 발표 없음)
    "Macro FRED": WorkerSLO(owner="macro.yml", cadence_min=60, max_age_h=_H_30MIN,
                             max_age_weekend_h=_H_WEEKEND_STOP),
    "Macro ECOS": WorkerSLO(
        owner="macro.yml", cadence_min=60, max_age_h=_H_30MIN,
        max_age_weekend_h=_H_WEEKEND_STOP, status_ok=("completed", "skipped"),
        note="ECOS_API_KEY 미설정 시 skipped가 정상(design/21 §226 결측 문법)",
    ),
    "Macro Upbit": WorkerSLO(owner="macro.yml", cadence_min=60, max_age_h=_H_30MIN,
                             max_age_weekend_h=_H_WEEKEND_STOP),
    "Macro History": WorkerSLO(owner="macro.yml", cadence_min=60, max_age_h=_H_30MIN,
                             max_age_weekend_h=_H_WEEKEND_STOP),

    # stock.yml — KR 장중 매시(00~06 UTC 월~금) + KR 마감(06:35 UTC) + US 마감후(22:00 UTC 월~금).
    # 주 마지막 실행은 토 07:00 KST, 다음 실행은 월 09:00 KST → 50h. 평일 최장 공백은
    # 월 15:35 KST → 화 07:00 KST = 15.4h.
    "Stock KR Ranking": WorkerSLO(
        owner="stock.yml", cadence_min=60, max_age_h=20.0, max_age_weekend_h=54.0, min_items=1000,
        note="KRX 전종목 — 실측 2873건. 1000 미만이면 수집 절반 이상 실패",
    ),
    "Stock US Ranking": WorkerSLO(
        owner="stock.yml", cadence_min=60, max_age_h=20.0, max_age_weekend_h=54.0, min_items=400,
        note="S&P500 — 실측 503건",
    ),
    "Stock Hub 보조시세": WorkerSLO(
        owner="stock.yml", cadence_min=60, max_age_h=20.0, max_age_weekend_h=54.0,
        note="유니버스 결손분만 보충 — 결손이 없으면 0건이 정상이라 하한 없음",
    ),

    # financials.yml — UTC 일~목 21:00 = KST 월~금 06:00. 주말 정지(공시 없음)
    "FS DART corpCode": WorkerSLO(
        owner="financials.yml", cadence_min=24 * 60, max_age_h=_H_DAY,
        max_age_weekend_h=_H_DAY_WEEKEND,
        note="DART_API_KEY 미설정이면 예외 → error. 키가 없다면 status_ok에 skipped를 넣지 말고 키를 넣어라",
    ),
    "FS EDGAR CIK맵": WorkerSLO(
        owner="financials.yml", cadence_min=24 * 60, max_age_h=_H_DAY,
        max_age_weekend_h=_H_DAY_WEEKEND,
        note="EDGAR는 키 불필요(User-Agent만) — 실패는 진짜 장애다",
    ),

    # trades.yml — push 트리거 전용. 매매 입력이 없으면 몇 주도 안 도는 게 정상이다
    "Trade Manager": WorkerSLO(
        owner="trades.yml(push)", cadence_min=None,
        note="on-demand — 신선도 규칙 없음. 상태만 본다",
    ),

    # 자산 수집은 주체가 둘로 갈린다(design/28) — KIS·BYBIT는 REST라 CI가, Kiwoom은 OCX가
    # 데스크톱 세션을 요구해 로컬이 담당한다. 티어가 다르므로 SLO도 따로 선언한다.
    "Asset Kiwoom": WorkerSLO(
        owner="run_desktop(로컬)", cadence_min=24 * 60, max_age_h=_H_DAY,
        max_age_weekend_h=_H_DAY_WEEKEND, status_ok=("completed", "skipped"), tier=TIER_DESKTOP,
        note="32bit Windows + Kiwoom OCX 필요. CI는 이 워커를 아예 기록하지 않으므로"
             " (pipelines._kiwoom_available) last_run이 데스크톱 실행 시각 그대로다 —"
             " 이 신선도가 'PC를 며칠 안 켰다'를 재는 유일한 신호다",
    ),
    "Asset KIS 위탁": WorkerSLO(
        owner="asset.yml", cadence_min=12 * 60, max_age_h=_H_DAY,
        max_age_weekend_h=_H_DAY_WEEKEND, status_ok=("completed", "skipped"),
        note="REST라 PC 전원과 무관하게 CI가 하루 2회(09:00·18:00 KST) 수집한다",
    ),
    "Asset KIS ISA": WorkerSLO(
        owner="asset.yml", cadence_min=12 * 60, max_age_h=_H_DAY,
        max_age_weekend_h=_H_DAY_WEEKEND, status_ok=("completed", "skipped"),
        note="REST라 PC 전원과 무관하게 CI가 하루 2회(09:00·18:00 KST) 수집한다",
    ),
    "Asset BYBIT": WorkerSLO(
        owner="asset.yml", cadence_min=12 * 60, max_age_h=_H_DAY,
        max_age_weekend_h=_H_DAY_WEEKEND, status_ok=("completed", "skipped"),
        note="REST라 PC 전원과 무관하게 CI가 하루 2회(09:00·18:00 KST) 수집한다",
    ),
    "Asset Publish": WorkerSLO(
        owner="asset.yml + run_desktop", cadence_min=12 * 60, max_age_h=_H_DAY,
        max_age_weekend_h=_H_DAY_WEEKEND, status_ok=("completed", "skipped"),
        note="양쪽 주체가 모두 발행한다. detail의 '수집/승계/결측'이 어느 계좌가 신선한지 알려준다",
    ),
}

# ── 워크플로 설정점 ────────────────────────────────────────────────────────────
# gh run list로 최근 이력을 읽어 연속 실패를 본다. gh가 없거나 인증이 안 되면 이 축은
# 통째로 skip하고 사실대로 기록한다(없는 데이터를 추정하지 않는다).
WORKFLOWS: dict[str, dict] = {
    "news.yml":       {"max_consecutive_failures": 3, "desc": "News Center (*/30)"},
    "macro.yml":      {"max_consecutive_failures": 3, "desc": "Macroeconomics (매시)"},
    "morning.yml":    {"max_consecutive_failures": 1, "desc": "Morning Report (06:30 KST 월~금)"},
    "stock.yml":      {"max_consecutive_failures": 3, "desc": "Stock Ranking (장중·마감)"},
    "financials.yml": {"max_consecutive_failures": 2, "desc": "Financial Statements (06:00 KST)"},
    "trades.yml":     {"max_consecutive_failures": 1, "desc": "Trades Dashboard (push)"},
}

# 최근 N회를 조회해 연속 실패를 센다. 워크플로별 주기가 달라 "최근 N회"가 곧 시간창은 아니다.
WORKFLOW_LOOKBACK = 10

# ── 심각도 ────────────────────────────────────────────────────────────────────
# critical = 발행물이 이미 틀렸거나 곧 틀려진다 / major = 신선도·완결성 손상 / minor = 관측 결손
SEVERITY_ORDER = ("critical", "major", "minor")
