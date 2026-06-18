import { useMemo, useState } from "react";
import { SystemsColumn } from "./SystemsColumn";
import { MachineryPanel } from "./MachineryPanel";
import { TacticalPicture } from "./TacticalPicture";
import { ContactsPanel } from "./ContactsPanel";
import { RecordSpine } from "./RecordSpine";
import { ShipTwin } from "./twin/ShipTwin";
import { deriveZones } from "../lib/twin";
import type { Leaf, ShipState, Verdict } from "../lib/types";
import type { ConnState } from "../hooks/useShipState";

interface OperationsViewProps {
  state: ShipState;
  conn: ConnState;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  localLeaves: Leaf[];
  onDecision: (contactId: string, verdict: Verdict, serverSealed: boolean) => void;
}

type CenterTab = "twin" | "tactical";

/**
 * The working-system picture, with the 3D digital twin as the hero. Keeps the
 * bar-clearing CIC-v5 instrument rail (systems · machinery) and record spine,
 * and puts the orbitable warship twin at the centre. A sub-tab swaps the centre
 * hero between the TWIN and the AIS TACTICAL plot without losing the rest of the
 * board.
 */
export function OperationsView({
  state,
  conn,
  selectedId,
  onSelect,
  localLeaves,
  onDecision,
}: OperationsViewProps) {
  const [tab, setTab] = useState<CenterTab>("twin");
  const [orbiting, setOrbiting] = useState(false);
  const zones = useMemo(() => deriveZones(state.systems), [state.systems]);
  const twinConn = conn === "connecting" ? "connecting" : conn;

  return (
    <main
      style={{
        flex: 1,
        minHeight: 0,
        display: "grid",
        gridTemplateColumns: "320px minmax(0, 1fr) 340px",
      }}
    >
      {/* LEFT — ship instruments (systems over machinery) */}
      <div
        style={{
          display: "grid",
          gridTemplateRows: "1fr auto",
          borderRight: "1px solid var(--hair-lit)",
          minHeight: 0,
          background: "var(--panel)",
        }}
      >
        <div style={{ borderBottom: "1px solid var(--hair-lit)", minHeight: 0, overflow: "hidden", display: "flex" }}>
          <div style={{ flex: 1, minHeight: 0 }}>
            <SystemsColumn systems={state.systems} />
          </div>
        </div>
        <MachineryPanel machinery={state.machinery} />
      </div>

      {/* CENTER — the digital-twin hero over the human-in-command queue */}
      <div style={{ display: "grid", gridTemplateRows: "minmax(320px, 1.25fr) minmax(0, 1fr)", minHeight: 0 }}>
        <div
          style={{
            borderBottom: "1px solid var(--hair-lit)",
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            position: "relative",
            background: "var(--base)",
          }}
        >
          {/* centre hero header + sub-tabs */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "10px 14px",
              borderBottom: "1px solid var(--hair)",
              zIndex: 2,
            }}
          >
            <span className="mono" style={{ fontSize: 10, color: "var(--muted)", letterSpacing: "0.1em" }}>
              {tab === "twin" ? "03" : "03"}
            </span>
            <span
              className="display"
              style={{ fontSize: 12.5, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--ink)" }}
            >
              {tab === "twin" ? "Ship · Digital Twin" : "Tactical Picture · AIS"}
            </span>
            <div style={{ marginLeft: "auto", display: "flex", border: "1px solid var(--hair)" }}>
              <HeroTab active={tab === "twin"} onClick={() => setTab("twin")}>
                TWIN
              </HeroTab>
              <HeroTab active={tab === "tactical"} onClick={() => setTab("tactical")}>
                TACTICAL
              </HeroTab>
            </div>
          </div>

          <div style={{ position: "relative", flex: 1, minHeight: 0 }}>
            {tab === "twin" ? (
              <div
                style={{ position: "absolute", inset: 0 }}
                onPointerDown={() => setOrbiting(true)}
                onPointerUp={() => setOrbiting(false)}
                onPointerLeave={() => setOrbiting(false)}
              >
                <ShipTwin zones={zones} autoRotate={!orbiting} conn={twinConn} />
              </div>
            ) : (
              <TacticalPicture contacts={state.contacts} selectedId={selectedId} onSelect={onSelect} />
            )}
          </div>
        </div>

        <div style={{ minHeight: 0, display: "flex", flexDirection: "column" }}>
          <ContactsPanel
            contacts={state.contacts}
            selectedId={selectedId}
            onSelect={onSelect}
            onDecision={onDecision}
          />
        </div>
      </div>

      {/* RIGHT — the differentiator: tamper-evident record spine */}
      <RecordSpine record={state.record} localLeaves={localLeaves} />
    </main>
  );
}

function HeroTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        fontFamily: "var(--mono)",
        fontSize: 9.5,
        letterSpacing: "0.12em",
        padding: "5px 13px",
        background: active ? "var(--amber)" : "transparent",
        color: active ? "#0a0c10" : "var(--ink-dim)",
        border: "none",
        cursor: "pointer",
        fontWeight: 500,
      }}
    >
      {children}
    </button>
  );
}
