import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { gsap } from "gsap";
import { deriveLeaves, parseRecordMessage, shortHash } from "../lib/format";
import type { Leaf, LeafType, RecordState } from "../lib/types";

interface RecordSpineProps {
  record: RecordState;
  /** locally-sealed decision leaves, appended live below the chain tail */
  localLeaves: Leaf[];
}

const LEAF_COLOR: Record<LeafType, string> = {
  data_staged: "var(--ink-dim)",
  model_trained: "var(--ink-dim)",
  model_promoted: "var(--nominal)",
  explained_alert: "var(--ink-dim)",
  ais_anomaly: "var(--caution)",
  human_decision: "var(--amber)",
};

const LEAF_GLYPH: Record<LeafType, string> = {
  data_staged: "▸",
  model_trained: "▸",
  model_promoted: "✓",
  explained_alert: "▸",
  ais_anomaly: "△",
  human_decision: "◆",
};

export function RecordSpine({ record, localLeaves }: RecordSpineProps) {
  const { head, merkle } = parseRecordMessage(record.message ?? "");
  const baseLeaves = useMemo(() => deriveLeaves(record, 14), [record]);

  // local decision leaves continue the sequence past the chain tail
  const total = (record.leaf_count || baseLeaves.length) + localLeaves.length;
  const leaves: Leaf[] = useMemo(() => {
    const start = (record.leaf_count || baseLeaves.length) + 1;
    const renumbered = localLeaves.map((l, i) => ({ ...l, seq: start + i }));
    return [...baseLeaves, ...renumbered];
  }, [baseLeaves, localLeaves, record.leaf_count]);

  const verified = record.verify_ok;
  const listRef = useRef<HTMLDivElement>(null);
  const prevCount = useRef(leaves.length);

  // GSAP: snap-animate a freshly sealed leaf into the spine + flash the header
  useLayoutEffect(() => {
    if (leaves.length > prevCount.current && listRef.current) {
      const nodes = listRef.current.querySelectorAll("[data-leaf]");
      const newest = nodes[nodes.length - 1] as HTMLElement | undefined;
      if (newest) {
        gsap.fromTo(
          newest,
          { backgroundColor: "rgba(212,160,0,0.22)", x: 14, opacity: 0 },
          {
            backgroundColor: "rgba(212,160,0,0)",
            x: 0,
            opacity: 1,
            duration: 0.5,
            ease: "expo.out",
          },
        );
        newest.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
    prevCount.current = leaves.length;
  }, [leaves.length]);

  // count-up flourish on the leaf-count when it changes
  const countRef = useRef<HTMLSpanElement>(null);
  const prevTotal = useRef(total);
  useEffect(() => {
    if (total !== prevTotal.current && countRef.current) {
      const obj = { v: prevTotal.current };
      gsap.to(obj, {
        v: total,
        duration: 0.45,
        ease: "power2.out",
        onUpdate: () => {
          if (countRef.current) countRef.current.textContent = String(Math.round(obj.v));
        },
      });
    }
    prevTotal.current = total;
  }, [total]);

  return (
    <aside
      style={{
        display: "flex",
        flexDirection: "column",
        background: "var(--panel-2)",
        borderLeft: "1px solid var(--hair-lit)",
        minHeight: 0,
      }}
    >
      {/* verified header — the proof banner */}
      <div
        style={{
          padding: "13px 15px 14px",
          borderBottom: `1px solid ${verified ? "rgba(63,185,80,0.4)" : "var(--critical)"}`,
        }}
      >
        <div className="eyebrow" style={{ fontSize: 9, marginBottom: 9 }}>
          Tamper-Evident Record
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span
            style={{
              width: 8,
              height: 8,
              background: verified ? "var(--nominal)" : "var(--critical)",
            }}
          />
          <span
            className="display"
            style={{
              fontSize: 14,
              fontWeight: 700,
              letterSpacing: "0.02em",
              color: verified ? "var(--nominal)" : "var(--critical)",
            }}
          >
            CHAIN VERIFIED · {verified ? "PASS" : "FAIL"}
          </span>
        </div>

        <div style={{ display: "flex", gap: 18, marginTop: 13 }}>
          <Field label="LEAVES">
            <span ref={countRef} className="num" style={{ fontSize: 20, fontWeight: 500, color: "var(--ink)" }}>
              {total}
            </span>
          </Field>
          <Field label="MERKLE ROOT">
            <span className="num" style={{ fontSize: 12, color: "var(--ink-dim)" }}>
              {merkle ? shortHash(merkle.replace(/[^0-9a-f]/gi, ""), 6, 4) : "—"}
            </span>
          </Field>
        </div>
        <Field label="HEAD" style={{ marginTop: 11 }}>
          <span className="num" style={{ fontSize: 12, color: "var(--ink-dim)" }}>
            {head ? shortHash(head.replace(/[^0-9a-f]/gi, ""), 8, 6) : "—"}
          </span>
        </Field>
      </div>

      {/* ledger — the growing spine */}
      <div className="eyebrow" style={{ padding: "10px 15px 8px", fontSize: 9 }}>
        Sealed Leaves · chain order ↓
      </div>
      <div ref={listRef} style={{ flex: 1, overflowY: "auto", paddingBottom: 12 }}>
        {leaves.map((leaf, i) => (
          <LeafRow key={`${leaf.seq}-${leaf.hash}`} leaf={leaf} last={i === leaves.length - 1} />
        ))}
      </div>

      <div
        className="mono"
        style={{
          padding: "10px 15px",
          borderTop: "1px solid var(--hair)",
          fontSize: 9.5,
          color: "var(--muted)",
          lineHeight: 1.5,
          letterSpacing: "0.02em",
        }}
      >
        Every model, anomaly &amp; human ruling is hash-chained. tamper-EVIDENT ·
        SWAN-side · unclassified.
      </div>
    </aside>
  );
}

function LeafRow({ leaf, last }: { leaf: Leaf; last: boolean }) {
  const color = LEAF_COLOR[leaf.type] ?? "var(--ink-dim)";
  const glyph = LEAF_GLYPH[leaf.type] ?? "▸";
  const isDecision = leaf.type === "human_decision";
  return (
    <div
      data-leaf
      style={{
        display: "grid",
        gridTemplateColumns: "18px 1fr",
        padding: "0 13px 0 11px",
      }}
    >
      {/* connector rail */}
      <div style={{ position: "relative", display: "flex", justifyContent: "center" }}>
        <span
          style={{
            position: "absolute",
            top: 0,
            bottom: last ? "50%" : 0,
            width: 1,
            background: "var(--hair-lit)",
          }}
        />
        <span
          className="mono"
          style={{
            position: "relative",
            marginTop: 11,
            fontSize: 10,
            color,
            background: "var(--panel-2)",
            lineHeight: 1,
            zIndex: 1,
          }}
        >
          {glyph}
        </span>
      </div>

      {/* entry */}
      <div
        style={{
          padding: "9px 0 9px 9px",
          borderBottom: "1px solid var(--hair)",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span className="num" style={{ fontSize: 9.5, color: "var(--muted)", minWidth: 26 }}>
            #{String(leaf.seq).padStart(3, "0")}
          </span>
          <span
            className="display"
            style={{
              fontSize: 10.5,
              fontWeight: 600,
              letterSpacing: "0.04em",
              color: isDecision ? "var(--amber)" : "var(--ink)",
            }}
          >
            {leaf.label}
          </span>
          {leaf.local ? (
            <span className="mono" style={{ fontSize: 8, color: "var(--muted)", marginLeft: "auto", letterSpacing: "0.1em" }}>
              LOCAL
            </span>
          ) : null}
        </div>
        <div className="num" style={{ fontSize: 10, color, marginTop: 4, letterSpacing: "0.02em" }}>
          {shortHash(leaf.hash, 8, 6)}
        </div>
        <div className="mono" style={{ fontSize: 9.5, color: "var(--muted)", marginTop: 3, lineHeight: 1.4 }}>
          {leaf.detail}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
  style,
}: {
  label: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div style={style}>
      <div className="eyebrow" style={{ fontSize: 9, marginBottom: 4 }}>
        {label}
      </div>
      {children}
    </div>
  );
}
