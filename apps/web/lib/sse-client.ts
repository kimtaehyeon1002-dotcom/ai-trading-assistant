// SSE 구독 유틸 — Phase 2 리서치 스트리밍이 재사용.
// 이벤트 타입: token | stage | tool | done | error (설계서 §7.1)
export type SseHandlers = {
  onToken?: (text: string) => void;
  onStage?: (stage: string) => void;
  onTool?: (tool: any) => void;
  onDone?: (result: any) => void;
  onError?: (err: any) => void;
};

export function subscribe(streamUrl: string, handlers: SseHandlers): () => void {
  // EventSource는 헤더 설정 불가 → 토큰은 쿼리스트링으로 전달(Phase 2에서 서버가 검증).
  const access = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const url = access ? `${streamUrl}${streamUrl.includes("?") ? "&" : "?"}token=${access}` : streamUrl;
  const es = new EventSource(url);

  // token은 개행을 포함할 수 있어 서버가 JSON({t})으로 감싼다(SSE 프레이밍 보호).
  es.addEventListener("token", (e) => {
    const d = (e as MessageEvent).data;
    try {
      handlers.onToken?.(JSON.parse(d).t ?? "");
    } catch {
      handlers.onToken?.(d);
    }
  });
  es.addEventListener("stage", (e) => handlers.onStage?.((e as MessageEvent).data));
  es.addEventListener("tool", (e) => handlers.onTool?.(JSON.parse((e as MessageEvent).data)));
  es.addEventListener("done", (e) => {
    handlers.onDone?.(JSON.parse((e as MessageEvent).data));
    es.close();
  });
  es.addEventListener("error", (e) => handlers.onError?.(e));

  return () => es.close();
}
