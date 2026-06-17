import { DECISION_URL } from "../hooks/useShipState";
import type { Verdict } from "./types";

export interface DecisionResult {
  ok: boolean;
  /** true if the server confirmed the seal; false if we sealed locally only */
  serverSealed: boolean;
  status?: number;
}

/**
 * POST a watch-officer ruling to the record. The endpoint is being added
 * server-side; until it returns 2xx we still seal the leaf locally so the
 * "human decides → proven in the record" beat lands. tamper-EVIDENT: the
 * local leaf is flagged as locally-sealed, never silently presented as server
 * truth.
 */
export async function postDecision(
  contactId: string,
  verdict: Verdict,
): Promise<DecisionResult> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 3000);
    const res = await fetch(DECISION_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contact_id: contactId, verdict, by: "WATCH" }),
      signal: ctrl.signal,
    });
    clearTimeout(t);
    return { ok: true, serverSealed: res.ok, status: res.status };
  } catch {
    return { ok: false, serverSealed: false };
  }
}
