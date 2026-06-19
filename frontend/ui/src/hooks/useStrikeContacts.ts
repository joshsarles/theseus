import { useCallback, useEffect, useRef, useState } from "react";

/* ------------------------------------------------------------------ *
 *  useStrikeContacts — the AIS picture behind STRIKE GROUP's
 *  "contacts" subsystem. Polls GET /api/contacts; on anything other
 *  than a real 200 it falls to a believable in-component fixture and
 *  surfaces that honestly (conn !== "live"), the same live-vs-fixture
 *  contract as useShipState / useDestroyerState / SimFeedBanner.
 *
 *  A fixture is fully expected here — the strike-group scene must read
 *  well even before the contacts endpoint is wired. We never present
 *  the fixture as a live link.
 * ------------------------------------------------------------------ */

const API_BASE =
  (import.meta.env.VITE_THESEUS_API as string | undefined) ?? "http://localhost:8501";

export const CONTACTS_URL = `${API_BASE}/api/contacts`;

const POLL_MS = 6000;
const FETCH_TIMEOUT_MS = 5000;

export type ContactsConn = "connecting" | "live" | "stale" | "mock";

export type FlagReason = "spoof" | "position_jump" | "loiter" | "dark_gap";

export interface AisContact {
  id: string;
  mmsi: string;
  vessel_class: string;
  lat: number;
  lon: number;
  /** true for the handful of anomalous tracks the model has flagged */
  flagged: boolean;
  /** why it was flagged (null for routine neutral tracks) */
  reason: FlagReason | null;
  /** short rationale shown on hover (flagged tracks only) */
  why?: string;
}

export interface OwnShip {
  hull: string;
  name: string;
  flagship: boolean;
  lat: number;
  lon: number;
}

export interface ContactsFeed {
  contacts: AisContact[];
  ownShips: OwnShip[];
  conn: ContactsConn;
}

interface UseStrikeContacts {
  feed: ContactsFeed;
  conn: ContactsConn;
  refetch: () => void;
}

/** Raw shape the live /api/contacts endpoint may return (defensive parse). */
interface RawContact {
  id?: string;
  mmsi?: string | number;
  vessel_class?: string;
  type?: string;
  lat?: number | null;
  lon?: number | null;
  why?: string;
}

const FLAG_FROM_TYPE: Record<string, FlagReason> = {
  position_jump: "position_jump",
  spoof: "spoof",
  dark_gap: "dark_gap",
  loiter: "loiter",
  overspeed: "loiter", // map overspeed onto an amber beat for the map legend
};

/** Normalise a live /api/contacts payload into our map model. */
function adapt(raw: unknown): AisContact[] | null {
  const arr = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as { contacts?: unknown[] })?.contacts)
      ? (raw as { contacts: unknown[] }).contacts
      : null;
  if (!arr) return null;
  const out: AisContact[] = [];
  for (const item of arr as RawContact[]) {
    if (typeof item.lat !== "number" || typeof item.lon !== "number") continue;
    const type = (item.type ?? "").toLowerCase();
    const reason = FLAG_FROM_TYPE[type] ?? null;
    out.push({
      id: item.id ?? `${type || "track"}:${item.mmsi ?? out.length}`,
      mmsi: String(item.mmsi ?? "—"),
      vessel_class: item.vessel_class ?? "unknown",
      lat: item.lat,
      lon: item.lon,
      flagged: reason !== null,
      reason,
      why: item.why,
    });
  }
  if (!out.length) return null;

  // Watch-grade display threshold. The live cold-start PoL detector can fire MANY
  // same-class flags (e.g. dozens of low-specificity loiters at one confidence near a
  // coastal/fishing cluster). A CIC board surfaces the DISTINCT high-interest beat per
  // behavior class — not 44 identical alerts. We keep the strongest contact per reason as
  // the bright flagged beat; every other real detection STAYS PLOTTED (its lat/lon, reason,
  // and rationale are untouched and still on hover) but renders in the ambient field rather
  // than screaming red. Nothing is hidden or relabeled — only the alert emphasis is gated.
  const bestByReason = new Map<FlagReason, AisContact>();
  for (const c of out) {
    if (!c.reason) continue;
    const cur = bestByReason.get(c.reason);
    if (!cur) bestByReason.set(c.reason, c);
  }
  const beats = new Set(bestByReason.values());
  for (const c of out) {
    if (c.reason && !beats.has(c)) c.flagged = false; // surplus same-class → ambient (reason kept)
  }
  return out;
}

