import { useEffect, useMemo, useRef, useState } from "react";
import { SectionHead } from "./Hairline";
import { CONTACT_COLOR, CONTACT_LABEL, CONTACT_ORDER } from "../lib/palette";
import { fmtLat, fmtLon, fmtPct } from "../lib/format";
import { postDecision } from "../lib/decision";
import type { Contact, ContactType, Verdict } from "../lib/types";

interface ContactsPanelProps {
  contacts: Contact[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** fires when a ruling is sealed → spine grows a human_decision leaf */
  onDecision: (contactId: string, verdict: Verdict, serverSealed: boolean) => void;
}

type Ruling = { verdict: Verdict; serverSealed: boolean };

/** Risk #7: hold the button locked this long after a click so a presenter's
 * rapid double-tap cannot fire a second POST / seal a second leaf. */
const DEBOUNCE_MS = 1000;

export function ContactsPanel({ contacts, selectedId, onSelect, onDecision }: ContactsPanelProps) {
  const [rulings, setRulings] = useState<Record<string, Ruling>>({});
  const [busy, setBusy] = useState<string | null>(null);
  // Synchronous re-entrancy guards — set BEFORE any await so two clicks landing
  // in the same React batch (before `busy` re-renders) can never both proceed.
  const inFlight = useRef<Set<string>>(new Set());
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    const timers = debounceTimers.current;
    return () => {
      for (const id of Object.keys(timers)) clearTimeout(timers[id]);
    };
  }, []);

  const sorted = useMemo(
    () =>
      [...contacts].sort((a, b) => {
        const o = CONTACT_ORDER[a.type] - CONTACT_ORDER[b.type];
        if (o !== 0) return o;
        return b.confidence - a.confidence;
      }),
    [contacts],
  );

  const pending = sorted.filter((c) => !rulings[c.id]);

  async function decide(c: Contact, verdict: Verdict) {
    // Re-entrancy guard #1: already ruled. Re-entrancy guard #2: a POST for this
    // contact is in flight OR inside its post-click debounce window. Both are
    // checked synchronously (refs, not async state) so a double-click seals once.
    if (rulings[c.id] || inFlight.current.has(c.id)) return;
    inFlight.current.add(c.id);
    setBusy(c.id);

    // Hold the lock for at least DEBOUNCE_MS even if the POST returns instantly,
    // so the button stays disabled across a rapid double-tap on stage.
    if (debounceTimers.current[c.id]) clearTimeout(debounceTimers.current[c.id]);
    debounceTimers.current[c.id] = setTimeout(() => {
      inFlight.current.delete(c.id);
      delete debounceTimers.current[c.id];
    }, DEBOUNCE_MS);

    const res = await postDecision(c.id, verdict);
    setRulings((r) => ({ ...r, [c.id]: { verdict, serverSealed: res.serverSealed } }));
    setBusy(null);
    onDecision(c.id, verdict, res.serverSealed);
  }

  return (
    <section style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      <SectionHead
        index="04"
        title="Contacts · Human-in-Command"
        meta={`${pending.length} PENDING RULING`}
      />
      <div
        className="mono"
        style={{
          padding: "8px 14px",
          fontSize: 10,
          color: "var(--muted)",
          borderBottom: "1px solid var(--hair)",
          lineHeight: 1.5,
          letterSpacing: "0.01em",
        }}
      >
        THESEUS recommends · the watch officer decides · nothing actions automatically.
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {sorted.map((c) => (
          <ContactRow
            key={c.id}
            c={c}
            selected={c.id === selectedId}
            ruling={rulings[c.id]}
            busy={busy === c.id}
            onSelect={() => onSelect(c.id)}
            onDecide={(v) => decide(c, v)}
          />
        ))}
      </div>
    </section>
  );
}

