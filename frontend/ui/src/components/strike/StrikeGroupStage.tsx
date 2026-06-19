import { useLayoutEffect, useMemo, useRef } from "react";
import { gsap } from "gsap";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";
import type { DestroyerState } from "../../lib/types";
import type { DestroyerConn } from "../../hooks/useDestroyerState";

gsap.registerPlugin(MotionPathPlugin);

interface StrikeGroupStageProps {
  destroyer: DestroyerState;
  conn: DestroyerConn;
}

const W = 1280;
const H = 380;

/**
 * The strike-group sync picture: every hull (left, in formation) pushes a SIGNED
 * model delta to the SHORE FLEET BRAIN (Node 3, right). GSAP animates the signed
 * packets travelling the trust paths; the poisoned/unattested delta races at the
 * provenance gate, is DENIED, and snaps back — it never touches the merge.
 *
 *   hulls ──signed delta──▸ provenance gate ▸ FedAvg ▸ eval gate ▸ NODE-3
 *   poison ──forged──▸ ✕ REJECTED at the gate
 *
 * Framed: human-authorized · eval-gated · provenance-attested. Never "self-updating".
 */
export function StrikeGroupStage({ destroyer, conn }: StrikeGroupStageProps) {
  const root = useRef<SVGSVGElement>(null);

  const hulls = destroyer.destroyers;
  const shore = destroyer.shore;
  const poison = destroyer.rejected[0];

  // formation anchors on the left, evenly spaced
  const hullX = 150;
  const gateX = 720;
  const gateY = H / 2;
  const brainX = 1050;
  const brainY = H / 2;
  const poisonY = H - 46;

  const hullPts = useMemo(
    () => hulls.map((_, i) => ({ x: hullX, y: 70 + i * ((H - 150) / Math.max(1, hulls.length - 1)) })),
    [hulls.length],
  );

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const ctx = gsap.context(() => {
      // signed-delta packets: hull → gate → brain (loop, staggered)
      gsap.utils.toArray<SVGCircleElement>("[data-delta-packet]").forEach((p, i) => {
        gsap.fromTo(
          p,
          { motionPath: { path: `#delta-path-${i}`, start: 0, end: 0 }, opacity: 0 },
          {
            motionPath: { path: `#delta-path-${i}`, start: 0, end: 1 },
            duration: 2.2,
            ease: "power1.inOut",
            repeat: -1,
            repeatDelay: 0.9,
            delay: i * 0.45,
            keyframes: { opacity: [0, 1, 1, 0] },
          },
        );
      });

      // poison packet: races to the gate, DENIED, snaps back
      const poisonEl = el.querySelector<SVGCircleElement>("[data-poison-packet]");
      if (poisonEl) {
        const tl = gsap.timeline({ repeat: -1, repeatDelay: 0.8 });
        tl.set(poisonEl, { opacity: 0 })
          .fromTo(
            poisonEl,
            { motionPath: { path: "#poison-path", start: 0, end: 0 }, opacity: 0 },
            { motionPath: { path: "#poison-path", start: 0, end: 0.66 }, opacity: 1, duration: 1.3, ease: "power2.in" },
          )
          .to(poisonEl, { scale: 1.7, duration: 0.12, transformOrigin: "center" })
          .to(poisonEl, { motionPath: { path: "#poison-path", start: 0.66, end: 0 }, scale: 1, opacity: 0, duration: 0.7, ease: "power2.out" });

        const denied = el.querySelector("[data-denied-stamp]");
        if (denied) {
          gsap.timeline({ repeat: -1, repeatDelay: 0.8, delay: 1.3 })
            .fromTo(denied, { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: 0.16, transformOrigin: "center" })
            .to(denied, { opacity: 0.9, duration: 0.8 })
            .to(denied, { opacity: 0, duration: 0.5 });
        }
      }

      // improved-model push-back: brain → fleet manifold (returns to every hull)
      gsap.utils.toArray<SVGCircleElement>("[data-push-packet]").forEach((p, i) => {
        gsap.fromTo(
          p,
          { motionPath: { path: `#push-path-${i}`, start: 0, end: 0 }, opacity: 0 },
          {
            motionPath: { path: `#push-path-${i}`, start: 0, end: 1 },
            duration: 2.6,
            ease: "power1.inOut",
            repeat: -1,
            repeatDelay: 1.1,
            delay: 1.6 + i * 0.35,
            keyframes: { opacity: [0, 1, 1, 0] },
          },
        );
      });

      gsap.to("[data-brain-core]", { opacity: 0.45, duration: 1.6, repeat: -1, yoyo: true, ease: "sine.inOut" });
    }, root);
    return () => ctx.revert();
  }, [hulls.length]);

  return (
    <svg
      ref={root}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
    >
      <defs>
        {hullPts.map((p, i) => (
          <path key={i} id={`delta-path-${i}`} d={curve(p.x + 70, p.y, brainX - 64, brainY)} fill="none" />
        ))}
        <path id="poison-path" d={curve(hullX + 70, poisonY, gateX - 6, gateY + 36)} fill="none" />
        {hullPts.map((p, i) => (
          <path key={i} id={`push-path-${i}`} d={curve(brainX + 64, brainY, p.x + 70, p.y)} fill="none" />
        ))}
      </defs>

      {/* static trust lines hull → brain */}
      {hullPts.map((p, i) => (
        <path key={i} d={curve(p.x + 70, p.y, brainX - 64, brainY)} fill="none" stroke="#2b3138" strokeWidth={1} />
      ))}
      {/* static push-back lines (improved model returns) */}
      {hullPts.map((p, i) => (
        <path key={`pb-${i}`} d={curve(brainX + 64, brainY, p.x + 70, p.y)} fill="none" stroke="#1e2a20" strokeWidth={1} strokeDasharray="2 6" />
      ))}
      {/* poison line — red, denied */}
      <path d={curve(hullX + 70, poisonY, gateX - 6, gateY + 36)} fill="none" stroke="#5a2528" strokeWidth={1} strokeDasharray="4 4" />

      {/* animated packets */}
      {hullPts.map((_, i) => (
        <circle key={i} data-delta-packet r={4.5} fill="#d4a000" />
      ))}
      {hullPts.map((_, i) => (
        <circle key={`pp-${i}`} data-push-packet r={4.5} fill="#3fb950" />
      ))}
      <circle data-poison-packet r={4.5} fill="#e5484d" />

      {/* LEFT: hulls in formation */}
      {hulls.map((d, i) => (
        <HullNode key={d.hull} x={hullPts[i].x} y={hullPts[i].y} name={d.name} hull={d.hull} flagship={d.flagship} delta={d.sync.delta} status={d.sync.status} />
      ))}

      {/* poison node */}
      <PoisonNode x={hullX} y={poisonY} keyid={poison?.keyid ?? "UNREG"} />

      {/* provenance gate (intercept) */}
      <GateGlyph x={gateX} y={gateY} />

      {/* RIGHT: shore fleet brain (Node 3) */}
      <ShoreBrain x={brainX} y={brainY} shore={shore} />

      {/* flow labels */}
      <FlowLabel x={(hullX + gateX) / 2} y={50} text="① EACH HULL LEARNS LOCAL · DDIL" />
      <FlowLabel x={(hullX + gateX) / 2} y={66} text="signs a model delta ▸ never raw data" sub />
      <FlowLabel x={gateX - 30} y={H - 14} text="② PROVENANCE GATE ▸ FEDAVG ▸ EVAL GATE" />
      <FlowLabel x={(gateX + brainX) / 2 + 40} y={H - 14} text="③ IMPROVED MODEL PUSHED BACK TO EVERY HULL" sub />

      <text x={W - 12} y={H - 8} textAnchor="end" fill="#646b75" fontSize={9} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        {conn === "live" ? "◆ STRIKE-GROUP RECORD LIVE · /api/destroyer" : "◆ STRIKE-GROUP · SIM FIXTURE"}
      </text>
    </svg>
  );
}

