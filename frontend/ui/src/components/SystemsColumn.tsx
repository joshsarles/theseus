import { SectionHead } from "./Hairline";
import { SEVERITY_COLOR } from "../lib/palette";
import type { ShipSystem } from "../lib/types";

interface SystemsColumnProps {
  systems: ShipSystem[];
}

export function SystemsColumn({ systems }: SystemsColumnProps) {
  const live = systems.filter((s) => s.live).length;
  return (
    <section style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      <SectionHead
        index="01"
        title="Ship Systems"
        meta={`${live} LIVE · ${systems.length - live} STANDBY`}
      />
      <div style={{ flex: 1, overflowY: "auto" }}>
        {systems.map((s, i) => (
          <SystemRow key={s.key} sys={s} num={i + 1} />
        ))}
      </div>
    </section>
  );
}

function SystemRow({ sys, num }: { sys: ShipSystem; num: number }) {
  const color = SEVERITY_COLOR[sys.severity];
  const standby = !sys.live;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "3px 24px 1fr",
        alignItems: "stretch",
        borderBottom: "1px solid var(--hair)",
        background: sys.severity === "critical" ? "var(--critical-wash)" : "transparent",
        opacity: standby ? 0.62 : 1,
      }}
    >
      {/* severity spine */}
      <div style={{ background: standby ? "transparent" : color }} />

      {/* index */}
      <div
        className="num"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 10,
          color: "var(--muted)",
          borderRight: "1px solid var(--hair)",
        }}
      >
        {String(num).padStart(2, "0")}
      </div>

      {/* body */}
      <div style={{ padding: "10px 13px", minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 4,
          }}
        >
          <span
            className="display"
            style={{
              fontSize: 11.5,
              fontWeight: 600,
              letterSpacing: "0.03em",
              color: standby ? "var(--ink-dim)" : "var(--ink)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {sys.label}
          </span>
          <span
            className="mono"
            style={{
              marginLeft: "auto",
              fontSize: 9,
              letterSpacing: "0.12em",
              color: standby ? "var(--muted)" : color,
              padding: "2px 6px",
              border: `1px solid ${standby ? "var(--hair)" : color}`,
              whiteSpace: "nowrap",
            }}
          >
            {standby ? "STANDBY" : sys.severity.toUpperCase()}
          </span>
        </div>
        <div
          className="mono"
          style={{
            fontSize: 10.5,
            color: "var(--muted)",
            lineHeight: 1.4,
            letterSpacing: "0.01em",
          }}
        >
          {sys.detail}
        </div>
      </div>
    </div>
  );
}
