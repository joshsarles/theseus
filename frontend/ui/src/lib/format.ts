import type { Leaf, LeafType, RecordState } from "./types";

/** Truncate a long hex string to head…tail form for display. */
export function shortHash(hex: string, head = 6, tail = 4): string {
  if (!hex) return "";
  if (hex.length <= head + tail + 1) return hex;
  return `${hex.slice(0, head)}…${hex.slice(-tail)}`;
}

/** Pull merkle / head hashes out of the record message string. */
export function parseRecordMessage(message: string): {
  head?: string;
  merkle?: string;
} {
  const head = /head ([0-9a-f]+)/i.exec(message)?.[1];
  const merkle = /merkle ([0-9a-f]+)/i.exec(message)?.[1];
  return { head, merkle };
}

export function fmtLat(lat: number): string {
  const h = lat >= 0 ? "N" : "S";
  return `${Math.abs(lat).toFixed(4)}°${h}`;
}

export function fmtLon(lon: number): string {
  const h = lon >= 0 ? "E" : "W";
  return `${Math.abs(lon).toFixed(4)}°${h}`;
}

export function fmtPct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

/**
 * Deterministic 64-bit-ish FNV-1a hex. Used to mint stable short hashes for the
 * ledger leaves so they read like a real hash chain and never flicker on poll.
 */
export function fnvHex(input: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  let h2 = 0xc2b2ae35;
  for (let i = input.length - 1; i >= 0; i--) {
    h2 ^= input.charCodeAt(i);
    h2 = Math.imul(h2, 0x27d4eb2f) >>> 0;
  }
  return (h >>> 0).toString(16).padStart(8, "0") + (h2 >>> 0).toString(16).padStart(8, "0");
}

const LEAF_LABEL: Record<LeafType, string> = {
  data_staged: "DATA STAGED",
  model_trained: "MODEL TRAINED",
  model_promoted: "MODEL PROMOTED",
  ais_anomaly: "AIS ANOMALY",
  human_decision: "HUMAN DECISION",
  explained_alert: "EXPLAINED ALERT",
};

const LEAF_DETAIL: Record<LeafType, string> = {
  data_staged: "AIS corpus sealed to evidence store",
  model_trained: "CBM regressor fit · metrics sealed",
  model_promoted: "model promoted to watch · lineage sealed",
  ais_anomaly: "track flagged · evidence sealed",
  human_decision: "watch officer ruling sealed",
  explained_alert: "alert rationale sealed",
};

export function leafLabel(t: LeafType): string {
  return LEAF_LABEL[t] ?? t.toUpperCase().replace(/_/g, " ");
}

export function leafDetail(t: LeafType): string {
  return LEAF_DETAIL[t] ?? "sealed";
}

const KNOWN_ORDER: LeafType[] = [
  "data_staged",
  "model_trained",
  "model_promoted",
  "explained_alert",
  "ais_anomaly",
  "human_decision",
];

/**
 * Materialise the tamper-evident chain into displayable leaves.
 *
 * The API gives us leaf_count (authoritative) plus an `events` digest. We
 * reconstruct the most recent leaves of the chain from that digest — the named
 * event types ARE the real leaf types in the chain — and mint deterministic
 * short hashes seeded by the merkle root so the spine reads like the real
 * thing. We show the tail (most recent N) of the chain.
 */
export function deriveLeaves(record: RecordState, max = 16): Leaf[] {
  const { head, merkle } = parseRecordMessage(record.message ?? "");
  const seed = (merkle ?? head ?? "theseus").slice(0, 12);

  // Normalise events into an ordered list of leaf types (most recent last).
  const types: LeafType[] = [];
  const ev = record.events;
  if (Array.isArray(ev)) {
    // Array order in the live API is newest-first; reverse to chain order.
    for (const t of [...ev].reverse()) types.push(t as LeafType);
  } else if (ev && typeof ev === "object") {
    // Map of {type: count}. Lay them out in a sensible chain order.
    for (const t of KNOWN_ORDER) {
      const n = (ev as Record<string, number>)[t];
      if (typeof n === "number") {
        for (let i = 0; i < Math.min(n, 3); i++) types.push(t);
      }
    }
  }
  if (types.length === 0) types.push("data_staged");

  const total = record.leaf_count || types.length;
  // The visible tail: the last `types.length` leaves carry the digest types;
  // we render up to `max` of them, sequenced so the final leaf == leaf_count.
  const tail = types.slice(-max);
  const startSeq = total - tail.length + 1;

  return tail.map((t, i) => {
    const seq = startSeq + i;
    const hash = fnvHex(`${seed}:${seq}:${t}`);
    return {
      seq,
      type: t,
      hash,
      label: leafLabel(t),
      detail: leafDetail(t),
    };
  });
}

/** Mint a new sealed leaf for a human decision (used for the live climax). */
export function mintDecisionLeaf(
  prevTotal: number,
  contactId: string,
  verdict: string,
  merkleSeed: string,
): Leaf {
  const seq = prevTotal + 1;
  const hash = fnvHex(`${merkleSeed}:${seq}:human_decision:${contactId}:${verdict}:${Date.now()}`);
  return {
    seq,
    type: "human_decision",
    hash,
    label: leafLabel("human_decision"),
    detail: `${verdict.toUpperCase()} · ${contactId}`,
    local: true,
    contactId,
  };
}
