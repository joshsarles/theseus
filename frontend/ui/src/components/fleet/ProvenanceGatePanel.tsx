import { SectionHead } from "../Hairline";
import type { FleetRejection } from "../../lib/types";

interface ProvenanceGatePanelProps {
  rejected: FleetRejection[];
  accepted: string[];
}

/**
 * The provenance gate — the poisoning defense, made legible. The fleet brain
 * merges ONLY contributions carrying a valid Ed25519/DSSE attestation whose
 * keyid is in the trust registry. A captured/forged hull's delta is REJECTED
 * before it can touch the model. This is the Byzantine-poisoning answer.
 */
export function ProvenanceGatePanel({ rejected, accepted }: ProvenanceGatePanelProps) {
  return (
    <section style={{ borderRight: "1px solid var(--hair-lit)", display: "flex", flexDirection: "column" }}>
      <SectionHead index="A" title="Provenance Gate" meta="POISONING DEFENSE" />
      <div style={{ padding: "12px 15px", flex: 1 }}>
        {/* accepted */}
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 11 }}>
          <span style={{ width: 8, height: 8, background: "var(--nominal)" }} />
          <span className="mono" style={{ fontSize: 10.5, color: "var(--ink)", letterSpacing: "0.04em" }}>
            {accepted.length} ATTESTED · ADMITTED
          </span>
          <span className="mono" style={{ fontSize: 9, color: "var(--muted)", marginLeft: "auto" }}>
            {accepted.join(" · ") || "—"}
          </span>
        </div>

        {/* rejected — the headline beat */}
        {rejected.map((r) => (
          <div
            key={r.id ?? "poison"}
            style={{
              border: "1px solid var(--critical)",
              background: "var(--critical-wash)",
              padding: "10px 12px",
              marginBottom: 9,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 6 }}>
              <span className="display" style={{ fontSize: 12, fontWeight: 700, color: "var(--critical)", letterSpacing: "0.06em" }}>
                ✕ REJECTED
              </span>
              <span className="mono" style={{ fontSize: 10, color: "var(--ink)", marginLeft: "auto" }}>
                {r.id}
              </span>
            </div>
            <div className="mono" style={{ fontSize: 9.5, color: "var(--ink-dim)", lineHeight: 1.5 }}>
              {r.reason}
            </div>
          </div>
        ))}
        {rejected.length === 0 ? (
          <div className="mono" style={{ fontSize: 10, color: "var(--muted)" }}>
            no rejected deltas in this merge
          </div>
        ) : null}

        <div className="mono" style={{ fontSize: 9, color: "var(--muted)", lineHeight: 1.55, marginTop: 4, letterSpacing: "0.01em" }}>
          A captured hull cannot poison the fleet model: an unregistered keyid is
          denied at the gate before FedAvg.
        </div>
      </div>
    </section>
  );
}
