import { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, ContactShadows, Environment, Lightformer } from "@react-three/drei";
import * as THREE from "three";
import { Warship } from "./Warship";
import { TWIN_STATUS, type ZoneStatus } from "../../lib/twin";

interface ShipTwinProps {
  zones: ZoneStatus[];
  /** pause auto-rotation (e.g. while the operator is dragging) */
  autoRotate?: boolean;
  conn: "live" | "stale" | "mock" | "connecting";
}

/**
 * The digital-twin hero. A procedural warship in a premium three-point studio
 * light rig with an in-scene environment (NO remote HDR — Lightformers generate
 * the env map locally, airgap-clean). Slow cinematic idle orbit; the operator
 * can grab and orbit. The two Pi-node subsystem zones glow live by status.
 */
export function ShipTwin({ zones, autoRotate = true, conn }: ShipTwinProps) {
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <Canvas
        shadows
        gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.12 }}
        camera={{ position: [5.4, 2.9, 6.4], fov: 31, near: 0.1, far: 60 }}
        dpr={[1, 2]}
        style={{ background: "transparent" }}
      >
        {/* warm off-black fog seats the hull in the CIC base color */}
        <color attach="background" args={["#0a0c10"]} />
        <fog attach="fog" args={["#0a0c10", 13, 30]} />

        <Suspense fallback={null}>
          {/* ── three-point rig ── */}
          {/* key: warm command light from high-fore-starboard */}
          <directionalLight
            position={[7, 10, 5]}
            intensity={2.9}
            color="#fff4d8"
            castShadow
            shadow-mapSize={[2048, 2048]}
            shadow-bias={-0.0004}
          >
            <orthographicCamera attach="shadow-camera" args={[-8, 8, 8, -8, 0.1, 30]} />
          </directionalLight>
          {/* fill: cool, soft, from the port side to model the steel */}
          <directionalLight position={[-9, 4, -4]} intensity={0.7} color="#9fb4d4" />
          {/* rim: amber accent edge from behind to separate hull from base */}
          <directionalLight position={[-5, 3.5, 9]} intensity={1.1} color="#d4a000" />
          {/* cool under-fill bounce so the hull belly isn't a void */}
          <directionalLight position={[2, -4, 3]} intensity={0.22} color="#3a4656" />
          <ambientLight intensity={0.16} color="#5b6573" />

          {/* in-scene environment — built from Lightformers, no remote files */}
          <Environment resolution={256} frames={1}>
            <Lightformer intensity={2.6} position={[0, 6, 0]} scale={[12, 4, 1]} color="#d6dfec" />
            <Lightformer intensity={1.3} position={[7, 2, 5]} scale={[7, 7, 1]} color="#fff1d2" />
            <Lightformer intensity={0.9} position={[-7, 1, -4]} scale={[7, 7, 1]} color="#7e8aa0" />
            <Lightformer form="ring" intensity={1.0} position={[-5, 2, 8]} scale={[3, 3, 1]} color="#d4a000" />
            <Lightformer intensity={0.5} position={[0, -3, 0]} scale={[12, 4, 1]} color="#1a1f27" />
          </Environment>

          <Warship zones={zones} autoRotate={autoRotate} />
          <TwinStage />

          {/* grounded soft contact shadow (the "sea" under the hull) */}
          <ContactShadows
            position={[0, -0.66, 0]}
            opacity={0.7}
            scale={16}
            blur={2.4}
            far={4}
            resolution={1024}
            color="#000000"
          />

          <OrbitControls
            enablePan={false}
            enableZoom
            minDistance={5.2}
            maxDistance={13}
            minPolarAngle={0.2}
            maxPolarAngle={Math.PI / 2.05}
            target={[0, 0.05, 0]}
            makeDefault
          />
        </Suspense>
      </Canvas>

      {/* instrument-grade overlays — HTML, never a remote font in 3D */}
      <TwinHud />
      <TwinLegend zones={zones} conn={conn} />
    </div>
  );
}

/**
 * The instrumented base the twin sits on — a measurement stage, not decoration.
 * A faint scanned-grid disc, an amber azimuth ring with radial bearing ticks,
 * and a slow counter-rotating scan sweep. Reads as "this is a digital twin under
 * measurement," the Palantir/instrument-grade tell.
 */
