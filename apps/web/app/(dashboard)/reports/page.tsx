"use client";

// AI 모닝리포트 — 날짜별 5-섹션 브리핑 + 테마 스코어(관찰 지표). 설계서 §2.4, §2.7.
// 매수/매도 추천 없음. 테마 점수는 관찰 지표이며 매수 신호가 아님.
import { useEffect, useState } from "react";
import {
  getReportByDate,
  getThemeScores,
  generateReport,
  me,
} from "@/lib/api-client";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const [date, setDate] = useState(today());
  const [report, setReport] = useState<any>(null);
  const [themesUs, setThemesUs] = useState<any[]>([]);
  const [themesKr, setThemesKr] = useState<any[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function load(d: string) {
    setMsg(null);
    try {
      setReport(await getReportByDate(d));
    } catch {
      setReport(null);
      setMsg(`${d} 리포트가 아직 없습니다.`);
    }
    try {
      setThemesUs(await getThemeScores("US"));
      setThemesKr(await getThemeScores("KR"));
    } catch {
      /* themes optional */
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const u = await me();
        setIsAdmin(u.role === "ADMIN" || u.role === "OWNER");
      } catch {
        /* ignore */
      }
      await load(date);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onGenerate() {
    setMsg("생성 요청됨 — 잠시 후 새로고침하세요.");
    try {
      await generateReport({ report_date: date, force: true });
    } catch (e: any) {
      setMsg(e.message);
    }
  }

  function ThemeList({ title, items }: { title: string; items: any[] }) {
    if (!items?.length) return null;
    return (
      <div className="panel">
        <h3>{title} <span className="badge">관찰 지표 · 매수 신호 아님</span></h3>
        <ol>
          {items.map((t) => (
            <li key={t.slug}>
              {t.theme} — score {Math.round(t.score)} (rank {t.rank})
            </li>
          ))}
        </ol>
      </div>
    );
  }

  return (
    <div className="row" style={{ flexDirection: "column" }}>
      <div className="panel">
        <h2>AI 모닝리포트</h2>
        <span className="badge">정보·교육 목적 · 매수/매도 추천 없음</span>
        <div className="row" style={{ marginTop: 12 }}>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <button onClick={() => load(date)}>조회</button>
          {isAdmin && <button onClick={onGenerate}>생성(관리자)</button>}
        </div>
        {msg && <p className="muted">{msg}</p>}
      </div>

      <ThemeList title="미국 강세 테마" items={themesUs} />
      <ThemeList title="예상 한국 강세 테마" items={themesKr} />

      {report && (
        <div className="panel">
          <p className="muted">
            {report.report_date} · {report.status} · {report.model}
            {report.blocked ? " · 차단됨(중립 안내)" : ""}
          </p>
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{report.markdown}</pre>
        </div>
      )}
    </div>
  );
}
