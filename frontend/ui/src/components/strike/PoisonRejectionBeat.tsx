import { useEffect } from "react";
import { useFleetInject } from "../../hooks/useFleetInject";
import type { DestroyerConn } from "../../hooks/useDestroyerState";
import type { InjectResult } from "../../lib/types";

/**
 * PROVENANCE GATE — the live, interactive poison-rejection beat.
 *
 * The watch officer arms and fires a FORGED model delta at the shore fleet brain.
 * The REAL provenance gate (fleet/fleet_brain.py, via POST /api/fleet/inject)
 * rejects it — unknown keyid, no .pub in the trust registry — while the attested
 * deltas merge through the eval gate and the tamper-evident chain RE-VERIFIES on
 * screen. Nothing here is canned: every field is read from the gate's actual report.
 *
 * This is the visceral "trustworthy AI" moment — the moat witnessed, not described.
 */
export function PoisonRejectionBeat({
  conn,
  onComplete,
}: {
  conn: DestroyerConn;
  /** fired with the gate's report when it decides — lets the scene re-pull OSCAL + flash the moment */
  onComplete?: (result: InjectResult) => void;
}) {
  const { phase, result, inject, reset } = useFleetInject();
  const busy = phase === "injecting";

  // when the live merge seals (phase → done), hand the result up so the scene can re-verify
  // OSCAL in lockstep and flash the cross-panel "forged delta rejected" moment
  useEffect(() => {
    if (phase === "done" && result && onComplete) onComplete(result);
  }, [phase, result, onComplete]);

  return (
    <div style={{ padding: "12px 15px", borderBottom: "1px solid var(--hair)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div className="eyebrow" style={{ fontSize: 9 }}>Provenance Gate · poisoning defense</div>
        <span className="mono" style={{ fontSize: 8, color: "var(--muted)", marginLeft: "auto", letterSpacing: "0.1em" }}>
          LIVE · fleet_brain.py
        </span>
      </div>

      {/* the arming control */}
      <button
        type="button"
        onClick={phase === "done" || phase === "error" ? reset : inject}
        disabled={busy}
        style={{
          width: "100%",
          marginTop: 10,
          padding: "9px 11px",
          background: busy ? "var(--panel)" : phase === "done" ? "transparent" : "rgba(212,160,0,0.08)",
          border: `1px solid ${phase === "done" ? "var(--hair-lit)" : "var(--amber-dim)"}`,
          color: busy ? "var(--amber)" : phase === "done" ? "var(--muted)" : "var(--amber)",
          cursor: busy ? "wait" : "pointer",
          font: "inherit",
          letterSpacing: "0.12em",
          fontSize: 10,
          textTransform: "uppercase",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
        }}
        className="display"
      >
        {busy ? (
          <>
            <Spinner /> Injecting forged delta…
          </>
        ) : phase === "done" || phase === "error" ? (
          "↺ Re-arm gate"
        ) : (
          "⚠ Inject forged delta"
        )}
      </button>

      {phase === "idle" && (
        <div className="mono" style={{ fontSize: 8.5, color: "var(--muted)", lineHeight: 1.5, marginTop: 8 }}>
          Fire a model delta signed by a key NOT in the trust registry. A naive fleet would merge it.
          {conn !== "live" && (
            <span style={{ color: "var(--caution)" }}> · needs the live API (:8501)</span>
          )}
        </div>
      )}

      {phase === "error" && (
        <div
          className="mono"
          style={{ fontSize: 9, color: "var(--caution)", lineHeight: 1.5, marginTop: 9, border: "1px solid var(--amber-dim)", padding: "8px 10px" }}
        >
          Live fleet brain unreachable — start the API: <span style={{ color: "var(--ink)" }}>bash deploy/strike_group_up.sh</span>
        </div>
      )}

      {phase === "done" && result && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          {/* the REJECT card */}
          {result.rejected.map((r) => (
            <div
              key={r.keyid ?? "poison"}
              style={{ border: "1px solid var(--critical)", background: "var(--critical-wash)", padding: "9px 11px" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                <span className="display" style={{ fontSize: 12, fontWeight: 700, color: "var(--critical)", letterSpacing: "0.06em", flexShrink: 0 }}>
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

          {/* attested deltas admitted */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, background: "var(--nominal)", flexShrink: 0 }} />
            <span className="mono" style={{ fontSize: 10, color: "var(--ink)", letterSpacing: "0.03em" }}>
              {result.deltas_accepted} ATTESTED · ADMITTED
            </span>
            <span className="mono" style={{ fontSize: 9, color: "var(--muted)", marginLeft: "auto" }}>
              {result.accepted_ships.join(" · ")}
            </span>
          </div>

          {/* eval gate outcome */}
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span className="eyebrow" style={{ fontSize: 8.5 }}>Eval gate · n={result.held_out_n}</span>
            <span
              className="num"
              style={{ marginLeft: "auto", fontSize: 12, color: result.rmse_delta < 0 ? "var(--nominal)" : "var(--critical)" }}
            >
              RMSE Δ {result.rmse_delta > 0 ? "+" : ""}{result.rmse_delta.toFixed(6)}
            </span>
          </div>

          {/* the chain re-verify — the climax */}
          <div
            style={{
              border: `1px solid ${result.chain_verify ? "rgba(63,185,80,0.45)" : "var(--critical)"}`,
              background: result.chain_verify ? "rgba(63,185,80,0.06)" : "var(--critical-wash)",
              padding: "8px 10px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 8, height: 8, background: result.chain_verify ? "var(--nominal)" : "var(--critical)", flexShrink: 0 }} />
              <span className="display" style={{ fontSize: 11, fontWeight: 700, color: result.chain_verify ? "var(--nominal)" : "var(--critical)", letterSpacing: "0.06em" }}>
                {result.chain_verify ? "CHAIN RE-VERIFIES" : "CHAIN BROKEN"}
              </span>
              <span className="mono" style={{ fontSize: 9, color: "var(--muted)", marginLeft: "auto" }}>
                {result.leaf_count} LEAVES
              </span>
            </div>
            <div className="mono" style={{ fontSize: 8, color: "var(--muted)", lineHeight: 1.5, marginTop: 6 }}>
              {result.chain_verify_msg}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <span
      style={{
        width: 9,
        height: 9,
        border: "1.5px solid var(--amber-dim)",
        borderTopColor: "var(--amber)",
        borderRadius: "50%",
        display: "inline-block",
        animation: "theseus-spin 0.7s linear infinite",
      }}
    />
  );
}