function TwinStage() {
  const sweep = useRef<THREE.Mesh>(null);
  useFrame((_, dt) => {
    if (sweep.current) sweep.current.rotation.z -= dt * 0.5;
  });

  const ticks = useMemo(() => {
    const arr: { x: number; z: number; x2: number; z2: number; major: boolean }[] = [];
    const R = 5.0;
    for (let b = 0; b < 360; b += 7.5) {
      const a = (b * Math.PI) / 180;
      const major = b % 30 === 0;
      const inner = major ? R - 0.28 : R - 0.14;
      arr.push({
        x: Math.cos(a) * inner,
        z: Math.sin(a) * inner,
        x2: Math.cos(a) * R,
        z2: Math.sin(a) * R,
        major,
      });
    }
    return arr;
  }, []);

  const tickGeo = useMemo(() => {
    const pts: number[] = [];
    ticks.forEach((t) => {
      pts.push(t.x, 0, t.z, t.x2, 0, t.z2);
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [ticks]);

  return (
    <group position={[0, -0.64, 0]}>
      {/* scanned floor grid (built locally, hairline) */}
      <gridHelper args={[26, 52, "#161b22", "#0f1318"]} />
      {/* concentric range discs */}
      {[2.4, 3.7, 5.0].map((r, i) => (
        <mesh key={i} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[r - 0.008, r + 0.008, 128]} />
          <meshBasicMaterial color={i === 2 ? "#3a2f10" : "#1b2027"} transparent opacity={i === 2 ? 0.9 : 0.6} side={THREE.DoubleSide} />
        </mesh>
      ))}
      {/* amber azimuth ring + bearing ticks */}
      <lineSegments geometry={tickGeo} rotation={[0, 0, 0]}>
        <lineBasicMaterial color="#6f5410" transparent opacity={0.85} />
      </lineSegments>
      {/* slow scan sweep — a faint amber wedge */}
      <mesh ref={sweep} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.002, 0]}>
        <circleGeometry args={[5.0, 64, 0, 0.5]} />
        <meshBasicMaterial color="#d4a000" transparent opacity={0.05} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

/** Corner instrument frame + DIGITAL-TWIN watermark (HTML overlay). */
function TwinHud() {
  const corner = (pos: React.CSSProperties): React.CSSProperties => ({
    position: "absolute",
    width: 18,
    height: 18,
    borderColor: "var(--hair-lit)",
    pointerEvents: "none",
    ...pos,
  });
  return (
    <>
      {/* registration corners */}
      <div style={{ ...corner({ top: 10, left: 10 }), borderTop: "1px solid", borderLeft: "1px solid" }} />
      <div style={{ ...corner({ top: 10, right: 10 }), borderTop: "1px solid", borderRight: "1px solid" }} />
      <div style={{ ...corner({ bottom: 10, right: 10 }), borderBottom: "1px solid", borderRight: "1px solid" }} />
      {/* watermark */}
      <div
        className="mono"
        style={{
          position: "absolute",
          top: 14,
          right: 36,
          fontSize: 9,
          letterSpacing: "0.22em",
          color: "var(--muted)",
          pointerEvents: "none",
        }}
      >
        DIGITAL TWIN · DDG-CLASS · PROCEDURAL
      </div>
    </>
  );
}

function TwinLegend({ zones, conn }: { zones: ZoneStatus[]; conn: ShipTwinProps["conn"] }) {
  return (
    <div
      style={{
        position: "absolute",
        left: 14,
        bottom: 14,
        display: "flex",
        flexDirection: "column",
        gap: 7,
        pointerEvents: "none",
      }}
    >
      <div className="eyebrow" style={{ fontSize: 9, marginBottom: 1 }}>
        Live Hull Telemetry
      </div>
      {zones.map((z) => {
        const c = TWIN_STATUS[z.severity];
        const standby = z.severity === "standby";
        return (
          <div
            key={z.zone}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              border: "1px solid var(--hair)",
              background: "rgba(10,12,16,0.74)",
              padding: "7px 11px",
              minWidth: 252,
            }}
          >
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: c.hex,
                boxShadow: standby ? "none" : `0 0 7px ${c.hex}`,
                flexShrink: 0,
              }}
            />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span
                  className="display"
                  style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.04em", color: "var(--ink)" }}
                >
                  {z.label}
                </span>
                <span className="mono" style={{ fontSize: 8.5, color: "var(--muted)", letterSpacing: "0.12em", marginLeft: "auto" }}>
                  {z.node}
                </span>
              </div>
              <div className="mono" style={{ fontSize: 9, color: standby ? "var(--muted)" : c.hex, letterSpacing: "0.08em", marginTop: 2 }}>
                {standby ? "STANDBY · model pending" : z.severity.toUpperCase()}
              </div>
            </div>
          </div>
        );
      })}
      <div className="mono" style={{ fontSize: 8.5, color: "var(--muted)", letterSpacing: "0.1em", marginTop: 1 }}>
        {conn === "live" ? "◆ ZONES LIT FROM /api/state" : "◆ ZONES FROM SIM FIXTURE"} · DRAG TO ORBIT
      </div>
    </div>
  );
}