/* ---------------- sub-glyphs ---------------- */

function HullNode({
  x,
  y,
  name,
  hull,
  flagship,
  delta,
  status,
}: {
  x: number;
  y: number;
  name: string;
  hull: string;
  flagship: boolean;
  delta: number;
  status: string;
}) {
  const accent = flagship ? "#d4a000" : "#3fb950";
  const pending = status === "pending";
  return (
    <g transform={`translate(${x},${y})`}>
      <rect x={-70} y={-30} width={140} height={60} fill="#0d1117" stroke={flagship ? "#6f5410" : "#2b3138"} strokeWidth={1} />
      <rect x={-70} y={-30} width={3} height={60} fill={accent} />
      <ShipGlyph cx={-48} cy={-10} color={flagship ? "#d4a000" : "#9aa0a8"} />
      <text x={-26} y={-13} fill="#e6e8ea" fontSize={11} fontWeight={600} fontFamily="Space Grotesk, sans-serif" letterSpacing="0.3">
        {name.length > 13 ? name.slice(0, 12) + "…" : name}
      </text>
      <text x={-26} y={-1} fill="#646b75" fontSize={8} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        {hull} {flagship ? "· FLAGSHIP" : ""}
      </text>
      <text x={-60} y={20} fill={pending ? "#9aa0a8" : "#d4a000"} fontSize={10} fontFamily="JetBrains Mono, monospace">
        {delta > 0 ? "+" : ""}{delta.toFixed(5)}
      </text>
      <g transform="translate(48,18)">
        <rect x={-2} y={-7} width={26} height={13} fill="none" stroke={pending ? "#6f5410" : "#3fb950"} strokeWidth={0.8} />
        <text x={11} y={2.5} textAnchor="middle" fill={pending ? "#d4a000" : "#3fb950"} fontSize={6.5} fontFamily="JetBrains Mono, monospace" letterSpacing="0.4">
          {pending ? "QUEUED" : "SIGNED"}
        </text>
      </g>
    </g>
  );
}

