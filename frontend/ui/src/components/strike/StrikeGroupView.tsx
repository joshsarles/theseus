import { useMemo, useState } from "react";
import type { DestroyerState, Severity } from "../../lib/types";
import type { DestroyerConn } from "../../hooks/useDestroyerState";
import { DestroyerCard } from "./DestroyerCard";
import { StrikeContactsMap } from "./StrikeContactsMap";
import { StrikeGroupStage } from "./StrikeGroupStage";

interface StrikeGroupViewProps {
  destroyer: DestroyerState;
  conn: DestroyerConn;
}

/**
 * STRIKE GROUP — the whole vision legible at a glance.
 *
 *   · a doctrine strip framing the picture
 *   · a card row: MULTIPLE destroyers, each a self-contained city of 8 subsystems
 *     lit live by severity (the flagship carries the live 3D twin)
 *   · the animated sync stage: every hull pushes a SIGNED model delta to the
 *     SHORE FLEET BRAIN (Node 3); the poisoned delta is REJECTED at the gate
 *   · a gate readout: provenance gate + eval gate, the measured guarantees
 *
 * Framed throughout: human-authorized · eval-gated · provenance-attested.
 */
export function StrikeGroupView({ destroyer, conn }: StrikeGroupViewProps) {
  const [selected, setSelected] = useState<string>(
    () => destroyer.destroyers.find((d) => d.flagship)?.hull ?? destroyer.destroyers[0]?.hull ?? "",
  );

  const totals = useMemo(() => {
    let critical = 0;
    let warning = 0;
    destroyer.destroyers.forEach((d) =>
      d.subsystems.forEach((s) => {
        if (!s.live) return;
        if (s.severity === "critical") critical += 1;
        else if (s.severity === "warning") warning += 1;
      }),
    );
    return { critical, warning, hulls: destroyer.destroyers.length };
  }, [destroyer]);

  const shore = destroyer.shore;

  // contacts subsystem severity from the flagship (falls back to worst across hulls)
  const contactsSeverity: Severity = useMemo(() => {
    const flagship = destroyer.destroyers.find((d) => d.flagship) ?? destroyer.destroyers[0];
    const c = flagship?.subsystems.find((s) => s.key === "contacts");
    return c?.live ? c.severity : "warning";
  }, [destroyer]);

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        display: "grid",
        gridTemplateRows: "auto auto auto minmax(0, 1fr)",
        background: "var(--base)",
        overflow: "auto",
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
          Strike Group
        </span>
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-dim)", letterSpacing: "0.02em" }}>
          {totals.hulls} hulls · each a <span style={{ color: "var(--amber)" }}>self-contained city</span> of 8 subsystems ·
          syncing <span style={{ color: "var(--amber)" }}>signed model deltas</span> to the shore brain
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 9, alignItems: "center" }}>
          <Pill label="WARNING" value={totals.warning} tone={totals.warning ? "warning" : "muted"} />
          <Pill label="CRITICAL" value={totals.critical} tone={totals.critical ? "critical" : "muted"} />
          {["HUMAN-AUTHORIZED", "EVAL-GATED", "PROVENANCE-ATTESTED"].map((t) => (
            <span
              key={t}
              className="mono"
              style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--amber)", border: "1px solid var(--amber-dim)", padding: "3px 9px" }}
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* card row — one self-contained city per hull */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${destroyer.destroyers.length}, minmax(0, 1fr))`,
          gap: 12,
          padding: 14,
        }}
      >
        {destroyer.destroyers.map((d) => (
          <DestroyerCard
            key={d.hull}
            ship={d}
            conn={conn}
            selected={selected === d.hull}
            onSelect={() => setSelected(d.hull)}
          />
        ))}
      </div>

      {/* tactical contacts map — the "contacts" subsystem made tangible */}
      <div style={{ borderTop: "1px solid var(--hair-lit)", padding: "0 14px 14px" }}>
        <StrikeContactsMap contactsSeverity={contactsSeverity} />
      </div>

      {/* the animated sync stage + the gate readout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) 300px",
          minHeight: 360,
          borderTop: "1px solid var(--hair-lit)",
        }}
      >
        <div style={{ position: "relative", minHeight: 360, borderRight: "1px solid var(--hair)" }}>
          <StrikeGroupStage destroyer={destroyer} conn={conn} />
        </div>

        {/* gate readout column */}
        <div style={{ display: "flex", flexDirection: "column", background: "var(--panel)" }}>
          {/* provenance gate */}
          <div style={{ padding: "12px 15px", borderBottom: "1px solid var(--hair)" }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>Provenance Gate · poisoning defense</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 9 }}>
              <span style={{ width: 8, height: 8, background: "var(--nominal)" }} />
              <span className="mono" style={{ fontSize: 10.5, color: "var(--ink)", letterSpacing: "0.04em" }}>
                {shore.accepted_hulls.length} ATTESTED · ADMITTED
              </span>
              <span className="mono" style={{ fontSize: 9, color: "var(--muted)", marginLeft: "auto" }}>
                {shore.accepted_hulls.join(" · ")}
              </span>
            </div>
            {destroyer.rejected.map((r) => (
              <div
                key={r.keyid ?? "poison"}
                style={{ border: "1px solid var(--critical)", background: "var(--critical-wash)", padding: "9px 11px", marginTop: 9 }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                  <span className="display" style={{ fontSize: 12, fontWeight: 700, color: "var(--critical)", letterSpacing: "0.06em" }}>
                    ✕ REJECTED
                  </span>
                  <span className="mono" style={{ fontSize: 9.5, color: "var(--ink)", marginLeft: "auto" }}>
                    {r.keyid}
                  </span>
                </div>
                <div className="mono" style={{ fontSize: 9, color: "var(--ink-dim)", lineHeight: 1.5 }}>
                  {r.reason}
                </div>
              </div>
            ))}
          </div>

          {/* eval gate */}
          <div style={{ padding: "12px 15px", borderBottom: "1px solid var(--hair)" }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>Eval Gate · forgetting defense</div>
            <Bar label="INCUMBENT" value={shore.incumbent_rmse} max={Math.max(shore.incumbent_rmse, shore.merged_rmse)} color="var(--muted)" />
            <Bar label="MERGED" value={shore.merged_rmse} max={Math.max(shore.incumbent_rmse, shore.merged_rmse)} color={shore.eval_gate_pass ? "var(--nominal)" : "var(--caution)"} />
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 8 }}>
              <span className="eyebrow" style={{ fontSize: 8.5 }}>RMSE Δ · n={shore.held_out_n}</span>
              <span
                className="num"
                style={{ marginLeft: "auto", fontSize: 15, fontWeight: 500, color: shore.rmse_delta < 0 ? "var(--nominal)" : "var(--critical)" }}
              >
                {shore.rmse_delta > 0 ? "+" : ""}{shore.rmse_delta.toFixed(6)}
              </span>
            </div>
            <div
              style={{
                marginTop: 9,
                border: `1px solid ${shore.eval_gate_pass ? "rgba(63,185,80,0.4)" : "var(--caution)"}`,
                padding: "7px 10px",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span style={{ width: 8, height: 8, background: shore.eval_gate_pass ? "var(--nominal)" : "var(--caution)" }} />
              <span className="display" style={{ fontSize: 11.5, fontWeight: 700, color: shore.eval_gate_pass ? "var(--nominal)" : "var(--caution)", letterSpacing: "0.06em" }}>
                {shore.eval_gate_pass ? "PASS · MERGE PROMOTED" : "HOLD · ROLL BACK"}
              </span>
            </div>
          </div>

          {/* accreditation footer */}
          <div style={{ padding: "12px 15px", flex: 1 }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>Accreditation Record</div>
            <div
              style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 9 }}
            >
              <span style={{ width: 8, height: 8, background: destroyer.record.verify_ok ? "var(--nominal)" : "var(--critical)" }} />
              <span className="mono" style={{ fontSize: 10, color: destroyer.record.verify_ok ? "var(--nominal)" : "var(--critical)", letterSpacing: "0.04em" }}>
                {destroyer.record.verify_ok ? "VERIFY OK" : "VERIFY FAILED"} · {destroyer.record.leaf_count} LEAVES
              </span>
            </div>
            <div className="mono" style={{ fontSize: 8.5, color: "var(--muted)", lineHeight: 1.55, marginTop: 7 }}>
              {destroyer.record.message}
            </div>
            <div className="mono" style={{ fontSize: 8.5, color: "var(--muted)", lineHeight: 1.55, marginTop: 9 }}>
              Ed25519 · in-toto/DSSE → NIST OSCAL · cATO-for-AI. The fleet improves
              only when measurably better; an unregistered keyid never touches FedAvg.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Pill({ label, value, tone }: { label: string; value: number; tone: "warning" | "critical" | "muted" }) {
  const color = tone === "critical" ? "var(--critical)" : tone === "warning" ? "var(--caution)" : "var(--muted)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, paddingRight: 4 }}>
      <span className="eyebrow" style={{ fontSize: 8 }}>{label}</span>
      <span className="num" style={{ fontSize: 14, fontWeight: 500, color }}>{value}</span>
    </div>
  );
}

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
        <span className="eyebrow" style={{ fontSize: 8.5 }}>{label}</span>
        <span className="num" style={{ fontSize: 11, color: "var(--ink)" }}>{value.toFixed(6)}</span>
      </div>
      <div style={{ height: 6, background: "var(--hair)", position: "relative" }}>
        <div style={{ position: "absolute", inset: 0, width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
