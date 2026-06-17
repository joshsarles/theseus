import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { useShipState } from "./hooks/useShipState";
import { GradientMesh } from "./components/GradientMesh";
import { CommandBar } from "./components/CommandBar";
import { HeroShip } from "./components/HeroShip";
import { TacticalPicture } from "./components/TacticalPicture";
import { SystemCard } from "./components/SystemCard";
import { MachineryPanel } from "./components/MachineryPanel";
import { AlertFeed } from "./components/AlertFeed";
import { RecordPanel } from "./components/RecordPanel";
import { Panel } from "./components/Panel";
import type { ReviewVerdict } from "./components/ContactAlert";

export function App() {
  const { state, conn } = useShipState();
  const [reviews, setReviews] = useState<Record<string, ReviewVerdict>>({});

  const handleReview = useCallback((id: string, verdict: ReviewVerdict) => {
    setReviews((prev) => ({ ...prev, [id]: verdict }));
  }, []);

  if (!state) {
    return (
      <>
        <GradientMesh />
        <div className="flex h-full w-full items-center justify-center">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center gap-3"
          >
            <span className="text-2xl">⚓</span>
            <span className="num animate-softPulse text-[12px] tracking-[0.28em] text-cyan/80">
              ESTABLISHING LINK TO THESEUS…
            </span>
          </motion.div>
        </div>
      </>
    );
  }

  const liveCount = state.systems.filter((s) => s.live).length;
  const pending = Object.keys(reviews).length;
  const remaining = state.human_in_command.pending - pending;

  return (
    <>
      <GradientMesh />
      <div className="flex h-full w-full flex-col">
        <CommandBar state={state} conn={conn} />

        {/* main 3-column ops grid */}
        <main className="grid min-h-0 flex-1 grid-cols-[300px_minmax(0,1fr)_390px] gap-3 p-3">
          {/* LEFT RAIL — ship systems + machinery */}
          <div className="flex min-h-0 flex-col gap-3 overflow-hidden">
            <Panel
              title="Ship Systems"
              meta={`${liveCount}/${state.systems.length} LIVE`}
              className="min-h-0 flex-1"
              bodyClassName="flex flex-col gap-2"
              scroll
              delay={0.05}
            >
              {state.systems.map((s, i) => (
                <SystemCard key={s.key} system={s} index={i} />
              ))}
            </Panel>

            <Panel
              title="Machinery · HM&E"
              meta="CBM"
              className="shrink-0"
              delay={0.12}
            >
              <MachineryPanel machinery={state.machinery} />
            </Panel>
          </div>

          {/* CENTER — hero ship + tactical */}
          <div className="flex min-h-0 flex-col gap-3 overflow-hidden">
            <HeroShip systems={state.systems} />

            <Panel
              title="Tactical Picture · Pattern-of-Life"
              meta={`${state.contacts.length} CONTACTS`}
              className="min-h-0 flex-1"
              bodyClassName="p-0"
              delay={0.1}
            >
              <div className="h-full min-h-[220px] w-full p-1">
                <TacticalPicture contacts={state.contacts} />
              </div>
            </Panel>
          </div>

          {/* RIGHT RAIL — contact alerts + record */}
          <div className="flex min-h-0 flex-col gap-3 overflow-hidden">
            <Panel
              title="Contacts · Recommend → Decide"
              meta={`${remaining > 0 ? remaining : 0} PENDING`}
              className="min-h-0 flex-1"
              scroll
              delay={0.08}
            >
              <AlertFeed
                contacts={state.contacts}
                reviews={reviews}
                onReview={handleReview}
              />
            </Panel>

            <Panel
              title="Tamper-Evident Record"
              meta="MERKLE LOG"
              className="shrink-0"
              delay={0.14}
            >
              <RecordPanel record={state.record} />
            </Panel>
          </div>
        </main>

        {/* doctrine footer */}
        <footer className="shrink-0 px-4 py-1.5 text-center">
          <p className="num text-[9px] tracking-[0.18em] text-faint">
            DECISION-SUPPORT · HUMAN-IN-COMMAND — THESEUS RECOMMENDS, THE WATCH
            OFFICER DECIDES · NOTHING IS AUTO-ACTIONED · SWAN-SIDE / UNCLASSIFIED
            · TAMPER-EVIDENT
          </p>
        </footer>
      </div>
    </>
  );
}
