import { useCallback, useEffect, useRef, useState } from "react";
import type { MlflowState } from "../lib/types";

const API_BASE =
  (import.meta.env.VITE_THESEUS_API as string | undefined) ??
  "http://localhost:8501";

export const MLFLOW_URL = `${API_BASE}/api/mlflow`;

const POLL_MS = 8000;
const FETCH_TIMEOUT_MS = 9000;

export type MlflowConn = "connecting" | "live" | "stale" | "offline";

interface UseMlflowState {
  mlflow: MlflowState | null;
  conn: MlflowConn;
  refetch: () => void;
}

/**
 * Polls GET /api/mlflow — the Node-3 MLflow registry status + result metrics
 * (proxied; the browser can't reach MLflow's REST API directly). Honesty
 * contract matching useFleetState: a real 200 with connected:true is "live";
 * a 200 with connected:false (MLflow down behind the proxy) is "offline" and
 * surfaced as such; a transport failure with prior data holds "stale". The
 * registry is never faked — if MLflow is unreachable the UI says so.
 */
export function useMlflowState(): UseMlflowState {
  const [mlflow, setMlflow] = useState<MlflowState | null>(null);
  const [conn, setConn] = useState<MlflowConn>("connecting");
  const mounted = useRef(true);

  const poll = useCallback(async () => {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
      const res = await fetch(MLFLOW_URL, { signal: ctrl.signal });
      clearTimeout(t);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as MlflowState;
      if (!mounted.current) return;
      setMlflow(json);
      setConn(json.connected ? "live" : "offline");
    } catch {
      if (!mounted.current) return;
      setMlflow((prev) => prev); // keep last-good
      setConn((prev) => (prev === "live" || prev === "stale" ? "stale" : "offline"));
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void poll();
    const id = setInterval(() => void poll(), POLL_MS);
    return () => {
      mounted.current = false;
      clearInterval(id);
    };
  }, [poll]);

  return { mlflow, conn, refetch: poll };
}
