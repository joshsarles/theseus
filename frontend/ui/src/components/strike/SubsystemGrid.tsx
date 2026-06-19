import { SEVERITY_COLOR } from "../../lib/palette";
import type { DestroyerSubsystem } from "../../lib/types";

interface SubsystemGridProps {
  subsystems: DestroyerSubsystem[];
  /** compact cells for the card; expanded shows the detail line */
  expanded?: boolean;
}

/**
 * The "self-contained city" tell: a hull's 8 subsystems as a tight 4×2 lattice
 * of hairline cells, each lit by severity (nominal/warning/critical). A standby
 * cell is honestly dim — never green. This is what makes a single destroyer read
 * as a whole instrumented city at a glance.
 */
export function SubsystemGrid({ subsystems, expanded = false }: SubsystemGridProps) {
  return (
    <div
      role="list"
      aria-label="subsystems"
      style={{
        display: "grid",
        gridTemplateColumns: expanded ? "1fr 1fr" : "1fr 1fr 1fr 1fr",
        gap: 1,
        background: "var(--hair)",
        border: "1px solid var(--hair)",
      }}
    >
      {subsystems.map((s) => {
        const standby = !s.live || s.severity === "standby";
        const color = standby ? "var(--faint)" : SEVERITY_COLOR[s.severity];
        return (
          <div
            key={s.key}
            role="listitem"
            title={`${s.label} — ${s.detail}`}
            style={{
              background: "var(--panel-2)",
              padding: expanded ? "9px 11px" : "7px 8px",
              display: "flex",
              flexDirection: "column",
              gap: 5,
              minWidth: 0,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span
                aria-hidden
                style={{
                  width: 7,
                  height: 7,
                  flexShrink: 0,
                  background: color,
                  boxShadow: standby ? "none" : `0 0 6px ${color}`,
                }}
              />
              <span
                className="mono"
                style={{
                  fontSize: 8.5,
                  letterSpacing: "0.04em",
                  color: standby ? "var(--muted)" : "var(--ink)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {s.label}
              </span>
            </div>
            {expanded ? (
              <span
                className="mono"
                style={{
                  fontSize: 8.5,
                  lineHeight: 1.4,
                  color: standby ? "var(--muted)" : color,
                  letterSpacing: "0.01em",
                }}
              >
                {standby ? "STANDBY · model pending" : s.detail}
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
