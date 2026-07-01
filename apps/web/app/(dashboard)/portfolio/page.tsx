"use client";

// 포트폴리오 AI — 보유 입력 → 비중·집중도(HHI)·노출 코드 계산 → 분산 관점 분석.
// 매수/매도·리밸런싱 지시 없음. 집중도는 관찰 지표.
import { useEffect, useState } from "react";
import {
  getHoldings,
  addHolding,
  deleteHolding,
  getPortfolioMetrics,
  analyzePortfolio,
} from "@/lib/api-client";

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [symbol, setSymbol] = useState("");
  const [qty, setQty] = useState("");
  const [avg, setAvg] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setHoldings(await getHoldings());
      setMetrics(await getPortfolioMetrics());
    } catch (e: any) {
      setMsg(e.message);
    }
  }
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await addHolding({
        symbol: symbol || undefined,
        quantity: Number(qty),
        avg_cost: avg ? Number(avg) : undefined,
      });
      setSymbol(""); setQty(""); setAvg("");
      await refresh();
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string) {
    await deleteHolding(id);
    await refresh();
  }

  async function onAnalyze() {
    setBusy(true);
    try {
      setAnalysis(await analyzePortfolio());
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  const M = metrics;
  function Exposure({ title, b }: { title: string; b: any }) {
    if (!b || !Object.keys(b).length) return null;
    return (
      <p className="muted">
        {title}: {Object.entries(b).map(([k, v]: any) => `${k} ${Math.round(v.weight * 100)}%`).join(" · ")}
      </p>
    );
  }

  return (
    <div className="row" style={{ flexDirection: "column" }}>
      <div className="panel">
        <h2>포트폴리오 AI</h2>
        <span className="badge">분산 관점 관찰 · 리밸런싱/매매 지시 없음</span>
        <form onSubmit={onAdd} className="row" style={{ marginTop: 12, flexWrap: "wrap" }}>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="종목 (예: 005930, AAPL)" />
          <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="수량" style={{ width: 100 }} />
          <input value={avg} onChange={(e) => setAvg(e.target.value)} placeholder="평단(선택)" style={{ width: 110 }} />
          <button type="submit" disabled={busy}>보유 추가</button>
        </form>
        {msg && <p className="muted">{msg}</p>}
      </div>

      {M && M.n_positions > 0 && (
        <div className="panel">
          <h3>지표 (코드 계산)</h3>
          <ul>
            <li>총 평가액 {M.total_value} {M.base_currency} · {M.n_positions}종목</li>
            <li>
              집중도 HHI {M.hhi} · 유효 종목수 {M.effective_n} · 밴드 <b>{M.concentration_band}</b>
            </li>
            <li>상위1 {Math.round(M.top1_weight * 100)}% · 상위3 {Math.round(M.top3_weight * 100)}%</li>
          </ul>
          <Exposure title="섹터" b={M.by_sector} />
          <Exposure title="시장" b={M.by_market} />
          <Exposure title="통화" b={M.by_currency} />
          {M.valuation_note && <p className="muted">⚠ {M.valuation_note}</p>}
          <button onClick={onAnalyze} disabled={busy} style={{ marginTop: 8 }}>분산 관점 분석</button>
        </div>
      )}

      {analysis && (
        <div className="panel">
          {analysis.blocked && <span className="badge" style={{ background: "#5a2b2b" }}>컴플라이언스 차단됨</span>}
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{analysis.markdown}</pre>
        </div>
      )}

      {holdings.length > 0 && (
        <div className="panel">
          <h3>보유 종목</h3>
          <ul>
            {holdings.map((h) => (
              <li key={h.holding_id}>
                {h.name ?? h.symbol_norm} · {h.quantity} · {h.weight != null ? `${Math.round(h.weight * 100)}%` : "—"}
                {h.valuation_basis !== "market" ? ` (${h.valuation_basis})` : ""}{" "}
                <button onClick={() => onDelete(h.holding_id)} style={{ marginLeft: 8 }}>삭제</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
