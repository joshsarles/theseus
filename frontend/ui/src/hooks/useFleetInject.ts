import { useCallback, useRef, useState } from "react";
import type { InjectResult } from "../lib/types";

const API_BASE =
  (import.meta.env.VITE_THESEUS_API as string | undefined) ??
  "http://localhost:8501";

export const INJECT_URL = `${API_BASE}/api/fleet/inject`;

const INJECT_TIMEOUT_MS = 15000;

/**
 * Phases of the live poison-rejection beat:
 *   idle      — armed, awaiting the operator
 *   injecting — the forged delta is in flight to the fleet brain
 *   done      — the gate decided; `result` holds the REAL report
 *   error     — the endpoint was unreachable (no API / offline)
 */
export type InjectPhase = "idle" | "injecting" | "done" | "error";

interface UseFleetInject {
  phase: InjectPhase;
  result: InjectResult | null;
  inject: () => void;
  reset: () => void;
}

/**
 * The interactive trustworthy-AI moment. POSTs to /api/fleet/inject, which runs
 * the REAL fleet-brain provenance + eval-gated merge over a freshly-forged delta
 * and re-seals + re-verifies the tamper-evident fleet record. The returned report
 * is the actual gate decision — the forged delta REJECTED, the attested deltas
 * merged, the chain re-verified — never a canned animation.
 */
export function useFleetInject(): UseFleetInject {
  const [phase, setPhase] = useState<InjectPhase>("idle");
  const [result, setResult] = useState<InjectResult | null>(null);
  const inFlight = useRef(false);

  const inject = useCallback(() => {
    if (inFlight.current) return; // guard against double-fire / rapid clicks
    inFlight.current = true;
    setPhase("injecting");
    setResult(null);
    void (async () => {
      try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), INJECT_TIMEOUT_MS);
        const res = await fetch(INJECT_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
          signal: ctrl.signal,
        });
        clearTimeout(t);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = (await res.json()) as InjectResult;
        setResult(json);
        setPhase("done");
      } catch {
        setPhase("error");
      } finally {
        inFlight.current = false;
      }
    })();
  }, []);

  const reset = useCallback(() => {
    setPhase("idle");
    setResult(null);
  }, []);

  return { phase, result, inject, reset };
}
