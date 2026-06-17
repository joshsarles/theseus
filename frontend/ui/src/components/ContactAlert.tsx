import { motion } from "framer-motion";
import type { Contact } from "../lib/types";
import { CONTACT_COLOR, CONTACT_LABEL } from "../lib/palette";
import { fmtPct } from "../lib/format";

export type ReviewVerdict = "accepted" | "overridden";

interface ContactAlertProps {
  contact: Contact;
  index: number;
  verdict?: ReviewVerdict;
  onReview: (id: string, verdict: ReviewVerdict) => void;
}

export function ContactAlert({
  contact,
  index,
  verdict,
  onReview,
}: ContactAlertProps) {
  const color = CONTACT_COLOR[contact.type];
  const critical = contact.type === "position_jump";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{
        type: "spring",
        stiffness: 380,
        damping: 30,
        delay: Math.min(index * 0.03, 0.4),
      }}
      className="glass relative overflow-hidden rounded-lg px-3 py-2.5"
      style={{ borderLeft: `2px solid ${color}` }}
    >
      {critical && !verdict && (
        <span
          className="pointer-events-none absolute inset-0 rounded-lg"
          style={{ boxShadow: `inset 0 0 26px ${color}40` }}
        />
      )}

      {/* header */}
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5">
          <span
            className={`h-1.5 w-1.5 rounded-full ${critical && !verdict ? "animate-softPulse" : ""}`}
            style={{ backgroundColor: color, boxShadow: `0 0 7px ${color}` }}
          />
          <span
            className="num text-[10px] font-semibold tracking-[0.12em]"
            style={{ color, textShadow: critical ? `0 0 10px ${color}99` : "none" }}
          >
            {CONTACT_LABEL[contact.type]}
          </span>
        </span>
        <span className="num text-[9px] tracking-[0.06em] text-muted">
          MMSI {contact.mmsi} · {contact.vessel_class} · {fmtPct(contact.confidence)}
        </span>
      </div>

      {/* why */}
      <p className="mt-1.5 text-[11px] leading-snug text-ink/90">
        {contact.why}
      </p>

      {/* recommendation */}
      <div className="mt-1.5 flex items-start gap-1.5">
        <span className="num text-[9px] tracking-[0.1em] text-faint">REC</span>
        <p className="num text-[10px] leading-snug text-cyan/90">
          ▸ {contact.recommended_action}
        </p>
      </div>

      {/* actions */}
      <div className="mt-2.5">
        {verdict ? (
          <div
            className="num flex items-center justify-center gap-2 rounded-md py-1.5 text-[10px] tracking-[0.16em]"
            style={{
              color: verdict === "accepted" ? "#1aba45" : "#f4a261",
              border: `1px solid ${verdict === "accepted" ? "rgba(26,186,69,0.4)" : "rgba(244,162,97,0.4)"}`,
              background:
                verdict === "accepted"
                  ? "rgba(26,186,69,0.08)"
                  : "rgba(244,162,97,0.08)",
            }}
          >
            {verdict === "accepted" ? "✓ ACCEPTED" : "↺ OVERRIDDEN"}
            <span className="text-faint">· WATCH OFFICER</span>
          </div>
        ) : (
          <div className="flex gap-2">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => onReview(contact.id, "accepted")}
              className="num flex-1 rounded-md border border-hairline bg-white/[0.03] py-1.5 text-[10px] tracking-[0.14em] text-ink/80 transition-colors hover:border-nominal/60 hover:bg-nominal/10 hover:text-nominal"
            >
              ACCEPT
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => onReview(contact.id, "overridden")}
              className="num flex-1 rounded-md border border-hairline bg-white/[0.03] py-1.5 text-[10px] tracking-[0.14em] text-ink/80 transition-colors hover:border-warning/60 hover:bg-warning/10 hover:text-warning"
            >
              OVERRIDE
            </motion.button>
          </div>
        )}
      </div>
    </motion.div>
  );
}
