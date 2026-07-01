import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Th_bot — AI 투자 리서치/비서",
  description: "투자 판단 보조 (매수/매도 추천 없음)",
};

const SHORT_DISCLAIMER =
  "※ 본 서비스의 모든 내용은 정보제공·교육 목적의 참고자료이며, 특정 종목의 매수·매도 권유나 투자자문이 아닙니다. " +
  "투자 판단과 결과에 대한 책임은 이용자 본인에게 있으며, 투자에는 원금 손실 위험이 있습니다.";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="nav">
          <strong>Th_bot</strong>
          <span className="badge">판단 보조 · 추천 없음</span>
          <div style={{ flex: 1 }} />
          <a href="/">대시보드</a>
          <a href="/research">리서치</a>
          <a href="/login">로그인</a>
        </div>
        <main className="container">{children}</main>
        <footer className="container">
          <p className="disclaimer">{SHORT_DISCLAIMER}</p>
        </footer>
      </body>
    </html>
  );
}
