import { useCallback, useEffect, useRef, useState } from "react";
import type { ShipState } from "../lib/types";

const API_BASE =
  (import.meta.env.VITE_THESEUS_API as string | undefined) ??
  "http://localhost:8501";

export const STATE_URL = `${API_BASE}/api/state`;
export const DECISION_URL = `${API_BASE}/api/decision`;

const POLL_MS = 4000;

export type ConnState = "connecting" | "live" | "stale" | "mock";

interface UseShipState {
  state: ShipState | null;
  conn: ConnState;
  lastUpdated: number | null;
  refetch: () => void;
}

/** Polls the THESEUS API every 4s; falls back to a realistic mock if unreachable. */
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
      const res = await fetch(STATE_URL, { signal: ctrl.signal });
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
      setState((prev) => {
        if (prev) {
          setConn("stale");
          return prev;
        }
        setConn("mock");
        return MOCK_STATE;
      });
      setLastUpdated((p) => p ?? Date.now());
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
    { key: "contacts", label: "CONTACTS / TACTICAL", live: true, severity: "critical", detail: "50 track(s) flagged · 2 possible spoof/jump" },
    { key: "power", label: "POWER & ELECTRICAL", live: false, severity: "standby", detail: "organ instrumented · model pending" },
    { key: "navigation", label: "NAVIGATION", live: false, severity: "standby", detail: "organ instrumented · model pending" },
    { key: "damage_control", label: "DAMAGE CONTROL", live: false, severity: "standby", detail: "organ instrumented · model pending" },
    { key: "readiness", label: "READINESS", live: false, severity: "standby", detail: "mission-capability rollup pending" },
  ],
  machinery: { model: "theseus-cbm", version: 1, rmse: 0.003823, framework: "sklearn", status: "nominal", promotions: 1 },
  contacts: [
    { id: "position_jump:360000000", mmsi: "360000000", type: "position_jump", vessel_class: "other", confidence: 0.75, why: "implausible jump: 27370kn implied vs 0kn reported (494.2nm/1min)", recommended_action: "possible GNSS spoofing or identity swap — verify", lat: 38.54006, lon: -90.25016, status: "pending" },
    { id: "position_jump:367075320", mmsi: "367075320", type: "position_jump", vessel_class: "other", confidence: 0.75, why: "implausible jump: 2655kn implied vs 0kn reported (51.6nm/1min)", recommended_action: "possible GNSS spoofing or identity swap — verify", lat: 30.01885, lon: -93.74823, status: "pending" },
    { id: "dark_gap:367463060", mmsi: "367463060", type: "dark_gap", vessel_class: "passenger", confidence: 0.65, why: "AIS gap 50 min while underway (9kn) — possible AIS-off", recommended_action: "cue another sensor; flag possible dark-vessel behavior", lat: 47.32633, lon: -122.50914, status: "pending" },
    { id: "overspeed:366968740", mmsi: "366968740", type: "overspeed", vessel_class: "fishing", confidence: 0.6, why: "SOG over 1.5x in-situ fishing envelope (12kn) for 20 consecutive fixes (max 25kn)", recommended_action: "verify track quality; possible anomalous transit", lat: 29.28235, lon: -89.35734, status: "pending" },
    { id: "loiter:368171390", mmsi: "368171390", type: "loiter", vessel_class: "other", confidence: 0.7, why: "transited then loitered: 86/114 fixes <0.5kn over 2.3h (peak 9kn)", recommended_action: "verify intent; flag for watch — possible surveillance/rendezvous", lat: 33.72501, lon: -118.22, status: "pending" },
    { id: "loiter:367780660", mmsi: "367780660", type: "loiter", vessel_class: "other", confidence: 0.7, why: "transited then loitered: 79/105 fixes <0.5kn over 2.3h (peak 6kn)", recommended_action: "verify intent; flag for watch — possible surveillance/rendezvous", lat: 29.7649, lon: -95.10813, status: "pending" },
    { id: "loiter:368286050", mmsi: "368286050", type: "loiter", vessel_class: "other", confidence: 0.7, why: "transited then loitered: 48/59 fixes <0.5kn over 1.2h (peak 14kn)", recommended_action: "verify intent; flag for watch — possible surveillance/rendezvous", lat: 40.71131, lon: -74.04752, status: "pending" },
  ],
  human_in_command: { pending: 50, note: "Theseus recommends; the watch officer decides. Nothing is actioned automatically." },
  record: {
    verify_ok: true,
    first_bad_leaf: null,
    message: "PASS — 54 leaves, head 49b5aad0bc53…, merkle ead78b20eed5…",
    leaf_count: 54,
    events: ["ais_anomaly", "data_staged", "model_promoted", "model_trained"],
  },
};