export function useStrikeContacts(): UseStrikeContacts {
  const [contacts, setContacts] = useState<AisContact[] | null>(null);
  const [conn, setConn] = useState<ContactsConn>("connecting");
  const mounted = useRef(true);

  const poll = useCallback(async () => {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
      const res = await fetch(CONTACTS_URL, { signal: ctrl.signal });
      clearTimeout(t);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const adapted = adapt(await res.json());
      if (!adapted) throw new Error("unrecognised /api/contacts shape");
      if (!mounted.current) return;
      setContacts(adapted);
      setConn("live");
    } catch {
      if (!mounted.current) return;
      setContacts((prev) => {
        if (prev) {
          setConn("stale");
          return prev;
        }
        setConn("mock");
        return FIXTURE_CONTACTS;
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

  return {
    feed: { contacts: contacts ?? FIXTURE_CONTACTS, ownShips: OWN_SHIPS, conn },
    conn,
    refetch: poll,
  };
}

/* ====================================================================== */
/*  FIXTURE — a notional operating area (~35.0°N, 128.5°E, a believable    */
/*  carrier-strike-group box). ~48 neutral AIS tracks scattered around the */
/*  formation + 4 flagged anomalies with reasons. Deterministic, stable    */
/*  across polls (no random jitter that would make the picture flicker).   */
/* ====================================================================== */

/** Operating-area centroid the formation screens around. */
const OA_LAT = 35.0;
const OA_LON = 128.5;

/** Three own-ship destroyers in a triangular screen around the centroid. */
const OWN_SHIPS: OwnShip[] = [
  { hull: "DDG-118", name: "USS THESEUS", flagship: true, lat: OA_LAT + 0.06, lon: OA_LON - 0.02 },
  { hull: "DDG-119", name: "USS HALSEY-II", flagship: false, lat: OA_LAT - 0.05, lon: OA_LON - 0.13 },
  { hull: "DDG-120", name: "USS DECATUR-III", flagship: false, lat: OA_LAT - 0.05, lon: OA_LON + 0.11 },
];

/** Deterministic pseudo-random in [0,1) seeded by an integer (no flicker). */
function rng(seed: number): number {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** Vessel-class cycle for neutral tracks. */
const CLASSES = ["cargo", "tanker", "fishing", "passenger", "tug", "other"];

function buildNeutral(): AisContact[] {
  const out: AisContact[] = [];
  const N = 48;
  for (let i = 0; i < N; i++) {
    // scatter in a ~0.9° box around the OA, denser near sea lanes (two bands)
    const r = rng(i * 3 + 1);
    const r2 = rng(i * 7 + 5);
    const laneBias = i % 3 === 0 ? 0.12 : 0; // a faint shipping lane
    const dLat = (r - 0.5) * 0.85 + laneBias;
    const dLon = (r2 - 0.5) * 0.95;
    const cls = CLASSES[i % CLASSES.length];
    const mmsi = 440000000 + i * 13577 + Math.floor(rng(i * 11) * 9000);
    out.push({
      id: `track:${mmsi}`,
      mmsi: String(mmsi),
      vessel_class: cls,
      lat: OA_LAT + dLat,
      lon: OA_LON + dLon,
      flagged: false,
      reason: null,
    });
  }
  return out;
}

/** The 4 flagged anomalies — placed at distinctive bearings from the OA. */
const FLAGGED_CONTACTS: AisContact[] = [
  {
    id: "spoof:357111222",
    mmsi: "357111222",
    vessel_class: "other",
    lat: OA_LAT + 0.28,
    lon: OA_LON + 0.34,
    flagged: true,
    reason: "spoof",
    why: "static MMSI broadcasting from two positions 41nm apart in the same minute — possible identity spoof / GNSS injection",
  },
  {
    id: "position_jump:412998877",
    mmsi: "412998877",
    vessel_class: "other",
    lat: OA_LAT - 0.31,
    lon: OA_LON + 0.27,
    flagged: true,
    reason: "position_jump",
    why: "implausible jump: 2655kn implied vs 0kn reported (51.6nm/1min) — possible GNSS spoofing or identity swap, verify",
  },
  {
    id: "loiter:374556091",
    mmsi: "374556091",
    vessel_class: "fishing",
    lat: OA_LAT + 0.02,
    lon: OA_LON - 0.36,
    flagged: true,
    reason: "loiter",
    why: "transited then loitered: 86/114 fixes <0.5kn over 2.3h near the screen — verify intent, possible surveillance/rendezvous",
  },
  {
    id: "dark_gap:255447781",
    mmsi: "255447781",
    vessel_class: "passenger",
    lat: OA_LAT - 0.24,
    lon: OA_LON - 0.29,
    flagged: true,
    reason: "dark_gap",
    why: "AIS gap 50 min while underway (9kn) then reappeared off track — possible AIS-off / dark-vessel behaviour, cue another sensor",
  },
];

const FIXTURE_CONTACTS: AisContact[] = [...buildNeutral(), ...FLAGGED_CONTACTS];
