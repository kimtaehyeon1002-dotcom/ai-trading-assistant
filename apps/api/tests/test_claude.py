"""Claude 래퍼 — 모델 라우팅 + 비용 계산 + 스텁 모드."""
from app.agents.claude import ClaudeResult
from app.agents.router import HAIKU, OPUS, SONNET, Task, model_for


def test_model_routing():
    assert model_for(Task.PING) == HAIKU
    assert model_for(Task.CLASSIFY) == HAIKU
    assert model_for(Task.RESEARCH) == SONNET
    assert model_for(Task.RESEARCH_DEEP) == OPUS
    assert model_for(Task.MORNING_REPORT) == OPUS


def test_cost_opus():
    # Opus 4.8: $5/$25 per MTok → 1M in + 1M out = $30
    r = ClaudeResult(text="x", model=OPUS, task_type="research_deep",
                     input_tokens=1_000_000, output_tokens=1_000_000)
    assert r.cost_usd == 30.0


def test_cost_with_cache():
    # cache_read는 input 단가의 0.1x
    r = ClaudeResult(text="x", model=SONNET, task_type="research",
                     input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000)
    # 1M * $3 * 0.1 / 1M = $0.30
    assert r.cost_usd == 0.30


def test_stub_zero_cost():
    r = ClaudeResult(text="[stub]", model=HAIKU, task_type="ping", is_stub=True)
    assert r.cost_usd == 0.0
