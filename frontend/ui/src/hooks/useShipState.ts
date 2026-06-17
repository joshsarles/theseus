import { useCallback, useEffect, useRef, useState } from "react";
import type { ShipState } from "../lib/types";

const API_URL =
  (import.meta.env.VITE_THESEUS_API as string | undefined) ??
  "http://localhost:8501/api/state";

const POLL_MS = 4000;

export type ConnState = "connecting" | "live" | "stale" | "mock";

interface UseShipState {
  state: ShipState | null;
  conn: ConnState;
  lastUpdated: number | null;
  refetch: () => void;
}

/** Polls the THESEUS API every 4s; falls back to a realistic mock if the API is unreachable. */
export function useShipState(): UseShipState {
  const [state, setState] = useState<ShipState | null>(null);
  const [conn, setConn] = useState<ConnState>("connecting");
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const failures = useRef(0);
  const mounted = useRef(true);

  const poll = useCallback(async () => {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 3500);
      const res = await fetch(API_URL, { signal: ctrl.signal });
      clearTimeout(t);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as ShipState;
      if (!mounted.current) return;
      failures.current = 0;
      setState(json);
      setConn("live");
      setLastUpdated(Date.now());
    } catch {
      if (!mounted.current) return;
      failures.current += 1;
      // After repeated failures with no data, surface mock so the console is never empty.
      setState((prev) => {
        if (prev) {
          setConn("stale");
          return prev;
        }
        setConn("mock");
        return MOCK_STATE;
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

  return { state, conn, lastUpdated, refetch: poll };
}

/* ---------- realistic offline mock matching the live contract ---------- */
const MOCK_STATE: ShipState = {
  ship: "THESEUS",
  posture: "decision-support · human-in-command · SWAN-side",
  systems: [
    { key: "propulsion", label: "PROPULSION / ENGINEERING", live: true, severity: "nominal", detail: "gas-turbine decay model v1 · RMSE 0.003823" },
    { key: "machinery", label: "MACHINERY / HM&E", live: true, severity: "nominal", detail: "condition-based maintenance" },
    { key: "contacts", label: "CONTACTS / TACTICAL", live: true, severity: "critical", detail: "100 track(s) flagged · 3 possible spoof/jump" },
    { key: "power", label: "POWER & ELECTRICAL", live: false, severity: "standby", detail: "organ instrumented · model pending" },
    { key: "navigation", label: "NAVIGATION", live: false, severity: "standby", detail: "organ instrumented · model pending" },
    { key: "damage_control", label: "DAMAGE CONTROL", live: false, severity: "standby", detail: "organ instrumented · model pending" },
    { key: "readiness", label: "READINESS", live: false, severity: "standby", detail: "mission-capability rollup pending" },
  ],
  machinery: { model: "theseus-cbm", version: 1, rmse: 0.003823, framework: "sklearn", status: "nominal", promotions: 1 },
  contacts: [
    { id: "position_jump:360000000", mmsi: "360000000", type: "position_jump", vessel_class: "other", confidence: 0.75, why: "implausible jump: 27370kn implied vs 0kn reported (494.2nm/1min)", recommended_action: "possible GNSS spoofing or identity swap — verify", lat: 38.54006, lon: -90.25016, status: "pending" },
    { id: "dark_gap:367463060", mmsi: "367463060", type: "dark_gap", vessel_class: "passenger", confidence: 0.65, why: "AIS gap 50 min while underway (9kn) — possible AIS-off", recommended_action: "cue another sensor; flag possible dark-vessel behavior", lat: 47.32633, lon: -122.50914, status: "pending" },
    { id: "overspeed:367681730", mmsi: "367681730", type: "overspeed", vessel_class: "other", confidence: 0.6, why: "SOG over 1.5x in-situ other envelope (19kn) for 3 consecutive fixes (max 30kn)", recommended_action: "verify track quality; possible anomalous transit", lat: 40.70144, lon: -74.01762, status: "pending" },
    { id: "loiter:367767310", mmsi: "367767310", type: "loiter", vessel_class: "passenger", confidence: 0.7, why: "transited then loitered: 74/97 fixes <0.5kn over 2.2h (peak 7kn)", recommended_action: "verify intent; flag for watch — possible surveillance/rendezvous", lat: 27.84003, lon: -97.0697, status: "pending" },
    { id: "loiter:366952790", mmsi: "366952790", type: "loiter", vessel_class: "passenger", confidence: 0.7, why: "transited then loitered: 90/109 fixes <0.5kn over 2.2h (peak 18kn)", recommended_action: "verify intent; flag for watch — possible surveillance/rendezvous", lat: 40.65335, lon: -74.05382, status: "pending" },
  ],
  human_in_command: { pending: 100, note: "Theseus recommends; the watch officer decides. Nothing is actioned automatically." },
  record: {
    verify_ok: true,
    first_bad_leaf: null,
    message: "PASS — 111 leaves, head 8029acf240be…, merkle 7ebecc250ff2…",
    leaf_count: 111,
    events: { ais_anomaly: 100, data_staged: 1, explained_alert: 6, model_promoted: 1, model_trained: 3 },
  },
};
