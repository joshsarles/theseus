import { SectionHead } from "../Hairline";
import type { FleetMerge } from "../../lib/types";

interface EvalGatePanelProps {
  merge: FleetMerge | null;
  pass: boolean | null;
}

/**
 * The eval gate — the catastrophic-forgetting defense, made legible. A merged
 * model is accepted ONLY if it beats the incumbent on a held-out set. The
 * incumbent → merged RMSE delta is shown as two measured bars; the gate is the
 * reason "the fleet improves" can be said honestly (improves SAFELY).
 */
export function EvalGatePanel({ merge, pass }: EvalGatePanelProps) {
  const ok = pass === true;
  // bars normalised against the larger RMSE so the improvement is visible
  const max = merge ? Math.max(merge.incumbent_rmse, merge.merged_rmse) : 1;
  const incPct = merge ? (merge.incumbent_rmse / max) * 100 : 0;
  const mrgPct = merge ? (merge.merged_rmse / max) * 100 : 0;

  return (
    <section style={{ borderRight: "1px solid var(--hair-lit)", display: "flex", flexDirection: "column" }}>
      <SectionHead index="B" title="Eval Gate" meta="FORGETTING DEFENSE" />
      <div style={{ padding: "12px 15px", flex: 1 }}>
        {merge ? (
          <>
            <Bar label="INCUMBENT" value={merge.incumbent_rmse} pct={incPct} color="var(--muted)" />
            <Bar label="MERGED" value={merge.merged_rmse} pct={mrgPct} color={ok ? "var(--nominal)" : "var(--caution)"} />

            <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 12 }}>
              <span className="eyebrow" style={{ fontSize: 9 }}>
                RMSE Δ · HELD-OUT n={merge.held_out_n}
              </span>
              <span
                className="num"
                style={{
                  marginLeft: "auto",
                  fontSize: 17,
                  fontWeight: 500,
                  color: merge.rmse_delta < 0 ? "var(--nominal)" : "var(--critical)",
                  letterSpacing: "-0.02em",
                }}
              >
                {merge.rmse_delta > 0 ? "+" : ""}
                {merge.rmse_delta.toFixed(6)}
              </span>
            </div>

            <div
              style={{
                marginTop: 11,
                border: `1px solid ${ok ? "rgba(63,185,80,0.4)" : "var(--caution)"}`,
                padding: "8px 11px",
                display: "flex",
                alignItems: "center",
                gap: 9,
              }}
            >
              <span style={{ width: 8, height: 8, background: ok ? "var(--nominal)" : "var(--caution)" }} />
              <span className="display" style={{ fontSize: 12, fontWeight: 700, color: ok ? "var(--nominal)" : "var(--caution)", letterSpacing: "0.06em" }}>
                {ok ? "PASS · MERGE PROMOTED" : "HOLD · DID NOT BEAT INCUMBENT"}
              </span>
            </div>
          </>
        ) : (
          <div className="mono" style={{ fontSize: 10, color: "var(--muted)" }}>
            no merge yet — run fleet/run_miniature.sh
          </div>
        )}

        <div className="mono" style={{ fontSize: 9, color: "var(--muted)", lineHeight: 1.55, marginTop: 11, letterSpacing: "0.01em" }}>
          The fleet improves only when the merged model is measurably better than
          the one it replaces. Otherwise: roll back to last-good.
        </div>
      </div>
    </section>
  );
}

function Bar({ label, value, pct, color }: { label: string; value: number; pct: number; color: string }) {
  return (
    <div style={{ marginBottom: 9 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
        <span className="eyebrow" style={{ fontSize: 9 }}>
          {label}
        </span>
        <span className="num" style={{ fontSize: 12, color: "var(--ink)" }}>
          {value.toFixed(6)}
        </span>
      </div>
      <div style={{ height: 7, background: "var(--hair)", position: "relative" }}>
        <div style={{ position: "absolute", inset: 0, width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
