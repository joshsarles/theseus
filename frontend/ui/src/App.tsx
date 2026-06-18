import { useCallback, useMemo, useState } from "react";
import { useShipState } from "./hooks/useShipState";
import { useFleetState } from "./hooks/useFleetState";
import { CommandHeader } from "./components/CommandHeader";
import { SimFeedBanner } from "./components/SimFeedBanner";
import { OperationsView } from "./components/OperationsView";
import { FleetFlywheel } from "./components/fleet/FleetFlywheel";
import { mintDecisionLeaf, parseRecordMessage } from "./lib/format";
import type { Leaf, SceneMode, Verdict } from "./lib/types";

export function App() {
  const { state, conn, refetch } = useShipState();
  const { fleet, conn: fleetConn } = useFleetState();
  const [mode, setMode] = useState<SceneMode>("operations");
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
      // Risk #7: the spine must tick on the same beat the officer clicks — pull
      // the authoritative leaf_count NOW instead of waiting up to 4s for the
      // next poll, which reads on stage as "the seal didn't work".
      if (serverSealed) refetch();
    },
    [state?.record.leaf_count, merkleSeed, refetch],
  );

  // Risk #1: a giant red SIM-FEED bar shows whenever the link is not truly live.
  // In FLEET mode the banner tracks the fleet endpoint's connection instead.
  const activeConn = mode === "fleet" ? fleetConn : conn;
  const simBannerActive = activeConn !== "live";

  return (
    <>
      <SimFeedBanner conn={activeConn} />
      <div className="vignette" />
      <div className="grain" />
      <div
        style={{
          position: "relative",
          zIndex: 1,
          height: "100vh",
          paddingTop: simBannerActive ? 62 : 0,
          display: "flex",
          flexDirection: "column",
          background: "var(--base)",
        }}
      >
        {state ? <CommandHeader state={state} conn={conn} mode={mode} onMode={setMode} /> : null}

        {state ? (
          mode === "operations" ? (
            <OperationsView
              state={state}
              conn={conn}
              selectedId={selectedId}
              onSelect={setSelectedId}
              localLeaves={localLeaves}
              onDecision={onDecision}
            />
          ) : fleet ? (
            <FleetFlywheel fleet={fleet} conn={fleetConn} />
          ) : (
            <Booting label="LINKING TO FLEET BRAIN …" />
          )
        ) : (
          <Booting label="LINKING TO THESEUS …" />
        )}
      </div>
    </>
  );
}

function Booting({ label }: { label: string }) {
  return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="mono" style={{ fontSize: 12, color: "var(--muted)", letterSpacing: "0.16em" }}>
        {label}
      </div>
    </div>
  );
}
