import { useLayoutEffect, useMemo, useRef } from "react";
import { gsap } from "gsap";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";
import type { FleetState, FleetShip } from "../../lib/types";
import type { FleetConn } from "../../hooks/useFleetState";

gsap.registerPlugin(MotionPathPlugin);

interface FleetStageProps {
  fleet: FleetState;
  acceptedShips: FleetShip[];
  conn: FleetConn;
}

const W = 1280;
const H = 560;

/**
 * The fleet-learning stage. A signed-delta flow diagram:
 *   sister hulls (learn locally)  ──signed delta──▶  FLEET BRAIN
 *   poisoned node                 ──forged──▶ ✕ REJECTED at the provenance gate
 *   FLEET BRAIN  ──eval-gated merged model──▶  pushed back to every hull
 * GSAP animates packets travelling the trust paths; the poison packet is
 * intercepted and snapped back at the gate.
 */
export function FleetStage({ fleet, acceptedShips, conn }: FleetStageProps) {
  const root = useRef<SVGSVGElement>(null);

  // Honest hull roster: the accepted ships from the record, padded to a 3-hull
  // fleet picture (this ship + sisters). Each carries its real n_samples / rmse.
  const hulls = useMemo(() => {
    const names = ["MACHINERY", "CONTACTS", "SISTER-03"];
    return names.map((nm, i) => {
      const found = acceptedShips.find((s) => s.id === nm);
      return {
        id: nm,
        label: i === 2 ? "SISTER HULL" : nm,
        n: found?.n_samples ?? null,
        rmse: found?.local_train_rmse ?? null,
        accepted: !!found || i === 2,
        projected: i === 2, // SISTER-03 is the projected next hull (honest: not in this run)
      };
    });
  }, [acceptedShips]);

  // vertical anchors for the three hulls on the left
  const hullY = [120, 280, 440];
  const hullX = 150;
  const brainX = 660;
  const brainY = 280;
  const poisonY = 472;
  const poisonX = 150;
  const pushX = 1150;

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const ctx = gsap.context(() => {
      // trust packets: hull → brain (loop)
      gsap.utils.toArray<SVGCircleElement>("[data-trust-packet]").forEach((p, i) => {
        gsap.fromTo(
          p,
          { motionPath: { path: `#trust-path-${i}`, start: 0, end: 0 }, opacity: 0 },
          {
            motionPath: { path: `#trust-path-${i}`, start: 0, end: 1 },
            opacity: 1,
            duration: 2.0,
            ease: "power1.inOut",
            repeat: -1,
            repeatDelay: 1.0,
            delay: i * 0.5,
            keyframes: { opacity: [0, 1, 1, 0] },
          },
        );
      });

      // poison packet: races toward the gate, gets DENIED, snaps back
      const poison = el.querySelector<SVGCircleElement>("[data-poison-packet]");
      if (poison) {
        const tl = gsap.timeline({ repeat: -1, repeatDelay: 0.8 });
        tl.set(poison, { opacity: 0 })
          .fromTo(
            poison,
            { motionPath: { path: "#poison-path", start: 0, end: 0 }, opacity: 0 },
            { motionPath: { path: "#poison-path", start: 0, end: 0.62 }, opacity: 1, duration: 1.4, ease: "power2.in" },
          )
          .to(poison, { scale: 1.6, duration: 0.12, transformOrigin: "center" })
          .to(poison, { motionPath: { path: "#poison-path", start: 0.62, end: 0 }, scale: 1, opacity: 0, duration: 0.7, ease: "power2.out" });
        // flash the DENIED stamp in sync
        const denied = el.querySelector("[data-denied-stamp]");
        if (denied) {
          gsap.timeline({ repeat: -1, repeatDelay: 0.8, delay: 1.4 })
            .fromTo(denied, { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: 0.18, transformOrigin: "center" })
            .to(denied, { opacity: 0.85, duration: 0.8 })
            .to(denied, { opacity: 0, duration: 0.5 });
        }
      }

      // push-back packet: brain → fleet (the improved model returning)
      const push = el.querySelector<SVGCircleElement>("[data-push-packet]");
      if (push) {
        gsap.fromTo(
          push,
          { motionPath: { path: "#push-path", start: 0, end: 0 }, opacity: 0 },
          {
            motionPath: { path: "#push-path", start: 0, end: 1 },
            opacity: 1,
            duration: 2.4,
            ease: "power1.inOut",
            repeat: -1,
            repeatDelay: 1.2,
            delay: 1.5,
            keyframes: { opacity: [0, 1, 1, 0] },
          },
        );
      }

      // brain core breathing
      gsap.to("[data-brain-core]", {
        opacity: 0.5,
        duration: 1.6,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
      });
    }, root);
    return () => ctx.revert();
  }, [hulls.length]);

  const merge = fleet.merge;

  return (
    <svg
      ref={root}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
    >
      <defs>
        {/* trust paths hull → brain */}
        {hullY.map((y, i) => (
          <path key={i} id={`trust-path-${i}`} d={curve(hullX + 84, y, brainX - 78, brainY)} fill="none" />
        ))}
        {/* poison path */}
        <path id="poison-path" d={curve(poisonX + 84, poisonY, brainX - 78, brainY + 40)} fill="none" />
        {/* push-back path brain → fleet manifold on the right */}
        <path id="push-path" d={curve(brainX + 84, brainY, pushX - 40, brainY)} fill="none" />
      </defs>

      {/* ── static trust lines (hairline) ── */}
      {hullY.map((y, i) => (
        <path
          key={i}
          d={curve(hullX + 84, y, brainX - 78, brainY)}
          fill="none"
          stroke={hulls[i].projected ? "#2a313a" : "#3a4049"}
          strokeWidth={1}
          strokeDasharray={hulls[i].projected ? "3 5" : undefined}
        />
      ))}
      {/* poison line — drawn red/denied */}
      <path d={curve(poisonX + 84, poisonY, brainX - 78, brainY + 40)} fill="none" stroke="#5a2528" strokeWidth={1} strokeDasharray="4 4" />
      {/* push-back line */}
      <path d={curve(brainX + 84, brainY, pushX - 40, brainY)} fill="none" stroke="#3a4049" strokeWidth={1} />

      {/* ── animated packets ── */}
      {hullY.map((_, i) => (
        <g key={i}>
          <circle data-trust-packet r={4.5} fill="#d4a000" />
        </g>
      ))}
      <circle data-push-packet r={5} fill="#3fb950" />
      <circle data-poison-packet r={4.5} fill="#e5484d" />

      {/* ── LEFT: sister hulls learning locally ── */}
      {hullY.map((y, i) => (
        <HullNode key={i} x={hullX} y={y} hull={hulls[i]} />
      ))}

      {/* ── the poisoned node ── */}
      <PoisonNode x={poisonX} y={poisonY} reason={fleet.rejected[0]?.reason ?? "forged signature · key not in trust registry"} />

      {/* ── the provenance gate (intercept point) ── */}
      <ProvenanceGateGlyph x={brainX - 150} y={brainY + 40} />

      {/* ── CENTER: the fleet brain ── */}
      <FleetBrain x={brainX} y={brainY} accepted={merge?.accepted_ships.length ?? 0} weights={merge?.fedavg_weights ?? []} />

      {/* ── RIGHT: pushed-back improved model manifold ── */}
      <PushBackNode x={pushX} y={brainY} merge={merge} pass={fleet.eval_gate_pass} />

      {/* labels along the flow */}
      <FlowLabel x={(hullX + brainX) / 2 + 20} y={brainY - 150} text="① LEARN LOCAL · DDIL" />
      <FlowLabel x={(hullX + brainX) / 2 + 20} y={brainY - 132} text="signed delta ▸ never raw data" sub />
      <FlowLabel x={brainX} y={H - 22} text="② PROVENANCE GATE + FEDAVG + EVAL GATE" />
      <FlowLabel x={(brainX + pushX) / 2 + 20} y={brainY - 40} text="③ PUSH IMPROVED MODEL BACK" />

      {/* connection provenance footnote */}
      <text x={W - 14} y={H - 12} textAnchor="end" fill="#646b75" fontSize={9} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        {conn === "live" ? "◆ FLEET RECORD LIVE · /api/fleet" : "◆ FLEET RECORD · SIM FIXTURE"}
      </text>
    </svg>
  );
}

