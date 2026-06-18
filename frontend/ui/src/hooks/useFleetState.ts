import { useCallback, useEffect, useRef, useState } from "react";
import type { FleetState } from "../lib/types";

const API_BASE =
  (import.meta.env.VITE_THESEUS_API as string | undefined) ??
  "http://localhost:8501";

export const FLEET_URL = `${API_BASE}/api/fleet`;

const POLL_MS = 5000;
const FETCH_TIMEOUT_MS = 6000;

export type FleetConn = "connecting" | "live" | "stale" | "mock";

interface UseFleetState {
  fleet: FleetState | null;
  conn: FleetConn;
  refetch: () => void;
}

/**
 * Polls GET /api/fleet — the fleet-learning flywheel. Same honesty contract as
 * useShipState: a real 200 is "live"; anything else falls to the offline mock
 * and is surfaced (never silently presented as live). The flywheel is sealed in
 * an independent fleet record (fleet/out/fleet_record), so its verify state is
 * reported separately from the one-ship CIC record.
 */
export function useFleetState(): UseFleetState {
  const [fleet, setFleet] = useState<FleetState | null>(null);
  const [conn, setConn] = useState<FleetConn>("connecting");
  const mounted = useRef(true);

  const poll = useCallback(async () => {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
      const res = await fetch(FLEET_URL, { signal: ctrl.signal });
      clearTimeout(t);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as FleetState;
      if (!mounted.current) return;
      setFleet(json);
      setConn("live");
    } catch {
      if (!mounted.current) return;
      setFleet((prev) => {
        if (prev) {
          setConn("stale");
          return prev;
        }
        setConn("mock");
        return MOCK_FLEET;
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

  return { fleet, conn, refetch: poll };
}

/* ---------- realistic offline mock matching the live /api/fleet contract ---------- */
const MOCK_FLEET: FleetState = {
  posture: "fleet learning · human-authorized · eval-gated · provenance-attested",
  ships: [
    { id: "MACHINERY", n_samples: 300, local_train_rmse: 0.029348, status: "merged" },
    { id: "CONTACTS", n_samples: 300, local_train_rmse: 0.027021, status: "merged" },
  ],
  rejected: [
    { id: "POISON_NODE", reason: "unknown ship keyid='POISON_NODE' (no .pub in key_dir)" },
  ],
  merge: {
    accepted_ships: ["MACHINERY", "CONTACTS"],
    fedavg_weights: [300, 300],
    incumbent_rmse: 0.031816,
    merged_rmse: 0.030019,
    rmse_delta: -0.001796,
    held_out_n: 150,
  },
  eval_gate_pass: true,
  record: {
    verify_ok: true,
    message:
      "PASS — 4 leaves, head 7b679f954f29…, merkle 20274cb21ec1…, 4 Ed25519 sigs OK, 4 in-toto/DSSE attestations OK",
    leaf_count: 4,
  },
};
