"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api-client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("owner@thbot.local");
  const [password, setPassword] = useState("changeme123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/");
    } catch (err: any) {
      setError(err.message ?? "로그인 실패");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel" style={{ maxWidth: 380, margin: "48px auto" }}>
      <h2>로그인</h2>
      <form onSubmit={onSubmit} className="row" style={{ flexDirection: "column" }}>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="이메일" />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호"
        />
        <button type="submit" disabled={loading}>
          {loading ? "..." : "로그인"}
        </button>
      </form>
      {error && <p style={{ color: "#ff6b6b" }}>{error}</p>}
      <p className="muted">시드 계정: owner@thbot.local / changeme123</p>
    </div>
  );
}
