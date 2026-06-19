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
  /** null until a CBM model is promoted (build_state returns null before then) */
  machinery: Machinery | null;
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

/* ====================================================================== */
/*  FLEET-LEARNING FLYWHEEL — GET /api/fleet                              */
/*  human-authorized · eval-gated · provenance-attested                  */
/* ====================================================================== */

/** A sister hull that trained locally and synced a signed delta. */
export interface FleetShip {
  id: string | null;
  n_samples: number | null;
  local_train_rmse: number | null;
  status: string;
}

/** A delta the provenance gate refused (poisoned / unattested). */
export interface FleetRejection {
  id: string | null;
  reason: string | null;
}

/** The eval-gated FedAvg merge: incumbent → merged on a held-out set. */
export interface FleetMerge {
  accepted_ships: string[];
  fedavg_weights: number[];
  incumbent_rmse: number;
  merged_rmse: number;
  rmse_delta: number;
  held_out_n: number;
}

export interface FleetRecord {
  verify_ok: boolean;
  message: string;
  leaf_count: number;
}

export interface FleetState {
  posture: string;
  ships: FleetShip[];
  rejected: FleetRejection[];
  merge: FleetMerge | null;
  eval_gate_pass: boolean | null;
  record: FleetRecord;
}

/* ====================================================================== */
/*  MLFLOW REGISTRY — GET /api/mlflow                                     */
/*  registry status + result metrics, proxied from the Node-3 MLflow      */
/*  server so the UI can render them (the UI can't reach MLflow directly). */
/* ====================================================================== */

/** A registered model + its @production alias + that version's eval results. */
export interface MlflowModel {
  name: string;
  production_version: string | null;
  version_count?: number | null;
  run_id?: string;
  /** result metrics logged on the @production run: precision_at_k, f1, false_alarm_rate, … */
  metrics: Record<string, number>;
  params?: Record<string, string>;
}

/** A recent training/registration run with its logged metrics. */
export interface MlflowRun {
  run_name: string;
  experiment: string;
  status: string | null;
  metrics: Record<string, number>;
}

export interface MlflowState {
  connected: boolean;
  tracking_uri: string;
  models: MlflowModel[];
  experiments?: { id: string; name: string }[];
  runs: MlflowRun[];
  error?: string;
}

export type SceneMode = "operations" | "fleet";