function PoisonNode({ x, y, keyid }: { x: number; y: number; keyid: string }) {
  return (
    <g transform={`translate(${x},${y})`}>
      <rect x={-70} y={-24} width={140} height={48} fill="#1a0d0f" stroke="#5a2528" strokeWidth={1} />
      <rect x={-70} y={-24} width={3} height={48} fill="#e5484d" />
      <ShipGlyph cx={-48} cy={-6} color="#e5484d" />
      <text x={-26} y={-8} fill="#e5484d" fontSize={10} fontWeight={600} fontFamily="Space Grotesk, sans-serif" letterSpacing="0.3">
        POISON NODE
      </text>
      <text x={-26} y={4} fill="#9a6468" fontSize={7.5} fontFamily="JetBrains Mono, monospace">
        keyid={keyid}
      </text>
      <text x={-60} y={18} fill="#9a6468" fontSize={7} fontFamily="JetBrains Mono, monospace">
        forged delta · captured hull
      </text>
    </g>
  );
}

function GateGlyph({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x},${y})`}>
      {/* gate frame */}
      <line x1={0} y1={-70} x2={0} y2={70} stroke="#2a313a" strokeWidth={1} strokeDasharray="3 4" />
      <text x={0} y={-78} textAnchor="middle" fill="#9aa0a8" fontSize={8.5} fontFamily="JetBrains Mono, monospace" letterSpacing="1.2">
        PROVENANCE GATE
      </text>
      {/* DENIED stamp flashes when poison hits */}
      <g data-denied-stamp opacity={0} transform="translate(0,40)">
        <rect x={-42} y={-14} width={84} height={28} fill="none" stroke="#e5484d" strokeWidth={1.5} />
        <text x={0} y={5} textAnchor="middle" fill="#e5484d" fontSize={12} fontWeight={700} fontFamily="Space Grotesk, sans-serif" letterSpacing="2">
          DENIED
        </text>
      </g>
      <text x={0} y={74} textAnchor="middle" fill="#9a6468" fontSize={7.5} fontFamily="JetBrains Mono, monospace" letterSpacing="0.6">
        keyid ∉ trust registry
      </text>
    </g>
  );
}

function ShoreBrain({ x, y, shore }: { x: number; y: number; shore: DestroyerState["shore"] }) {
  const ok = shore.eval_gate_pass;
  return (
    <g transform={`translate(${x},${y})`}>
      <circle r={64} fill="#0d1117" stroke="#2b3138" strokeWidth={1} />
      <circle data-brain-core r={64} fill="none" stroke="#d4a000" strokeWidth={1} opacity={0.9} />
      <circle r={50} fill="none" stroke="#1e232b" strokeWidth={1} />
      <text x={0} y={-30} textAnchor="middle" fill="#d4a000" fontSize={12} fontWeight={700} fontFamily="Space Grotesk, sans-serif" letterSpacing="0.6">
        {shore.label}
      </text>
      <text x={0} y={-17} textAnchor="middle" fill="#646b75" fontSize={8} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        {shore.node} · SHORE-SIDE
      </text>
      <text x={0} y={2} textAnchor="middle" fill="#e6e8ea" fontSize={9.5} fontFamily="JetBrains Mono, monospace">
        FedAvg {shore.fedavg_weights.length ? shore.fedavg_weights.join(":") : "—"}
      </text>
      <text x={0} y={17} textAnchor="middle" fill="#9aa0a8" fontSize={8.5} fontFamily="JetBrains Mono, monospace">
        RMSE {shore.merged_rmse.toFixed(5)}
      </text>
      <text x={0} y={34} textAnchor="middle" fill={ok ? "#3fb950" : "#e5484d"} fontSize={8.5} fontFamily="JetBrains Mono, monospace" letterSpacing="0.6">
        {ok ? `✓ EVAL PASS · ${shore.accepted_hulls.length} MERGED` : "EVAL HOLD"}
      </text>
    </g>
  );
}

function ShipGlyph({ cx, cy, color }: { cx: number; cy: number; color: string }) {
  return (
    <g transform={`translate(${cx},${cy})`}>
      <path d="M-11 2 L11 2 L7 7 L-7 7 Z" fill="none" stroke={color} strokeWidth={1.1} />
      <rect x={-4} y={-4} width={8} height={6} fill="none" stroke={color} strokeWidth={1} />
      <line x1={0} y1={-4} x2={0} y2={-9} stroke={color} strokeWidth={1} />
    </g>
  );
}

function FlowLabel({ x, y, text, sub }: { x: number; y: number; text: string; sub?: boolean }) {
  return (
    <text
      x={x}
      y={y}
      textAnchor="middle"
      fill={sub ? "#646b75" : "#9aa0a8"}
      fontSize={sub ? 8.5 : 9.5}
      fontFamily="JetBrains Mono, monospace"
      letterSpacing="1.2"
    >
      {text}
    </text>
  );
}

/** Smooth horizontal-ish bezier between two points. */
function curve(x1: number, y1: number, x2: number, y2: number): string {
  const mx = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
}
