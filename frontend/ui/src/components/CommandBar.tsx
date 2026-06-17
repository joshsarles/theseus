import { motion } from "framer-motion";
import type { ShipState } from "../lib/types";
import type { ConnState } from "../hooks/useShipState";
import { COLORS } from "../lib/palette";
import { useUtcClock } from "../hooks/useUtcClock";
import { StatusChip } from "./StatusChip";

interface CommandBarProps {
  state: ShipState;
  conn: ConnState;
}

export function CommandBar({ state, conn }: CommandBarProps) {
  const clock = useUtcClock();

  const hullAttention =
    state.systems.some((s) => s.severity === "critical") ||
    state.contacts.some((c) => c.type === "position_jump");

  const connLabel: Record<ConnState, string> = {
    connecting: "LINK ··· SYNC",
    live: "LINK · LIVE",
    stale: "LINK · STALE",
    mock: "LINK · OFFLINE",
  };
  const connColor: Record<ConnState, string> = {
    connecting: COLORS.warning,
    live: COLORS.cyan,
    stale: COLORS.warning,
    mock: COLORS.danger,
  };

  return (
    <header className="relative z-20 flex h-[58px] shrink-0 items-center gap-5 px-5 hairline-b">
      {/* wordmark */}
      <div className="flex items-baseline gap-3">
        <motion.span
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="select-none text-[15px] leading-none"
          style={{ filter: "drop-shadow(0 0 10px rgba(0,217,255,0.5))" }}
        >
          ⚓
        </motion.span>
        <motion.h1
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.05 }}
          className="num text-[19px] font-semibold tracking-[0.34em] text-ink"
        >
          THESEUS
        </motion.h1>
      </div>

      <div className="hidden h-5 w-px bg-hairline md:block" />
      <span className="eyebrow hidden md:block">
        onboard ship-systems decision-support
      </span>

      <div className="flex-1" />

      <div className="flex items-center gap-2.5">
        {/* DDIL / air-gap comms posture — always pulsing to signal contested-link operation */}
        <StatusChip
          dotColor={COLORS.warning}
          pulse
          tone="default"
          label={
            <span className="text-warning">COMMS · DDIL / AIR-GAP</span>
          }
        />
        <StatusChip
          dotColor={hullAttention ? COLORS.warning : COLORS.nominal}
          tone={hullAttention ? "default" : "nominal"}
          label={`HULL · ${hullAttention ? "ATTENTION" : "NOMINAL"}`}
        />
        <StatusChip
          dotColor={
            state.record.verify_ok ? COLORS.nominal : COLORS.danger
          }
          tone={state.record.verify_ok ? "nominal" : "danger"}
          label={state.record.verify_ok ? "RECORD ✓" : "RECORD ✕"}
        />
        <StatusChip
          dotColor={connColor[conn]}
          pulse={conn === "connecting"}
          label={connLabel[conn]}
        />
        <div className="glass num rounded-md px-3 py-[7px] text-[13px] tracking-[0.12em] text-cyan text-glow-cyan">
          {clock}
          <span className="ml-0.5 text-cyan/60">Z</span>
        </div>
      </div>
    </header>
  );
}
