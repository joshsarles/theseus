import { SectionHead } from "../Hairline";
import { parseRecordMessage, shortHash } from "../../lib/format";
import type { FleetRecord } from "../../lib/types";

interface AccreditationPanelProps {
  record: FleetRecord;
}

/**
 * The record-as-accreditation framing. The fleet chain isn't a side feature: it
 * is the trust fabric that makes safe fleet learning accreditable. Every merge
 * leaf is Ed25519-signed and wrapped as an in-toto / DSSE attestation, and the
 * chain maps to a NIST OSCAL control catalog — the cATO-for-AI claim: accredit
 * the pipeline's provenance, not the frozen weights. Credible, not hypey.
 */
export function AccreditationPanel({ record }: AccreditationPanelProps) {
  const { head, merkle } = parseRecordMessage(record.message ?? "");
  const ok = record.verify_ok;
  // the live message reports "N Ed25519 sigs OK, N in-toto/DSSE attestations OK"
  const sigs = /(\d+)\s+Ed25519/i.exec(record.message ?? "")?.[1];
  const dsse = /(\d+)\s+in-toto/i.exec(record.message ?? "")?.[1];

  return (
    <section style={{ borderRight: "1px solid var(--hair-lit)", display: "flex", flexDirection: "column" }}>
      <SectionHead index="C" title="Accreditation" meta="cATO-FOR-AI" />
      <div style={{ padding: "12px 15px", flex: 1 }}>
        {/* verify banner */}
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 11 }}>
          <span style={{ width: 8, height: 8, background: ok ? "var(--nominal)" : "var(--critical)" }} />
          <span
            className="display"
            style={{ fontSize: 12, fontWeight: 700, color: ok ? "var(--nominal)" : "var(--critical)", letterSpacing: "0.04em" }}
          >
            FLEET CHAIN · {ok ? "VERIFIED" : "SNAPPED"}
          </span>
          <span className="num" style={{ fontSize: 11, color: "var(--ink-dim)", marginLeft: "auto" }}>
            {record.leaf_count} LEAVES
          </span>
        </div>

        {/* crypto rail */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 11 }}>
          <Chip k="SIGNING" v={`Ed25519 · ${sigs ?? record.leaf_count} OK`} />
          <Chip k="ATTESTATION" v={`in-toto/DSSE · ${dsse ?? record.leaf_count} OK`} />
          <Chip k="MERKLE ROOT" v={merkle ? shortHash(merkle.replace(/[^0-9a-f]/gi, ""), 6, 4) : "—"} mono />
          <Chip k="CHAIN HEAD" v={head ? shortHash(head.replace(/[^0-9a-f]/gi, ""), 6, 4) : "—"} mono />
        </div>

        {/* OSCAL mapping */}
        <div style={{ border: "1px solid var(--hair-lit)", padding: "9px 11px" }}>
          <div className="eyebrow" style={{ fontSize: 9, marginBottom: 6 }}>
            Maps To
          </div>
          <Row a="NIST OSCAL" b="control-catalog evidence" />
          <Row a="cATO" b="continuous authorization to operate" />
          <Row a="SLSA / Sigstore" b="DoD-mandated supply-chain" />
        </div>

        <div className="mono" style={{ fontSize: 9, color: "var(--muted)", lineHeight: 1.55, marginTop: 11, letterSpacing: "0.01em" }}>
          You accredit the pipeline's provenance — not the frozen weights. A
          learning model becomes accreditable because every contribution, merge,
          and promotion is signed, attested, and replayable.
        </div>
      </div>
    </section>
  );
}

function Chip({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div style={{ border: "1px solid var(--hair)", padding: "6px 9px" }}>
      <div className="eyebrow" style={{ fontSize: 8.5, marginBottom: 3 }}>
        {k}
      </div>
      <div className={mono ? "num" : "mono"} style={{ fontSize: 10.5, color: "var(--ink)", letterSpacing: mono ? undefined : "0.02em" }}>
        {v}
      </div>
    </div>
  );
}

function Row({ a, b }: { a: string; b: string }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "2px 0" }}>
      <span className="mono" style={{ fontSize: 10, color: "var(--amber)", minWidth: 96, letterSpacing: "0.02em" }}>
        {a}
      </span>
      <span className="mono" style={{ fontSize: 9.5, color: "var(--ink-dim)" }}>
        {b}
      </span>
    </div>
  );
}
