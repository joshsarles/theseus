import { motion } from "framer-motion";
import type { RecordState } from "../lib/types";
import { parseRecordMessage } from "../lib/format";
import { COLORS } from "../lib/palette";

export function RecordPanel({ record }: { record: RecordState }) {
  const ok = record.verify_ok;
  const { head, merkle } = parseRecordMessage(record.message);
  const eventEntries = Object.entries(record.events ?? {});

  return (
    <div className="flex flex-col gap-3">
      {/* verdict banner */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="num flex items-center justify-center gap-2 rounded-lg py-2 text-[12px] font-semibold tracking-[0.16em]"
        style={{
          color: ok ? COLORS.nominal : COLORS.danger,
          border: `1px solid ${ok ? "rgba(26,186,69,0.45)" : "rgba(230,57,70,0.5)"}`,
          background: ok ? "rgba(26,186,69,0.08)" : "rgba(230,57,70,0.10)",
          boxShadow: ok
            ? "0 0 18px rgba(26,186,69,0.25)"
            : "0 0 22px rgba(230,57,70,0.4)",
        }}
      >
        <span
          className={`h-2 w-2 rounded-full ${ok ? "" : "animate-softPulse"}`}
          style={{
            backgroundColor: ok ? COLORS.nominal : COLORS.danger,
            boxShadow: `0 0 8px ${ok ? COLORS.nominal : COLORS.danger}`,
          }}
        />
        {ok ? "CHAIN VERIFIED · PASS" : `CHAIN SNAP @ ${record.first_bad_leaf}`}
      </motion.div>

      {/* hashes */}
      <div className="grid grid-cols-2 gap-2">
        <HashCell label="LEAVES" value={String(record.leaf_count)} />
        <HashCell label="MERKLE ROOT" value={merkle ?? "—"} mono />
        <HashCell label="CHAIN HEAD" value={head ?? "—"} mono />
        <HashCell label="INTEGRITY" value={ok ? "INTACT" : "BROKEN"} tone={ok} />
      </div>

      {/* event tape */}
      <div>
        <div className="num mb-1.5 text-[8px] tracking-[0.14em] text-faint">
          LOGGED EVENTS
        </div>
        <div className="flex flex-wrap gap-1.5">
          {eventEntries.map(([k, n]) => (
            <span
              key={k}
              className="num rounded border border-hairline bg-white/[0.03] px-1.5 py-0.5 text-[9px] tracking-[0.04em] text-muted"
            >
              {k.replace(/_/g, " ")}
              <span className="ml-1 text-cyan">{n}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function HashCell({
  label,
  value,
  mono,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: boolean;
}) {
  const color =
    tone === undefined
      ? "text-ink/90"
      : tone
        ? "text-nominal"
        : "text-danger";
  return (
    <div className="rounded-md border border-hairline bg-white/[0.02] px-2 py-1.5">
      <div className="num text-[7.5px] tracking-[0.14em] text-faint">
        {label}
      </div>
      <div
        className={`num mt-0.5 text-[10px] ${color} ${mono ? "break-all" : ""}`}
      >
        {value}
      </div>
    </div>
  );
}