function ContactRow({
  c,
  selected,
  ruling,
  busy,
  onSelect,
  onDecide,
}: {
  c: Contact;
  selected: boolean;
  ruling?: Ruling;
  busy: boolean;
  onSelect: () => void;
  onDecide: (v: Verdict) => void;
}) {
  const color = CONTACT_COLOR[c.type];
  const isSuspect = c.type === "position_jump";
  return (
    <div
      onClick={onSelect}
      style={{
        borderBottom: "1px solid var(--hair)",
        background: selected
          ? "var(--amber-wash)"
          : isSuspect && !ruling
            ? "var(--critical-wash)"
            : "transparent",
        borderLeft: selected ? "2px solid var(--amber)" : "2px solid transparent",
        cursor: "pointer",
        opacity: ruling ? 0.78 : 1,
      }}
    >
      <div style={{ padding: "11px 14px" }}>
        {/* header line */}
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 7 }}>
          <span
            className="mono"
            style={{
              fontSize: 9,
              letterSpacing: "0.12em",
              color,
              border: `1px solid ${color}`,
              padding: "1px 6px",
            }}
          >
            {CONTACT_LABEL[c.type as ContactType]}
          </span>
          <span className="num" style={{ fontSize: 11.5, color: "var(--ink)", letterSpacing: "0.01em" }}>
            {c.mmsi}
          </span>
          <span className="mono" style={{ fontSize: 9.5, color: "var(--muted)", textTransform: "uppercase" }}>
            {c.vessel_class}
          </span>
          <span className="num" style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-dim)" }}>
            CONF {fmtPct(c.confidence)}
          </span>
        </div>

        {/* coords */}
        <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginBottom: 6 }}>
          {typeof c.lat === "number" ? fmtLat(c.lat) : "—"} · {typeof c.lon === "number" ? fmtLon(c.lon) : "—"}
        </div>

        {/* why */}
        <div
          className="mono"
          style={{ fontSize: 10.5, color: "var(--ink-dim)", lineHeight: 1.5, marginBottom: 8 }}
        >
          {c.why}
        </div>

        {/* recommend + actions */}
        <div
          style={{
            borderTop: "1px solid var(--hair)",
            paddingTop: 9,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <span className="eyebrow" style={{ fontSize: 9, flexShrink: 0 }}>
            Recommend
          </span>
          <span
            className="mono"
            style={{
              fontSize: 10,
              color: "var(--ink-dim)",
              flex: 1,
              lineHeight: 1.4,
              minWidth: 0,
            }}
          >
            {c.recommended_action}
          </span>

          {ruling ? (
            <Sealed ruling={ruling} />
          ) : (
            <div style={{ display: "flex", gap: 6, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
              <Btn
                kind="accept"
                disabled={busy}
                onClick={() => onDecide("accepted")}
              >
                {busy ? "…" : "ACCEPT"}
              </Btn>
              <Btn
                kind="override"
                disabled={busy}
                onClick={() => onDecide("overridden")}
              >
                OVERRIDE
              </Btn>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Sealed({ ruling }: { ruling: Ruling }) {
  const accepted = ruling.verdict === "accepted";
  const color = accepted ? "var(--nominal)" : "var(--caution)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7, flexShrink: 0 }}>
      <span className="mono" style={{ fontSize: 9, color: "var(--muted)", letterSpacing: "0.1em" }}>
        {ruling.serverSealed ? "SEALED" : "SEALED · LOCAL"}
      </span>
      <span
        className="mono"
        style={{
          fontSize: 9.5,
          letterSpacing: "0.12em",
          color,
          border: `1px solid ${color}`,
          padding: "3px 9px",
        }}
      >
        {accepted ? "✓ ACCEPTED" : "⟂ OVERRIDDEN"}
      </span>
    </div>
  );
}

function Btn({
  children,
  kind,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  kind: "accept" | "override";
  disabled?: boolean;
  onClick: () => void;
}) {
  const accept = kind === "accept";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      style={{
        fontFamily: "var(--mono)",
        fontSize: 10,
        letterSpacing: "0.1em",
        padding: "5px 11px",
        background: accept ? "var(--amber)" : "transparent",
        color: accept ? "#0a0c10" : "var(--ink-dim)",
        border: `1px solid ${accept ? "var(--amber)" : "var(--hair-lit)"}`,
        cursor: disabled ? "wait" : "pointer",
        fontWeight: 500,
      }}
    >
      {children}
    </button>
  );
}
