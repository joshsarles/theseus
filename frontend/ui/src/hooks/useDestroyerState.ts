import { useCallback, useEffect, useRef, useState } from "react";
import type { DestroyerState } from "../lib/types";

const API_BASE =
  (import.meta.env.VITE_THESEUS_API as string | undefined) ??
  "http://localhost:8501";

export const DESTROYER_URL = `${API_BASE}/api/destroyer`;

const POLL_MS = 5000;
const FETCH_TIMEOUT_MS = 6000;

export type DestroyerConn = "connecting" | "live" | "stale" | "mock";

interface UseDestroyerState {
  destroyer: DestroyerState | null;
  conn: DestroyerConn;
  refetch: () => void;
}

/**
 * Polls GET /api/destroyer — the strike-group picture (multiple hulls, each a
 * city of 8 subsystems, syncing signed deltas to the shore fleet brain). Same
 * honesty contract as useShipState / useFleetState: a real 200 is "live";
 * anything else falls to the offline fixture and is surfaced (never silently
 * presented as live, see SimFeedBanner). The fixture is believable so the strike
 * group always reads well even before the API endpoint is wired.
 */
export function useDestroyerState(): UseDestroyerState {
  const [destroyer, setDestroyer] = useState<DestroyerState | null>(null);
  const [conn, setConn] = useState<DestroyerConn>("connecting");
  const mounted = useRef(true);

  const poll = useCallback(async () => {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
      const res = await fetch(DESTROYER_URL, { signal: ctrl.signal });
      clearTimeout(t);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as DestroyerState;
      if (!mounted.current) return;
      setDestroyer(json);
      setConn("live");
    } catch {
      if (!mounted.current) return;
      setDestroyer((prev) => {
        if (prev) {
          setConn("stale");
          return prev;
        }
        setConn("mock");
        return MOCK_DESTROYER;
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

  return { destroyer, conn, refetch: poll };
}

/* ---------- the 8 subsystems every hull is instrumented for ---------- */
import type { DestroyerSubsystem, Severity } from "../lib/types";

function sub(
  key: string,
  label: string,
  live: boolean,
  severity: Severity,
  detail: string,
): DestroyerSubsystem {
  return { key, label, live, severity, detail };
}

/** USS Theseus — the LIVE flagship: machinery + contacts wired, one critical. */
const THESEUS_SUBS: DestroyerSubsystem[] = [
  sub("propulsion", "PROPULSION", true, "nominal", "gas-turbine decay v1 · RMSE 0.003823"),
  sub("machinery", "MACHINERY · HM&E", true, "nominal", "condition-based maintenance · nominal"),
  sub("power", "POWER & ELECTRICAL", true, "warning", "bus-2 ripple trending · watch"),
  sub("contacts", "CONTACTS · TACTICAL", true, "critical", "50 tracks · 2 possible spoof/jump"),
  sub("navigation", "NAVIGATION", true, "nominal", "GNSS + INS cross-check nominal"),
  sub("damage_control", "DAMAGE CONTROL", true, "nominal", "zones sealed · no casualties"),
  sub("comms", "COMMS / C5I", true, "nominal", "SATCOM up · DDIL link nominal"),
  sub("readiness", "READINESS", true, "warning", "MC rollup degraded by contacts hold"),
];

/** A sister hull, mostly nominal with a single watch item. */
function sisterSubs(seed: number): DestroyerSubsystem[] {
  const warnAt = seed % 8;
  const critAt = seed % 3 === 0 ? (seed * 3) % 8 : -1;
  const base = [
    ["propulsion", "PROPULSION", "gas-turbine decay nominal"],
    ["machinery", "MACHINERY · HM&E", "CBM nominal · no exceedance"],
    ["power", "POWER & ELECTRICAL", "load balanced · nominal"],
    ["contacts", "CONTACTS · TACTICAL", "track picture clean"],
    ["navigation", "NAVIGATION", "GNSS + INS nominal"],
    ["damage_control", "DAMAGE CONTROL", "zones sealed"],
    ["comms", "COMMS / C5I", "DDIL link nominal"],
    ["readiness", "READINESS", "mission-capable"],
  ] as const;
  return base.map(([key, label, detail], i) => {
    let sev: Severity = "nominal";
    if (i === critAt) sev = "critical";
    else if (i === warnAt) sev = "warning";
    return sub(
      key,
      label,
      true,
      sev,
      sev === "critical" ? `${detail} · exceedance flagged` : sev === "warning" ? `${detail} · watch` : detail,
    );
  });
}

/* ---------- realistic offline fixture matching /api/destroyer ---------- */
const MOCK_DESTROYER: DestroyerState = {
  posture:
    "strike group · each hull a self-contained city · fleet learning under DDIL · human-authorized",
  destroyers: [
    {
      hull: "DDG-118",
      name: "USS THESEUS",
      flagship: true,
      posture: "decision-support · human-in-command · SWAN-side",
      station: { x: 0.5, y: 0.32 },
      subsystems: THESEUS_SUBS,
      model: { version: 7, local_rmse: 0.029348, n_samples: 300 },
      sync: { delta: -0.001796, signed: true, attested: true, status: "merged" },
    },
    {
      hull: "DDG-119",
      name: "USS DAEDALUS",
      flagship: false,
      posture: "decision-support · human-in-command",
      station: { x: 0.2, y: 0.66 },
      subsystems: sisterSubs(5),
      model: { version: 6, local_rmse: 0.027021, n_samples: 300 },
      sync: { delta: -0.001204, signed: true, attested: true, status: "merged" },
    },
    {
      hull: "DDG-120",
      name: "USS ARIADNE",
      flagship: false,
      posture: "decision-support · human-in-command",
      station: { x: 0.8, y: 0.66 },
      subsystems: sisterSubs(3),
      model: { version: 6, local_rmse: 0.031902, n_samples: 240 },
      sync: { delta: -0.000981, signed: true, attested: true, status: "pending" },
    },
  ],
  shore: {
    node: "NODE-3",
    label: "SHORE FLEET BRAIN",
    accepted_hulls: ["DDG-118", "DDG-119"],
    fedavg_weights: [300, 300],
    incumbent_rmse: 0.031816,
    merged_rmse: 0.030019,
    rmse_delta: -0.001796,
    held_out_n: 150,
    eval_gate_pass: true,
  },
  rejected: [
    {
      hull: "UNREG-04",
      keyid: "POISON_NODE",
      reason: "unknown ship keyid='POISON_NODE' (no .pub in trust registry) — forged delta",
    },
  ],
  record: {
    verify_ok: true,
    message:
      "PASS — 6 leaves, head 7b679f954f29…, merkle 20274cb21ec1…, 6 Ed25519 sigs OK, 6 in-toto/DSSE attestations OK",
    leaf_count: 6,
  },
};
