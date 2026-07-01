"use client";

// AI Research — 종목/질문 입력 → 4-블록 리포트를 SSE로 스트리밍(설계서 §2.4, §1.3-B).
// 모든 출력은 가드레일 통과 + 면책. 매수/매도 추천·목표가 없음.
import { useRef, useState } from "react";
import { API_ORIGIN, createResearchJob } from "@/lib/api-client";
import { subscribe } from "@/lib/sse-client";

type ToolEvent = { tool: string; ok: boolean; summary?: string; source?: string; count?: number; error?: string };

export default function ResearchPage() {
  const [symbol, setSymbol] = useState("005930");
  const [query, setQuery] = useState("");
  const [depth, setDepth] = useState("standard");
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState("");
  const [tools, setTools] = useState<ToolEvent[]>([]);
  const [text, setText] = useState("");
  const [done, setDone] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const cleanupRef = useRef<null | (() => void)>(null);

  async function onRun(e: React.FormEvent) {
    e.preventDefault();
    cleanupRef.current?.();
    setRunning(true);
    setStage("");
    setTools([]);
    setText("");
    setDone(null);
    setError(null);
    try {
      const job = await createResearchJob({
        symbol: symbol || null,
        query: query || null,
        depth,
        style: "swing",
      });
      cleanupRef.current = subscribe(`${API_ORIGIN}${job.stream_url}`, {
        onStage: (s) => {
          try {
            const o = JSON.parse(s);
            setStage(o.label || o.stage);
          } catch {
            setStage(s);
          }
        },
        onTool: (t) => setTools((prev) => [...prev, t]),
        onToken: (tok) => setText((prev) => prev + tok),
        onDone: (d) => {
          setDone(d);
          setRunning(false);
        },
        onError: () => {
          setError("스트리밍 오류가 발생했습니다.");
          setRunning(false);
        },
      });
    } catch (err: any) {
      setError(err.message);
      setRunning(false);
    }
  }

  return (
    <div className="row" style={{ flexDirection: "column" }}>
      <div className="panel">
        <h2>AI Research</h2>
        <span className="badge">매수/매도 추천·목표가 없음 · 정보·교육 목적</span>
        <form onSubmit={onRun} className="row" style={{ flexWrap: "wrap", marginTop: 12 }}>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="종목 (예: 005930, AAPL)"
            style={{ minWidth: 180 }}
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="질문 (선택)"
            style={{ flex: 1, minWidth: 220 }}
          />
          <select value={depth} onChange={(e) => setDepth(e.target.value)}>
            <option value="standard">표준 (Sonnet)</option>
            <option value="deep">심층 (Opus)</option>
          </select>
          <button type="submit" disabled={running}>
            {running ? "분석 중…" : "리서치"}
          </button>
        </form>
      </div>

      {stage && (
        <div className="panel">
          <p className="muted">단계: {stage}</p>
          {tools.length > 0 && (
            <ul>
              {tools.map((t, i) => (
                <li key={i} className="muted">
                  {t.ok ? "✓" : "—"} {t.tool}
                  {t.summary ? `: ${t.summary}` : t.error ? `: ${t.error}` : t.count != null ? `: ${t.count}건` : ""}
                  {t.source ? ` (${t.source})` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {error && (
        <div className="panel">
          <p style={{ color: "#ff6b6b" }}>{error}</p>
        </div>
      )}

      {(text || done) && (
        <div className="panel">
          {done?.blocked && (
            <span className="badge" style={{ background: "#5a2b2b" }}>
              컴플라이언스 차단됨 — 중립 안내로 대체
            </span>
          )}
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", margin: "8px 0" }}>{text}</pre>
          {done?.report_id && (
            <p className="muted">리포트 ID: {done.report_id} · 상태: {done.status}</p>
          )}
        </div>
      )}
    </div>
  );
}
