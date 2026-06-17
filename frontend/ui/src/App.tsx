import { useCallback, useMemo, useState } from "react";
import { useShipState } from "./hooks/useShipState";
import { CommandHeader } from "./components/CommandHeader";
import { SystemsColumn } from "./components/SystemsColumn";
import { MachineryPanel } from "./components/MachineryPanel";
import { TacticalPicture } from "./components/TacticalPicture";
import { ContactsPanel } from "./components/ContactsPanel";
import { RecordSpine } from "./components/RecordSpine";
import { mintDecisionLeaf, parseRecordMessage } from "./lib/format";
import type { Leaf, Verdict } from "./lib/types";

export function App() {
  const { state, conn } = useShipState();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [localLeaves, setLocalLeaves] = useState<Leaf[]>([]);

  const merkleSeed = useMemo(() => {
    const { merkle, head } = parseRecordMessage(state?.record.message ?? "");
    return (merkle ?? head ?? "theseus").slice(0, 12);
  }, [state?.record.message]);

  const onDecision = useCallback(
    (contactId: string, verdict: Verdict, serverSealed: boolean) => {
      setLocalLeaves((prev) => {
        const prevTotal = (state?.record.leaf_count ?? 0) + prev.length;
        const leaf = mintDecisionLeaf(prevTotal, contactId, verdict, merkleSeed);
        leaf.local = !serverSealed;
        return [...prev, leaf];
      });
    },
    [state?.record.leaf_count, merkleSeed],
  );

  return (
    <>
      <div className="vignette" />
      <div className="grain" />
      <div
        style={{
          position: "relative",
          zIndex: 1,
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          background: "var(--base)",
        }}
      >
        {state ? <CommandHeader state={state} conn={conn} /> : null}

        {state ? (
          <main
            style={{
              flex: 1,
              minHeight: 0,
              display: "grid",
              // asymmetric, content-driven: instrument rail · tactical theatre · record spine
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

            {/* CENTER — tactical theatre over the human-in-command queue */}
            <div
              style={{
                display: "grid",
                gridTemplateRows: "minmax(300px, 1.2fr) minmax(0, 1fr)",
                minHeight: 0,
              }}
            >
              <div
                style={{
                  borderBottom: "1px solid var(--hair-lit)",
                  minHeight: 0,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <TacticalPicture
                  contacts={state.contacts}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              </div>
              <div style={{ minHeight: 0, display: "flex", flexDirection: "column" }}>
                <ContactsPanel
                  contacts={state.contacts}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  onDecision={onDecision}
                />
              </div>
            </div>

            {/* RIGHT — the differentiator: tamper-evident record spine */}
            <RecordSpine record={state.record} localLeaves={localLeaves} />
          </main>
        ) : (
          <Booting />
        )}
      </div>
    </>
  );
}

function Booting() {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div className="mono" style={{ fontSize: 12, color: "var(--muted)", letterSpacing: "0.16em" }}>
        LINKING TO THESEUS …
      </div>
    </div>
  );
}
