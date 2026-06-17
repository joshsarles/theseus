import { useState } from "react";
import { motion } from "framer-motion";
import type { ShipSystem } from "../lib/types";
import { ShipScene } from "./ship3d/ShipScene";
import { SEVERITY_COLOR } from "../lib/palette";

interface HeroShipProps {
  systems: ShipSystem[];
}

export function HeroShip({ systems }: HeroShipProps) {
  const [ready, setReady] = useState(false);
  const live = systems.filter((s) => s.live).length;
  const critical = systems.filter((s) => s.severity === "critical").length;

  return (
    <motion.section
      initial={{ opacity: 0, scale: 0.985 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className="glass relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl"
      onAnimationComplete={() => setReady(true)}
    >
      {/* header overlay */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between p-3.5">
        <div>
          <div className="eyebrow flex items-center gap-2">
            <span className="inline-block h-[10px] w-[2px] rounded bg-cyan box-glow-cyan" />
            All-Systems Hull View
          </div>
          <div className="num mt-1 text-[10px] tracking-[0.16em] text-faint">
            7 ORGANS MONITORED · ONE BRAIN
          </div>
        </div>
        <div className="flex gap-2">
          <Stat label="LIVE" value={`${live}/${systems.length}`} tone="cyan" />
          <Stat
            label="CRITICAL"
            value={String(critical)}
            tone={critical > 0 ? "danger" : "muted"}
          />
        </div>
      </div>

      {/* corner ticks for that mission-control framing */}
      <Corner className="left-2 top-2 border-l border-t" />
      <Corner className="right-2 top-2 border-r border-t" />
      <Corner className="left-2 bottom-2 border-l border-b" />
      <Corner className="right-2 bottom-2 border-r border-b" />

      {/* radial floor glow behind ship */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(60% 55% at 50% 62%, rgba(0,217,255,0.10) 0%, rgba(0,217,255,0) 70%)",
        }}
      />

      {/* the 3D canvas — absolutely filled so R3F always measures a real size */}
      <div className="absolute inset-0">
        <ShipScene systems={systems} />
      </div>

      {/* loading shimmer until the canvas is up */}
      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="num animate-softPulse text-[11px] tracking-[0.2em] text-cyan/70">
            INITIALIZING HULL MODEL…
          </span>
        </div>
      )}

      {/* legend */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex items-center justify-center gap-4 p-3">
        {(
          [
            ["nominal", "NOMINAL"],
            ["critical", "CRITICAL"],
            ["standby", "STANDBY"],
          ] as const
        ).map(([sev, label]) => (
          <div key={sev} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{
                backgroundColor: SEVERITY_COLOR[sev],
                boxShadow:
                  sev !== "standby"
                    ? `0 0 8px ${SEVERITY_COLOR[sev]}`
                    : "none",
                opacity: sev === "standby" ? 0.6 : 1,
              }}
            />
            <span className="num text-[9px] tracking-[0.14em] text-faint">
              {label}
            </span>
          </div>
        ))}
      </div>
    </motion.section>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "cyan" | "danger" | "muted";
}) {
  const color =
    tone === "cyan"
      ? "text-cyan text-glow-cyan"
      : tone === "danger"
        ? "text-danger text-glow-danger"
        : "text-muted";
  return (
    <div className="glass rounded-md px-2.5 py-1.5 text-right">
      <div className="num text-[8px] tracking-[0.18em] text-faint">{label}</div>
      <div className={`num text-[15px] font-semibold leading-tight ${color}`}>
        {value}
      </div>
    </div>
  );
}

function Corner({ className }: { className: string }) {
  return (
    <span
      className={`pointer-events-none absolute z-10 h-4 w-4 border-cyan/30 ${className}`}
    />
  );
}
