import { useMemo } from "react";
import type { FleetState } from "../../lib/types";
import type { FleetConn } from "../../hooks/useFleetState";
import { FleetStage } from "./FleetStage";
import { ProvenanceGatePanel } from "./ProvenanceGatePanel";
import { EvalGatePanel } from "./EvalGatePanel";
import { AccreditationPanel } from "./AccreditationPanel";
import { MlflowPanel } from "./MlflowPanel";

interface FleetFlywheelProps {
  fleet: FleetState;
  conn: FleetConn;
}

/**
 * The fleet-learning flywheel — the beat that changes the category.
 *
 * Layout: a wide animated stage (ships → fleet brain → push-back) over a row of
 * three instrument panels that make the gates legible:
 *   · PROVENANCE GATE — the poisoned delta REJECTED (red / denied)
 *   · EVAL GATE       — incumbent_rmse → merged_rmse, the measured improvement
 *   · ACCREDITATION   — Ed25519 / in-toto-DSSE → NIST OSCAL · cATO-for-AI
 *
 * Framed everywhere as: human-authorized · eval-gated · provenance-attested.
 * NEVER "the fleet updates itself".
 */
export function FleetFlywheel({ fleet, conn }: FleetFlywheelProps) {
  const accepted = useMemo(
    () => fleet.ships.filter((s) => s.id),
    [fleet.ships],
  );

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        display: "grid",
        // header (auto) · the flywheel graphic gets the flexible space (1fr) · the instrument
        // panels are CAPPED (so a tall panel like the 9-model registry can't crush the graphic).
        gridTemplateRows: "auto minmax(0, 1fr) minmax(150px, 34vh)",
        background: "var(--base)",
      }}
    >
      {/* doctrine strip */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "11px 20px",
          borderBottom: "1px solid var(--hair-lit)",
          background: "var(--panel)",
        }}
      >
        <span className="eyebrow" style={{ fontSize: 9.5 }}>
          Fleet-Learning Flywheel
        </span>
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-dim)", letterSpacing: "0.02em" }}>
          each hull learns locally under DDIL · syncs <span style={{ color: "var(--amber)" }}>signed model deltas</span>, never raw data
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 9 }}>
          {["HUMAN-AUTHORIZED", "EVAL-GATED", "PROVENANCE-ATTESTED"].map((t) => (
            <span
              key={t}
              className="mono"
              style={{
                fontSize: 9,
                letterSpacing: "0.12em",
                color: "var(--amber)",
                border: "1px solid var(--amber-dim)",
                padding: "3px 9px",
              }}
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* the animated stage */}
      <div style={{ position: "relative", minHeight: 0 }}>
        <FleetStage fleet={fleet} acceptedShips={accepted} conn={conn} />
      </div>

      {/* the instrument panels — gates + the live model registry */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr 1fr",
          borderTop: "1px solid var(--hair-lit)",
          background: "var(--panel)",
          minHeight: 0,
          overflow: "hidden",
        }}
      >
        {/* each panel scrolls inside the capped row so none can grow the strip */}
        <div style={{ minHeight: 0, overflow: "auto" }}>
          <ProvenanceGatePanel rejected={fleet.rejected} accepted={fleet.merge?.accepted_ships ?? []} />
        </div>
        <div style={{ minHeight: 0, overflow: "auto" }}>
          <EvalGatePanel merge={fleet.merge} pass={fleet.eval_gate_pass} />
        </div>
        <div style={{ minHeight: 0, overflow: "auto" }}>
          <AccreditationPanel record={fleet.record} />
        </div>
        <div style={{ minHeight: 0, overflow: "auto", borderLeft: "1px solid var(--hair-lit)" }}>
          <MlflowPanel />
        </div>
      </div>
    </div>
  );
}
