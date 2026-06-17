import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei";
import * as THREE from "three";
import type { ShipSystem } from "../../lib/types";
import { ShipMesh } from "./ShipMesh";
import { SystemNodes } from "./SystemNodes";

/** Slowly rotating rig holding the ship + nodes; gentle bob for "afloat" feel. */
function Rig({ systems }: { systems: ShipSystem[] }) {
  const group = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime;
    group.current.rotation.y = t * 0.16; // slow, intentional spin
    group.current.position.y = -0.15 + Math.sin(t * 0.6) * 0.06; // subtle swell
    group.current.rotation.z = Math.sin(t * 0.5) * 0.015; // tiny roll
  });

  return (
    <group ref={group} scale={0.82}>
      <ShipMesh />
      <SystemNodes systems={systems} />
    </group>
  );
}

/** Sea plane below the ship with a radial alpha fade (no hard disc edge). */
function SeaPlane() {
  const tex = useMemo(() => {
    const s = 256;
    const cv = document.createElement("canvas");
    cv.width = cv.height = s;
    const ctx = cv.getContext("2d")!;
    const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    g.addColorStop(0, "rgba(12,34,64,0.85)");
    g.addColorStop(0.55, "rgba(8,20,44,0.55)");
    g.addColorStop(1, "rgba(8,20,44,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, s, s);
    const t = new THREE.CanvasTexture(cv);
    t.needsUpdate = true;
    return t;
  }, []);

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.0, 0]}>
      <circleGeometry args={[13, 96]} />
      <meshStandardMaterial
        map={tex}
        color="#1a3358"
        metalness={0.85}
        roughness={0.3}
        transparent
        opacity={0.9}
        depthWrite={false}
      />
    </mesh>
  );
}

export function ShipScene({ systems }: { systems: ShipSystem[] }) {
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [6.0, 3.0, 5.6], fov: 36 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      resize={{ debounce: 0 }}
      style={{ width: "100%", height: "100%", background: "transparent" }}
    >
      {/* lighting — cool key, strong cyan rim + magenta fill for the neon ops look */}
      <ambientLight intensity={0.5} color="#6478ad" />
      <hemisphereLight args={["#9fc7ff", "#0a1228", 0.6]} />
      <directionalLight
        position={[6, 10, 5]}
        intensity={2.2}
        color="#eaf2ff"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0004}
      />
      {/* cyan rim from behind-left for the signature glowing edge */}
      <directionalLight position={[-8, 3, -5]} intensity={2.0} color="#00d9ff" />
      <pointLight position={[2, 1.5, 4]} intensity={1.2} color="#00d9ff" distance={14} />
      <spotLight
        position={[-5, 7, 5]}
        angle={0.6}
        penumbra={0.9}
        intensity={1.4}
        color="#a78bff"
      />
      <pointLight position={[0, 6, -2]} intensity={0.7} color="#7aa0ff" />

      <Rig systems={systems} />
      <SeaPlane />
      <ContactShadows
        position={[0, -0.98, 0]}
        opacity={0.5}
        scale={12}
        blur={2.6}
        far={4}
        color="#000814"
      />

      <fog attach="fog" args={["#0a0e27", 12, 24]} />
    </Canvas>
  );
}
