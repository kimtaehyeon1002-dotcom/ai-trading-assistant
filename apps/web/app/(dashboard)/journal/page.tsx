"use client";

// 매매일지 + Trading Coach — Notion 임포트 → 코드 메트릭 대시보드 → 교육형 회고.
// 매수/매도 추천·목표가 없음. 코치는 행동 패턴+일반 리스크관리 교육만.
import { useEffect, useState } from "react";
import {
  importJournal,
  getJournalEntries,
  getJournalMetrics,
  coachJournal,
} from "@/lib/api-client";

export default function JournalPage() {
  const [metrics, setMetrics] = useState<any>(null);
  const [entries, setEntries] = useState<any[]>([]);
  const [coach, setCoach] = useState<any>(null);
  const [question, setQuestion] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setMetrics(await getJournalMetrics());
      setEntries(await getJournalEntries(50));
    } catch (e: any) {
      setMsg(e.message);
    }
  }
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onImport() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await importJournal();
      setMsg(`Notion 임포트: 신규 ${r.imported} · 중복 ${r.skipped}${r.is_stub ? " (스텁 데이터)" : ""}`);
      await refresh();
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onCoach() {
    setBusy(true);
    try {
      setCoach(await coachJournal(question || undefined));
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  const M = metrics;
  return (
    <div className="row" style={{ flexDirection: "column" }}>
      <div className="panel">
        <h2>매매일지 + Trading Coach</h2>
        <span className="badge">정보·교육 목적 · 매수/매도 추천 없음</span>
        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={onImport} disabled={busy}>Notion에서 가져오기</button>
        </div>
        {msg && <p className="muted">{msg}</p>}
      </div>

      {M && M.n_trades > 0 && (
        <div className="panel">
          <h3>지표 (코드 계산)</h3>
          <ul>
            <li>거래 {M.n_trades}건 · 승 {M.n_wins} / 패 {M.n_losses} / 무 {M.n_draws}</li>
            <li>승률 {M.win_rate != null ? `${Math.round(M.win_rate * 100)}%` : "—"} · 손익비 {M.profit_factor ?? "—"} · 기대값 ${M.expectancy ?? "—"}</li>
            <li>순손익 ${M.net_pnl} · 최대 연속손실 {M.max_loss_streak}회 · 최대낙폭 ${M.max_drawdown}</li>
          </ul>
          {M.unavailable?.length > 0 && (
            <p className="muted">데이터 부족으로 미계산: {M.unavailable.join(", ")}</p>
          )}
        </div>
      )}

      <div className="panel">
        <h3>교육형 회고</h3>
        <div className="row">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="질문(선택) — 예: 내 손실 패턴이 뭐야?"
            style={{ flex: 1, minWidth: 240 }}
          />
          <button onClick={onCoach} disabled={busy}>코치 분석</button>
        </div>
        {coach && (
          <>
            {coach.blocked && <span className="badge" style={{ background: "#5a2b2b" }}>컴플라이언스 차단됨</span>}
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{coach.markdown}</pre>
          </>
        )}
      </div>

      {entries.length > 0 && (
        <div className="panel">
          <h3>최근 거래</h3>
          <ul>
            {entries.slice(0, 15).map((e) => (
              <li key={e.entry_id} className="muted">
                {e.traded_on ?? "—"} · {e.symbol} · {e.position} · {e.outcome} · ${e.pnl}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
