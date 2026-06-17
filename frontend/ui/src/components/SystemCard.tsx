import { motion } from "framer-motion";
import type { ShipSystem } from "../lib/types";
import { SEVERITY_COLOR } from "../lib/palette";

const SEV_LABEL: Record<ShipSystem["severity"], string> = {
  nominal: "NOMINAL",
  warning: "WARNING",
  critical: "CRITICAL",
  standby: "STANDBY",
};

export function SystemCard({
  system,
  index,
}: {
  system: ShipSystem;
  index: number;
}) {
  const color = SEVERITY_COLOR[system.severity];
  const live = system.live && system.severity !== "standby";
  const critical = system.severity === "critical";

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay: 0.04 * index, ease: "easeOut" }}
      className={`glass glass-hover relative overflow-hidden rounded-lg px-3 py-2.5 ${
        live ? "" : "opacity-[0.72]"
      }`}
      style={{
        borderLeft: `2px solid ${live ? color : "rgba(90,106,138,0.5)"}`,
      }}
    >
      {/* critical edge glow */}
      {critical && (
        <span
          className="pointer-events-none absolute inset-0 rounded-lg"
          style={{ boxShadow: `inset 0 0 22px ${color}33` }}
        />
      )}

      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium tracking-[0.02em] text-ink/95">
          {system.label}
        </span>
        <span className="relative flex items-center gap-1.5">
          {live && (
            <span
              className={`h-1.5 w-1.5 rounded-full ${critical ? "animate-softPulse" : ""}`}
              style={{
                backgroundColor: color,
                boxShadow: `0 0 7px ${color}`,
              }}
            />
          )}
          <span
            className="num text-[9px] tracking-[0.14em]"
            style={{ color: live ? color : "#5a6a8a" }}
          >
            {live ? SEV_LABEL[system.severity] : "STANDBY"}
          </span>
        </span>
      </div>
      <p className="num mt-1 text-[10.5px] leading-snug text-muted">
        {system.detail}
      </p>
    </motion.div>
  );
}