/* ---------------- sub-glyphs ---------------- */

function HullNode({ x, y, hull }: { x: number; y: number; hull: { label: string; id: string; n: number | null; rmse: number | null; projected: boolean } }) {
  const dim = hull.projected;
  const color = dim ? "#646b75" : "#e6e8ea";
  return (
    <g transform={`translate(${x},${y})`} opacity={dim ? 0.62 : 1}>
      {/* hull plate */}
      <rect x={-80} y={-44} width={164} height={88} fill="#0d1117" stroke={dim ? "#2a313a" : "#2b3138"} strokeWidth={1} />
      <rect x={-80} y={-44} width={3} height={88} fill={dim ? "#3a4049" : "#3fb950"} />
      {/* ship glyph */}
      <ShipGlyph cx={-54} cy={-22} color={dim ? "#646b75" : "#9aa0a8"} />
      <text x={-32} y={-26} fill={color} fontSize={12} fontWeight={600} fontFamily="Space Grotesk, sans-serif" letterSpacing="0.5">
        {hull.label}
      </text>
      <text x={-32} y={-13} fill="#646b75" fontSize={8.5} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        {dim ? "PROJECTED HULL" : `${hull.id} · PI NODE`}
      </text>
      {/* local-train readout */}
      <text x={-68} y={10} fill="#646b75" fontSize={8} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        LOCAL TRAIN
      </text>
      <text x={-68} y={27} fill={dim ? "#646b75" : "#d4a000"} fontSize={13} fontFamily="JetBrains Mono, monospace">
        {hull.rmse != null ? `RMSE ${hull.rmse.toFixed(5)}` : "— pending"}
      </text>
      <text x={76} y={27} textAnchor="end" fill="#9aa0a8" fontSize={9} fontFamily="JetBrains Mono, monospace">
        {hull.n != null ? `n=${hull.n}` : ""}
      </text>
      {/* signed badge */}
      {!dim ? (
        <g transform="translate(58,-34)">
          <rect x={-2} y={-7} width={26} height={14} fill="none" stroke="#3fb950" strokeWidth={0.8} />
          <text x={11} y={3} textAnchor="middle" fill="#3fb950" fontSize={7} fontFamily="JetBrains Mono, monospace" letterSpacing="0.5">
            SIGNED
          </text>
        </g>
      ) : null}
    </g>
  );
}

