import { useMemo } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import type { Machinery } from "../lib/types";
import { COLORS } from "../lib/palette";

interface MachineryPanelProps {
  machinery: Machinery;
}

/** Synthesizes a smooth gas-turbine decay-coefficient trend seeded by the live RMSE. */
function useTrend(rmse: number) {
  return useMemo(() => {
    const n = 40;
    const base = 1.0;
    const pts: { t: number; decay: number; rmse: number }[] = [];
    // deterministic pseudo-random walk so it's stable between renders
    let seed = Math.floor(rmse * 1e6) || 7;
    const rand = () => {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return seed / 0x7fffffff;
    };
    let v = base;
    for (let i = 0; i < n; i++) {
      v -= 0.0009 + rand() * 0.0006; // gentle downward decay
      const jitter = (rand() - 0.5) * 0.004;
      pts.push({
        t: i,
        decay: +(v + jitter).toFixed(4),
        rmse: +(rmse * (0.85 + rand() * 0.4)).toFixed(5),
      });
    }
    return pts;
  }, [rmse]);
}

export function MachineryPanel({ machinery }: MachineryPanelProps) {
  const trend = useTrend(machinery.rmse);
  // RMSE health: lower is better. Map against a 0.02 "concern" ceiling.
  const ceiling = 0.02;
  const health = Math.max(0, Math.min(1, 1 - machinery.rmse / ceiling));
  const healthPct = Math.round(health * 100);
  const ring = 2 * Math.PI * 26;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-stretch gap-3">
        {/* RMSE health gauge */}
        <div className="relative flex h-[78px] w-[78px] shrink-0 items-center justify-center">
          <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
            <circle
              cx="32"
              cy="32"
              r="26"
              fill="none"
              stroke="rgba(255,255,255,0.08)"
              strokeWidth="5"
            />
            <circle
              cx="32"
              cy="32"
              r="26"
              fill="none"
              stroke={COLORS.nominal}
              strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray={ring}
              strokeDashoffset={ring * (1 - health)}
              style={{
                transition: "stroke-dashoffset 900ms cubic-bezier(.22,1,.36,1)",
                filter: `drop-shadow(0 0 6px ${COLORS.nominal})`,
              }}
            />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className="num text-[16px] font-semibold leading-none text-nominal">
              {healthPct}
            </span>
            <span className="num text-[7px] tracking-[0.12em] text-faint">
              HEALTH
            </span>
          </div>
        </div>

        {/* model metadata */}
        <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="num text-[12px] font-medium text-ink/95">
              {machinery.model}
            </span>
            <span className="num text-[9px] tracking-[0.1em] text-cyan">
              v{machinery.version}
            </span>
          </div>
          <Metric label="RMSE" value={machinery.rmse.toFixed(6)} glow />
          <div className="flex justify-between gap-2">
            <Metric label="FRAMEWORK" value={machinery.framework} />
            <Metric
              label="PROMOTED"
              value={`${machinery.promotions}×`}
            />
          </div>
        </div>
      </div>

      {/* decay trend sparkline */}
      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="num text-[8px] tracking-[0.14em] text-faint">
            GAS-TURBINE DECAY COEFFICIENT · CBM
          </span>
          <span className="num text-[8px] tracking-[0.12em] text-nominal">
            NOMINAL
          </span>
        </div>
        <div className="h-[56px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={trend}
              margin={{ top: 2, right: 0, bottom: 0, left: 0 }}
            >
              <defs>
                <linearGradient id="decayFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.cyan} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={COLORS.cyan} stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis hide domain={["dataMin - 0.005", "dataMax + 0.005"]} />
              <Tooltip
                cursor={{ stroke: COLORS.cyan, strokeOpacity: 0.3 }}
                contentStyle={{
                  background: "rgba(12,20,40,0.92)",
                  border: "1px solid rgba(0,217,255,0.3)",
                  borderRadius: 8,
                  fontFamily: "Geist Mono, monospace",
                  fontSize: 10,
                  padding: "4px 8px",
                }}
                labelStyle={{ display: "none" }}
                itemStyle={{ color: COLORS.cyan }}
                formatter={(v: number) => [v.toFixed(4), "decay"]}
              />
              <Area
                type="monotone"
                dataKey="decay"
                stroke={COLORS.cyan}
                strokeWidth={1.6}
                fill="url(#decayFill)"
                dot={false}
                isAnimationActive
                animationDuration={900}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  glow,
}: {
  label: string;
  value: string;
  glow?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="num text-[8px] tracking-[0.14em] text-faint">
        {label}
      </span>
      <span
        className={`num text-[10.5px] ${glow ? "text-cyan text-glow-cyan" : "text-ink/85"}`}
      >
        {value}
      </span>
    </div>
  );
}
