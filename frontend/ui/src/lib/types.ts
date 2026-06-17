export type Severity = "nominal" | "warning" | "critical" | "standby";

export type ContactType = "loiter" | "dark_gap" | "position_jump" | "overspeed";

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
  promotions: number;
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
  status: string;
}

export interface HumanInCommand {
  pending: number;
  note: string;
}

export interface RecordState {
  verify_ok: boolean;
  first_bad_leaf: string | null;
  message: string;
  leaf_count: number;
  events: Record<string, number>;
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