function PoisonNode({ x, y, reason }: { x: number; y: number; reason: string }) {
  return (
    <g transform={`translate(${x},${y})`}>
      <rect x={-80} y={-32} width={164} height={64} fill="#1a0d0f" stroke="#5a2528" strokeWidth={1} />
      <rect x={-80} y={-32} width={3} height={64} fill="#e5484d" />
      <ShipGlyph cx={-54} cy={-14} color="#e5484d" />
      <text x={-32} y={-16} fill="#e5484d" fontSize={11} fontWeight={600} fontFamily="Space Grotesk, sans-serif" letterSpacing="0.5">
        POISON NODE
      </text>
      <text x={-32} y={-3} fill="#9a6468" fontSize={8} fontFamily="JetBrains Mono, monospace" letterSpacing="0.5">
        forged delta · captured hull
      </text>
      <text x={-68} y={20} fill="#9a6468" fontSize={7.5} fontFamily="JetBrains Mono, monospace">
        {reason.length > 42 ? reason.slice(0, 40) + "…" : reason}
      </text>
    </g>
  );
}

function ProvenanceGateGlyph({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x},${y})`}>
      {/* the DENIED stamp that flashes when the poison hits the gate */}
      <g data-denied-stamp opacity={0}>
        <rect x={-44} y={-15} width={88} height={30} fill="none" stroke="#e5484d" strokeWidth={1.5} />
        <text x={0} y={5} textAnchor="middle" fill="#e5484d" fontSize={13} fontWeight={700} fontFamily="Space Grotesk, sans-serif" letterSpacing="2">
          DENIED
        </text>
      </g>
      <text x={0} y={34} textAnchor="middle" fill="#9a6468" fontSize={8} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        keyid ∉ trust registry
      </text>
    </g>
  );
}

function FleetBrain({ x, y, accepted, weights }: { x: number; y: number; accepted: number; weights: number[] }) {
  return (
    <g transform={`translate(${x},${y})`}>
      {/* outer trust ring */}
      <circle r={78} fill="#0d1117" stroke="#2b3138" strokeWidth={1} />
      <circle data-brain-core r={78} fill="none" stroke="#d4a000" strokeWidth={1} opacity={0.9} />
      <circle r={62} fill="none" stroke="#1e232b" strokeWidth={1} />
      {/* hub label */}
      <text x={0} y={-30} textAnchor="middle" fill="#d4a000" fontSize={13} fontWeight={700} fontFamily="Space Grotesk, sans-serif" letterSpacing="1">
        FLEET BRAIN
      </text>
      <text x={0} y={-15} textAnchor="middle" fill="#646b75" fontSize={8} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        SHORE · SQUADRON
      </text>
      {/* fedavg readout */}
      <text x={0} y={6} textAnchor="middle" fill="#e6e8ea" fontSize={10} fontFamily="JetBrains Mono, monospace" letterSpacing="0.5">
        FedAvg
      </text>
      <text x={0} y={22} textAnchor="middle" fill="#9aa0a8" fontSize={9} fontFamily="JetBrains Mono, monospace">
        {weights.length ? `weighted ${weights.join(":")}` : "—"}
      </text>
      <text x={0} y={40} textAnchor="middle" fill="#3fb950" fontSize={9} fontFamily="JetBrains Mono, monospace" letterSpacing="0.5">
        {accepted} ATTESTED ▸ MERGED
      </text>
    </g>
  );
}

function PushBackNode({ x, y, merge, pass }: { x: number; y: number; merge: FleetState["merge"]; pass: boolean | null }) {
  const ok = pass === true;
  return (
    <g transform={`translate(${x},${y})`}>
      {/* the fleet manifold the improved model returns to */}
      {[-58, 0, 58].map((dy, i) => (
        <g key={i} transform={`translate(0,${dy})`} opacity={i === 2 ? 0.55 : 1}>
          <rect x={-12} y={-13} width={92} height={26} fill="#0d1117" stroke={ok ? "#26482f" : "#2b3138"} strokeWidth={1} />
          <ShipGlyph cx={2} cy={0} color={ok ? "#3fb950" : "#646b75"} small />
          <text x={20} y={4} fill={ok ? "#3fb950" : "#9aa0a8"} fontSize={9} fontFamily="JetBrains Mono, monospace" letterSpacing="0.5">
            HULL {i + 1}▸
          </text>
        </g>
      ))}
      <text x={34} y={-92} textAnchor="middle" fill={ok ? "#3fb950" : "#646b75"} fontSize={10} fontWeight={600} fontFamily="Space Grotesk, sans-serif" letterSpacing="0.5">
        FLEET MODEL
      </text>
      <text x={34} y={-78} textAnchor="middle" fill="#646b75" fontSize={8} fontFamily="JetBrains Mono, monospace" letterSpacing="0.5">
        {merge ? `RMSE ${merge.merged_rmse.toFixed(5)}` : "—"}
      </text>
      <text x={34} y={110} textAnchor="middle" fill={ok ? "#3fb950" : "#e5484d"} fontSize={9} fontFamily="JetBrains Mono, monospace" letterSpacing="1">
        {ok ? "✓ EVAL-GATE PASS" : "EVAL-GATE HOLD"}
      </text>
    </g>
  );
}

function ShipGlyph({ cx, cy, color, small }: { cx: number; cy: number; color: string; small?: boolean }) {
  const s = small ? 0.7 : 1;
  return (
    <g transform={`translate(${cx},${cy}) scale(${s})`}>
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

/** A smooth horizontal-ish bezier between two points (for the trust paths). */
function curve(x1: number, y1: number, x2: number, y2: number): string {
  const mx = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
}
