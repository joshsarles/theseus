import { useUtcClock } from "../hooks/useUtcClock";
import type { ConnState } from "../hooks/useShipState";
import type { ShipState } from "../lib/types";

interface CommandHeaderProps {
  state: ShipState;
  conn: ConnState;
}

const CONN_LABEL: Record<ConnState, string> = {
  connecting: "LINKING",
  live: "LINK LIVE",
  stale: "LINK STALE",
  mock: "SIM FEED",
};

export function CommandHeader({ state, conn }: CommandHeaderProps) {
  const utc = useUtcClock();
  const critical = state.systems.filter((s) => s.severity === "critical").length;
  const liveCount = state.systems.filter((s) => s.live).length;
  const jumps = state.contacts.filter((c) => c.type === "position_jump").length;

  return (
    <header
      style={{
        borderBottom: "1px solid var(--hair-lit)",
        background: "var(--panel)",
      }}
    >
      {/* identity strip */}
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
          height: 64,
        }}
      >
        {/* ship sigil + name */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "0 22px",
            borderRight: "1px solid var(--hair)",
          }}
        >
          <Sigil />
          <div>
            <div
              className="display"
              style={{
                fontSize: 22,
                fontWeight: 700,
                letterSpacing: "-0.04em",
                lineHeight: 1,
                color: "var(--ink)",
              }}
            >
              {state.ship}
            </div>
            <div className="eyebrow" style={{ marginTop: 4 }}>
              Combat Information Center
            </div>
          </div>
        </div>

        {/* posture rail */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "0 20px",
            flex: 1,
            minWidth: 0,
          }}
        >
          <span
            className="mono"
            style={{
              fontSize: 11.5,
              color: "var(--ink-dim)",
              letterSpacing: "0.02em",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {state.posture}
          </span>
        </div>

        {/* live readouts */}
        <Readout label="SYSTEMS LIVE" value={`${liveCount}/${state.systems.length}`} />
        <Readout
          label="CONTACTS"
          value={String(state.contacts.length)}
          tone={state.contacts.length ? "ink" : "dim"}
        />
        <Readout
          label="SPOOF / JUMP"
          value={String(jumps)}
          tone={jumps > 0 ? "critical" : "ink"}
        />
        <Readout
          label="CRITICAL"
          value={String(critical)}
          tone={critical > 0 ? "critical" : "ink"}
        />

        {/* clock + link */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            gap: 5,
            padding: "0 22px",
            borderLeft: "1px solid var(--hair)",
            minWidth: 168,
          }}
        >
          <div
            className="num"
            style={{ fontSize: 18, fontWeight: 500, color: "var(--ink)", lineHeight: 1 }}
          >
            {utc}
            <span style={{ fontSize: 10, color: "var(--muted)", marginLeft: 6 }}>UTC</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span
              className={conn === "live" ? "live-dot" : ""}
              style={{
                width: 6,
                height: 6,
                background: conn === "live" ? "var(--amber)" : conn === "stale" ? "var(--caution)" : "var(--faint)",
              }}
            />
            <span
              className="mono"
              style={{
                fontSize: 10,
                letterSpacing: "0.14em",
                color: conn === "live" ? "var(--amber)" : "var(--muted)",
              }}
            >
              {CONN_LABEL[conn]}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}

function Readout({
  label,
  value,
  tone = "ink",
}: {
  label: string;
  value: string;
  tone?: "ink" | "dim" | "critical";
}) {
  const color =
    tone === "critical" ? "var(--critical)" : tone === "dim" ? "var(--muted)" : "var(--ink)";
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 5,
        padding: "0 18px",
        borderLeft: "1px solid var(--hair)",
        minWidth: 92,
      }}
    >
      <span className="eyebrow" style={{ fontSize: 9 }}>
        {label}
      </span>
      <span className="num" style={{ fontSize: 19, fontWeight: 500, color, lineHeight: 1 }}>
        {value}
      </span>
    </div>
  );
}

/** A minimal engraved anchor/ship sigil — vector, no glow. */
function Sigil() {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden>
      <rect x="0.5" y="0.5" width="29" height="29" stroke="var(--hair-lit)" />
      <path
        d="M15 5.5v19M15 5.5a1.6 1.6 0 100-3.2 1.6 1.6 0 000 3.2zM8 8.5h14M7 16c0 4.4 3.6 8 8 8s8-3.6 8-8M7 16l2.4 1.4M23 16l-2.4 1.4"
        stroke="var(--amber)"
        strokeWidth="1.1"
        strokeLinecap="square"
      />
    </svg>
  );
}
