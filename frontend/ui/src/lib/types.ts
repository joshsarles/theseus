export type Severity = "nominal" | "warning" | "critical" | "standby";

export type ContactType = "loiter" | "dark_gap" | "position_jump" | "overspeed";

export type LeafType =
  | "data_staged"
  | "model_trained"
  | "model_promoted"
  | "ais_anomaly"
  | "human_decision"
  | "explained_alert";

export interface ShipSystem {
  key: string;
  label: string;
  live: boolean;
  severity: Severity;
  detail: string;
}

export interface Machinery {
  model: string;
  version: number;
  rmse: number;
  framework: string;
  status?: string;
  promotions?: number;
}

export interface Contact {
  id: string;
  mmsi: string;
  type: ContactType;
  vessel_class: string;
  confidence: number;
  why: string;
  recommended_action: string;
  lat: number | null;
  lon: number | null;
  status?: string;
}

export interface HumanInCommand {
  pending: number;
  note?: string;
}

/**
 * The live API delivers `record.events` either as an array of leaf-type
 * strings or as a {type: count} map. The union keeps the reader honest about
 * both shapes; deriveLeaves() normalises them.
 */
export interface RecordState {
  verify_ok: boolean;
  first_bad_leaf?: string | null;
  message: string;
  leaf_count: number;
  events: string[] | Record<string, number>;
}

export interface ShipState {
  ship: string;
  posture: string;
  systems: ShipSystem[];
  machinery: Machinery;
  contacts: Contact[];
  human_in_command: HumanInCommand;
  record: RecordState;
}

/** A single sealed entry materialised for the ledger spine. */
export interface Leaf {
  seq: number;
  type: LeafType;
  hash: string;
  label: string;
  detail: string;
  /** locally-sealed decisions are flagged so the climax reads as live */
  local?: boolean;
  contactId?: string;
}

export type Verdict = "accepted" | "overridden";
