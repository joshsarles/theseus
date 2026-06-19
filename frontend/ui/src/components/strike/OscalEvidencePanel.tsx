import { useCallback, useRef, useState } from "react";
import type { OscalState } from "../../lib/types";
import { type OscalConn, OSCAL_TAMPER_URL } from "../../hooks/useOscalState";

/**
 * OSCAL EVIDENCE — the accreditation package an Authorizing Official ingests.
 *
 * The sealed tamper-evident record, projected onto NIST SP 800-53 rev5 as OSCAL
 * assessment-results (deploy/lula/record_to_oscal.py, GET /api/oscal). This is the
 * path-to-production win: runtime decisions reported as control evidence in the AO's
 * OWN language. A control reads `satisfied` ONLY when the record cryptographically
 * verifies AND its events are sealed + signed + in-toto attested — never asserted,
 * never CERTIFIED (the emitter enforces it; status stays EVIDENCE_LOGGED).
 */
export function OscalEvidencePanel({ oscal, conn = "live" }: { oscal: OscalState; conn?: OscalConn }) {
  // "Prove it snaps": fetch the OSCAL projection of a TAMPERED copy of the record (the real
  // record is never touched — the backend tampers a throwaway copy) and show every control
  // degrade to not-satisfied for a few seconds, then revert to the live evidence.
  const [preview, setPreview] = useState<OscalState | null>(null);
  const [snapping, setSnapping] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const proveItSnaps = useCallback(async () => {
    if (snapping) return;
    setSnapping(true);
    try {
      const res = await fetch(OSCAL_TAMPER_URL);
      if (res.ok) {
        const t = (await res.json()) as OscalState;
        setPreview(t);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => setPreview(null), 6000); // auto-revert to live
      }
    } catch {
      /* offline — leave the live view */
    } finally {
      setSnapping(false);
    }
  }, [snapping]);

  // What we render: the tampered projection while previewing, else the live evidence.
  const view = preview ?? oscal;
  const ok = view.record_verified;
  const tampering = !!preview;
  // Honesty: if the endpoint isn't truly live, this panel may be showing the offline fixture or
  // a stale snapshot — never let a fixture read as real cryptographic evidence (mirror the
  // PoisonRejectionBeat's conn treatment).
  const notLive = conn !== "live";
  const connLabel = conn === "mock" ? "OFFLINE FIXTURE" : conn === "stale" ? "STALE" : conn === "connecting" ? "LINKING…" : "";
  return (
    <div
      style={{
        padding: "12px 15px",
        flex: 1,
        minHeight: 0,
        overflow: "auto",
        // a faint red wash while the tamper demo is on-screen, so the SNAP reads at a glance
        background: tampering ? "var(--critical-wash)" : undefined,
        transition: "background 0.25s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div className="eyebrow" style={{ fontSize: 9 }}>Accreditation Evidence · OSCAL</div>
        {notLive && connLabel && !tampering && (
          <span
            className="mono"
            style={{ fontSize: 7.5, color: "var(--critical)", letterSpacing: "0.1em", border: "1px solid var(--critical)", padding: "2px 6px" }}
          >
            {connLabel}
          </span>
        )}
        {tampering && (
          <span
            className="mono"
            style={{ fontSize: 7.5, color: "var(--critical)", letterSpacing: "0.1em", border: "1px solid var(--critical)", padding: "2px 6px" }}
          >
            TAMPER DEMO · 1 BYTE FLIPPED (live record untouched)
          </span>
        )}
        <span
          className="mono"
          style={{ fontSize: 7.5, color: "var(--amber)", marginLeft: "auto", letterSpacing: "0.1em", border: "1px solid var(--amber-dim)", padding: "2px 6px" }}
        >
          {view.framework}
        </span>
      </div>

      {/* verify status + crypto coverage */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
        <span style={{ width: 8, height: 8, background: ok ? "var(--nominal)" : "var(--critical)", flexShrink: 0 }} />
        <span className="mono" style={{ fontSize: 10, color: ok ? "var(--nominal)" : "var(--critical)", letterSpacing: "0.03em" }}>
          {ok ? "RECORD VERIFIES" : tampering ? "CHAIN SNAPPED" : "VERIFY FAILED"}
        </span>
        <span className="mono" style={{ fontSize: 8.5, color: "var(--muted)", marginLeft: "auto" }}>
          {view.controls_satisfied}/{view.controls_total} CONTROLS
        </span>
      </div>

      <div style={{ display: "flex", gap: 14, marginTop: 8 }}>
        <Stat label="LEAVES" value={String(view.leaf_count)} />
        <Stat label="ED25519" value={view.signed_leaves} />
        <Stat label="IN-TOTO" value={view.attested_leaves} />
      </div>

      {/* the SP 800-53 control chips */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 11 }}>
        {view.controls.map((c) => {
          const sat = c.state === "satisfied";
          return (
            <div
              key={c.control}
              title={c.remark}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                border: "1px solid var(--hair)",
                borderLeft: `2px solid ${sat ? "var(--nominal)" : "var(--critical)"}`,
                padding: "5px 9px",
              }}
            >
              <span className="num" style={{ fontSize: 10, color: "var(--ink)", minWidth: 38, letterSpacing: "0.04em" }}>
                {c.control}
              </span>
              <span className="mono" style={{ fontSize: 9, color: "var(--ink-dim)", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.title}
              </span>
              <span
                className="mono"
                style={{ fontSize: 8, color: sat ? "var(--nominal)" : "var(--critical)", marginLeft: "auto", letterSpacing: "0.06em", flexShrink: 0 }}
              >
                {sat ? "SATISFIED" : "NOT SATISFIED"}
              </span>
            </div>
          );
        })}
      </div>

      {/* prove-it-snaps control — the tamper-evidence made visceral */}
      <button
        type="button"
        onClick={proveItSnaps}
        disabled={snapping || tampering}
        style={{
          width: "100%",
          marginTop: 10,
          padding: "6px 10px",
          background: "transparent",
          border: `1px solid ${tampering ? "var(--critical)" : "var(--hair-lit)"}`,
          color: tampering ? "var(--critical)" : "var(--ink-dim)",
          cursor: snapping || tampering ? "default" : "pointer",
          font: "inherit",
          fontSize: 9,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
        }}
        className="display"
      >
        {tampering ? "⚡ chain snapped — reverting to live…" : snapping ? "tampering a copy…" : "⚡ Prove it snaps"}
      </button>

      {/* the honest footer — the AO line */}
      <div className="mono" style={{ fontSize: 8.5, color: "var(--muted)", lineHeight: 1.55, marginTop: 10 }}>
        {view.standard} · status{" "}
        <span style={{ color: "var(--amber)" }}>{view.accreditation_status}</span> (never CERTIFIED).
        Ed25519 · in-toto/DSSE → NIST OSCAL · the runtime-decision evidence an AO signs as cATO-for-AI.
      </div>
      <div className="mono" style={{ fontSize: 8, color: "var(--faint)", lineHeight: 1.5, marginTop: 6, wordBreak: "break-all" }}>
        {tampering
          ? view.verify_message
          : `merkle ${view.merkle_root.slice(0, 24)}… · head ${view.chain_head.slice(0, 24)}…`}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span className="eyebrow" style={{ fontSize: 7.5 }}>{label}</span>
      <span className="num" style={{ fontSize: 12, color: "var(--ink)" }}>{value}</span>
    </div>
  );
}
