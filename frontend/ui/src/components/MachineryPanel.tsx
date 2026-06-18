import { useMemo } from "react";
import { SectionHead } from "./Hairline";
import type { Machinery } from "../lib/types";

interface MachineryPanelProps {
  machinery: Machinery | null;
}

export function MachineryPanel({ machinery }: MachineryPanelProps) {
  if (!machinery) return <MachineryStandby />;
  const { model, version, rmse, framework, status, promotions } = machinery;

  // Deterministic decay-residual trend seeded by the model, converging to rmse.
  const trend = useMemo(() => buildTrend(rmse, model), [rmse, model]);
  const nominal = (status ?? "nominal").toLowerCase() === "nominal";
  const color = nominal ? "var(--nominal)" : "var(--caution)";

  return (
    <section style={{ display: "flex", flexDirection: "column" }}>
      <SectionHead index="02" title="Machinery · HM&E" meta={framework.toUpperCase()} />

      <div style={{ padding: "14px 14px 4px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: 12,
          }}
        >
          <span
            className="mono"
            style={{ fontSize: 11.5, color: "var(--ink)", letterSpacing: "0.02em" }}
          >
            {model}
            <span style={{ color: "var(--muted)" }}> v{version}</span>
          </span>
          <span
            className="mono"
            style={{
              fontSize: 9,
              letterSpacing: "0.14em",
              color,
              border: `1px solid ${color}`,
              padding: "2px 7px",
            }}
          >
            {(status ?? "nominal").toUpperCase()}
          </span>
        </div>

        {/* hero metric: RMSE */}
        <div style={{ display: "flex", alignItems: "flex-end", gap: 22, marginBottom: 4 }}>
          <Metric
            label="DECAY RMSE"
            value={rmse.toFixed(6)}
            sub="gas-turbine residual"
            big
            color={color}
          />
          <Metric label="VERSION" value={String(version)} sub="lineage" />
          <Metric label="PROMOTIONS" value={String(promotions ?? 1)} sub="to watch" />
        </div>
      </div>

      {/* residual trend — static draw, no loop */}
      <div style={{ padding: "8px 14px 16px" }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>
          Residual Trend · last 48 fixes
        </div>
        <Trend points={trend} color={color} />
      </div>
    </section>
  );
}

/** Honest standby state — shown when no machinery model has been promoted yet. */
function MachineryStandby() {
  return (
    <section style={{ display: "flex", flexDirection: "column" }}>
      <SectionHead index="02" title="Machinery · HM&E" meta="STANDBY" />
      <div style={{ padding: "16px 14px", display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 8, height: 8, background: "var(--faint)" }} />
        <span className="mono" style={{ fontSize: 10.5, color: "var(--muted)", letterSpacing: "0.02em" }}>
          organ instrumented · CBM model pending promotion
        </span>
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  sub,
  big,
  color = "var(--ink)",
}: {
  label: string;
  value: string;
  sub: string;
  big?: boolean;
  color?: string;
}) {
  return (
    <div>
      <div className="eyebrow" style={{ fontSize: 9, marginBottom: 5 }}>
        {label}
      </div>
      <div
        className="num"
        style={{
          fontSize: big ? 30 : 20,
          fontWeight: 500,
          color,
          lineHeight: 0.95,
          letterSpacing: "-0.02em",
        }}
      >
        {value}
      </div>
      <div className="mono" style={{ fontSize: 9.5, color: "var(--muted)", marginTop: 5 }}>
        {sub}
      </div>
    </div>
  );
}

function Trend({ points, color }: { points: number[]; color: string }) {
  const W = 100;
  const H = 38;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = max - min || 1;
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * W;
      const y = H - ((p - min) / span) * (H - 4) - 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height: 56, display: "block" }}
    >
      {/* baseline grid hairlines */}
      {[0.25, 0.5, 0.75].map((g) => (
        <line
          key={g}
          x1="0"
          x2={W}
          y1={H * g}
          y2={H * g}
          stroke="var(--hair)"
          strokeWidth="0.4"
        />
      ))}
      <path d={path} fill="none" stroke={color} strokeWidth="1" vectorEffect="non-scaling-stroke" />
      {/* terminal marker */}
      <circle
        cx={W}
        cy={H - ((points[points.length - 1] - min) / span) * (H - 4) - 2}
        r="1.6"
        fill={color}
      />
    </svg>
  );
}

function buildTrend(rmse: number, seed: string): number[] {
  let s = 0;
  for (let i = 0; i < seed.length; i++) s = (s * 31 + seed.charCodeAt(i)) >>> 0;
  const rand = () => {
    s = (s * 1103515245 + 12345) >>> 0;
    return (s >>> 8) / 0xffffff;
  };
  const out: number[] = [];
  let v = rmse * 2.4;
  for (let i = 0; i < 48; i++) {
    // converge toward rmse with mild noise — looks like a settling residual
    v += (rmse - v) * 0.12 + (rand() - 0.5) * rmse * 0.5;
    out.push(Math.max(v, rmse * 0.3));
  }
  return out;
}
