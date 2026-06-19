import { useMemo } from "react";
import { motion } from "framer-motion";
import type { Destroyer, Severity } from "../../lib/types";
import { SEVERITY_COLOR } from "../../lib/palette";
import { ShipTwin } from "../twin/ShipTwin";
import { ShipSilhouette } from "./ShipSilhouette";
import { SubsystemGrid } from "./SubsystemGrid";
import type { ZoneStatus } from "../../lib/twin";

interface DestroyerCardProps {
  ship: Destroyer;
  conn: "live" | "stale" | "mock" | "connecting";
  selected: boolean;
  onSelect: () => void;
}

const SEVERITY_RANK: Record<Severity, number> = { critical: 3, warning: 2, nominal: 1, standby: 0 };

function worstSeverity(ship: Destroyer): Severity {
  return ship.subsystems.reduce<Severity>((worst, s) => {
    const sev = s.live ? s.severity : "standby";
    return SEVERITY_RANK[sev] > SEVERITY_RANK[worst] ? sev : worst;
  }, "standby");
}

/** Map this hull's subsystems onto the two twin zones (machinery aft, contacts fwd). */
function deriveTwinZones(ship: Destroyer): ZoneStatus[] {
  const find = (key: string) => ship.subsystems.find((s) => s.key === key);
  const machinery = find("machinery") ?? find("propulsion");
  const contacts = find("contacts");
  return [
    {
      zone: "machinery",
      label: "MACHINERY · HM&E",
      node: "PI-1 · AFT",
      severity: machinery?.live ? machinery.severity : "standby",
      detail: machinery?.detail ?? "engineering organ",
    },
    {
      zone: "contacts",
      label: "CONTACTS · TACTICAL",
      node: "PI-2 · FWD",
      severity: contacts?.live ? contacts.severity : "standby",
      detail: contacts?.detail ?? "sensor organ",
    },
  ];
}

/**
 * One destroyer in the strike group, as an instrument card: identity strip,
 * a ship rendering (the flagship gets the live procedural 3D twin; sisters get a
 * flat plan-view silhouette), the local CBM model + signed-delta sync readout,
 * and the 8-subsystem city grid lit live by severity.
 */
export function DestroyerCard({ ship, conn, selected, onSelect }: DestroyerCardProps) {
  const worst = useMemo(() => worstSeverity(ship), [ship]);
  const zones = useMemo(() => deriveTwinZones(ship), [ship]);
  const accent = SEVERITY_COLOR[worst];
  const critical = ship.subsystems.filter((s) => s.live && s.severity === "critical").length;
  const live = ship.subsystems.filter((s) => s.live).length;

  return (
    <motion.button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      style={{
        textAlign: "left",
        background: "var(--panel)",
        border: `1px solid ${selected ? "var(--amber)" : "var(--hair-lit)"}`,
        boxShadow: selected ? "inset 0 0 0 1px var(--amber-dim)" : "none",
        padding: 0,
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
      }}
    >
      {/* identity strip */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "9px 12px",
          borderBottom: "1px solid var(--hair)",
        }}
      >
        <span aria-hidden style={{ width: 4, alignSelf: "stretch", background: accent }} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span className="display" style={{ fontSize: 14, fontWeight: 700, letterSpacing: "-0.02em", color: "var(--ink)" }}>
              {ship.name}
            </span>
            <span className="mono" style={{ fontSize: 9.5, color: "var(--muted)", letterSpacing: "0.08em" }}>
              {ship.hull}
            </span>
          </div>
          <span className="mono" style={{ fontSize: 8.5, color: "var(--muted)", letterSpacing: "0.04em" }}>
            {ship.posture}
          </span>
        </div>
        {ship.flagship ? (
          <span
            className="mono"
            style={{ fontSize: 8, letterSpacing: "0.12em", color: "var(--amber)", border: "1px solid var(--amber-dim)", padding: "2px 6px" }}
          >
            FLAGSHIP · LIVE
          </span>
        ) : (
          <span className="mono" style={{ fontSize: 8, letterSpacing: "0.12em", color: "var(--muted)", border: "1px solid var(--hair)", padding: "2px 6px" }}>
            SISTER HULL
          </span>
        )}
      </div>

      {/* ship rendering */}
      <div
        style={{
          position: "relative",
          height: ship.flagship ? 220 : 96,
          borderBottom: "1px solid var(--hair)",
          background: "var(--base)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {ship.flagship ? (
          <ShipTwin zones={zones} conn={conn} autoRotate />
        ) : (
          <ShipSilhouette accent={accent} />
        )}
      </div>

      {/* model + signed-delta sync readout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          borderBottom: "1px solid var(--hair)",
        }}
      >
        <Stat label="LOCAL MODEL" value={`v${ship.model.version}`} sub={ship.model.local_rmse != null ? `RMSE ${ship.model.local_rmse.toFixed(5)}` : "pending"} />
        <Stat
          label="SIGNED Δ → SHORE"
          value={`${ship.sync.delta > 0 ? "+" : ""}${ship.sync.delta.toFixed(5)}`}
          sub={ship.sync.signed && ship.sync.attested ? "Ed25519 · attested" : "unattested"}
          tone={ship.sync.delta < 0 ? "nominal" : "ink"}
        />
        <Stat
          label="SUBSYSTEMS"
          value={`${live}/${ship.subsystems.length}`}
          sub={critical > 0 ? `${critical} critical` : "no critical"}
          tone={critical > 0 ? "critical" : "ink"}
        />
      </div>

      {/* the 8-subsystem city grid */}
      <div style={{ padding: 12 }}>
        <SubsystemGrid subsystems={ship.subsystems} />
      </div>
    </motion.button>
  );
}

function Stat({
  label,
  value,
  sub,
  tone = "ink",
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "ink" | "nominal" | "critical";
}) {
  const color = tone === "critical" ? "var(--critical)" : tone === "nominal" ? "var(--nominal)" : "var(--ink)";
  return (
    <div style={{ padding: "8px 11px", borderRight: "1px solid var(--hair)", minWidth: 0 }}>
      <div className="eyebrow" style={{ fontSize: 8, letterSpacing: "0.1em" }}>
        {label}
      </div>
      <div className="num" style={{ fontSize: 14, fontWeight: 500, color, lineHeight: 1.2, marginTop: 3 }}>
        {value}
      </div>
      <div className="mono" style={{ fontSize: 8, color: "var(--muted)", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {sub}
      </div>
    </div>
  );
}
