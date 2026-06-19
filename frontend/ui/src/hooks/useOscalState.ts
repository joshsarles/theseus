import { useCallback, useEffect, useRef, useState } from "react";
import type { OscalState } from "../lib/types";

const API_BASE =
  (import.meta.env.VITE_THESEUS_API as string | undefined) ??
  "http://localhost:8501";

export const OSCAL_URL = `${API_BASE}/api/oscal`;
export const OSCAL_TAMPER_URL = `${API_BASE}/api/oscal/tamper-preview`;

const POLL_MS = 8000;
const FETCH_TIMEOUT_MS = 6000;

export type OscalConn = "connecting" | "live" | "stale" | "mock";

interface UseOscalState {
  oscal: OscalState | null;
  conn: OscalConn;
  refetch: () => void;
}

/**
 * Polls GET /api/oscal — the sealed record projected onto NIST SP 800-53 rev5
 * as OSCAL assessment-results (the evidence package an Authorizing Official
 * ingests). Same honesty contract as the other hooks: a real 200 is "live";
 * anything else falls to the offline fixture and is surfaced, never silently
 * presented as live. The fixture mirrors a verifying 56-leaf record so the
 * panel reads well even before the endpoint is reachable.
 */
export function useOscalState(): UseOscalState {
  const [oscal, setOscal] = useState<OscalState | null>(null);
  const [conn, setConn] = useState<OscalConn>("connecting");
  const mounted = useRef(true);

  const poll = useCallback(async () => {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
      const res = await fetch(OSCAL_URL, { signal: ctrl.signal });
      clearTimeout(t);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as OscalState;
      if (!mounted.current) return;
      setOscal(json);
      setConn("live");
    } catch {
      if (!mounted.current) return;
      setOscal((prev) => {
        if (prev) {
          setConn("stale");
          return prev;
        }
        setConn("mock");
        return MOCK_OSCAL;
      });
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

  return { oscal, conn, refetch: poll };
}

/* ---------- realistic offline fixture matching /api/oscal ---------- */
const MOCK_OSCAL: OscalState = {
  standard: "NIST OSCAL 1.1.3 · assessment-results",
  framework: "NIST SP 800-53 rev5",
  title: "THESEUS Runtime Decision Record — OSCAL Assessment Results",
  record_verified: true,
  verify_message:
    "PASS — 56 leaves, head 3752f0946831…, merkle a1638c3edfe7…, 56 Ed25519 sigs OK, 56 in-toto/DSSE attestations OK",
  merkle_root: "a1638c3edfe77c63ad08e9a6278976c3f83ee71ebd5b67b98ddbf02a568b4330",
  chain_head: "3752f0946831767ec212ec562b531d93f4e02267908737d29ab1634826f48a53",
  leaf_count: 56,
  signed_leaves: "56/56",
  attested_leaves: "56/56",
  accreditation_status: "EVIDENCE_LOGGED",
  n_observations: 56,
  controls: [
    { control: "AU-2", title: "Audit Events", state: "satisfied", remark: "sealed audit events · signed + attested · verify PASS" },
    { control: "AU-9", title: "Protection of Audit Information", state: "satisfied", remark: "SHA-256 chain + Ed25519 + in-toto/DSSE · tamper-evident · verify PASS" },
    { control: "CA-7", title: "Continuous Monitoring", state: "satisfied", remark: "Pattern-of-Life surveillance sealed · signed + attested · verify PASS" },
    { control: "CM-3", title: "Configuration Change Control", state: "satisfied", remark: "model promotions sealed + versioned · signed + attested · verify PASS" },
  ],
  controls_satisfied: 4,
  controls_total: 4,
};
