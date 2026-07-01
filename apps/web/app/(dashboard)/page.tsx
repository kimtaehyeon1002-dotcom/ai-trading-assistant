"use client";

import { useEffect, useState } from "react";
import { me, searchSymbols, getQuote } from "@/lib/api-client";

export default function DashboardPage() {
  const [user, setUser] = useState<any>(null);
  const [symbols, setSymbols] = useState<any[]>([]);
  const [quote, setQuote] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setUser(await me());
        const s = await searchSymbols("");
        setSymbols(s.data);
        if (s.data[0]) setQuote(await getQuote(s.data[0].instrument_id));
      } catch (err: any) {
        setError(err.message);
      }
    })();
  }, []);

  if (error) {
    return (
      <div className="panel">
        <p style={{ color: "#ff6b6b" }}>{error}</p>
        <a href="/login">로그인하기</a>
      </div>
    );
  }

  return (
    <div className="row" style={{ flexDirection: "column" }}>
      <div className="panel">
        <h2>대시보드</h2>
        {user ? (
          <p className="muted">
            {user.email} · {user.role} · 스타일: {user.investment_styles?.join(", ")}
          </p>
        ) : (
          <p className="muted">불러오는 중…</p>
        )}
      </div>

      <div className="panel">
        <h3>종목 (시드)</h3>
        <ul>
          {symbols.map((s) => (
            <li key={s.instrument_id}>
              {s.name} ({s.symbol_norm}) · {s.market} · {s.currency}
            </li>
          ))}
        </ul>
      </div>

      {quote && (
        <div className="panel">
          <h3>현재가 — {quote.symbol_norm}</h3>
          <p>
            {quote.price} {quote.currency}{" "}
            {quote.change_pct != null && (
              <span className="muted">({quote.change_pct}%)</span>
            )}
          </p>
          <p className="muted">
            출처 {quote.meta?.source} · {quote.meta?.is_realtime ? "실시간" : "지연/EOD"} · 기준{" "}
            {quote.meta?.as_of}
          </p>
        </div>
      )}
    </div>
  );
}
