import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Billboard, Text } from "@react-three/drei";
import * as THREE from "three";
import type { ShipSystem } from "../../lib/types";
import { SEVERITY_COLOR } from "../../lib/palette";

/** Fixed mount positions on the hull for each of the 7 ship systems. */
const NODE_POS: Record<string, [number, number, number]> = {
  contacts: [0.55, 3.85, 0], // mast-top sensors
  navigation: [1.1, 2.35, 0], // bridge
  power: [-0.7, 2.05, 0], // funnel / power
  machinery: [-0.4, 1.0, 0.55], // engineering spaces (offset to starboard)
  propulsion: [-2.6, 0.95, 0], // aft / shafts
  damage_control: [0.0, 0.95, -0.55], // amidships (port)
  readiness: [2.3, 1.25, 0], // forward
};

const SHORT_LABEL: Record<string, string> = {
  contacts: "SENSORS",
  navigation: "NAV",
  power: "POWER",
  machinery: "HM&E",
  propulsion: "PROPULSION",
  damage_control: "DC",
  readiness: "READINESS",
};

interface NodeProps {
  system: ShipSystem;
  position: [number, number, number];
}

function SystemNode({ system, position }: NodeProps) {
  const ringRef = useRef<THREE.Mesh>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const matRef = useRef<THREE.MeshBasicMaterial>(null);

  const color = SEVERITY_COLOR[system.severity];
  const live = system.live && system.severity !== "standby";
  const critical = system.severity === "critical";

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (critical && coreRef.current && matRef.current) {
      // breathe brighter for critical
      const pulse = 0.6 + 0.4 * Math.sin(t * 3.2);
      matRef.current.opacity = pulse;
      const s = 1 + 0.12 * Math.sin(t * 3.2);
      coreRef.current.scale.setScalar(s);
    }
    if (ringRef.current && live) {
      // expanding alert ring for critical, gentle spin otherwise
      ringRef.current.rotation.z += critical ? 0.04 : 0.01;
    }
  });

  return (
    <group position={position}>
      {/* glowing core */}
      <mesh ref={coreRef}>
        <sphereGeometry args={[live ? 0.11 : 0.07, 16, 16]} />
        <meshBasicMaterial
          ref={matRef}
          color={color}
          transparent
          opacity={live ? 0.95 : 0.4}
        />
      </mesh>

      {/* layered halo glow (additive billboard) */}
      {live && (
        <Billboard>
          <mesh>
            <circleGeometry args={[critical ? 0.5 : 0.36, 32]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={critical ? 0.22 : 0.13}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
          <mesh>
            <circleGeometry args={[critical ? 0.28 : 0.2, 28]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={critical ? 0.4 : 0.26}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        </Billboard>
      )}

      {/* alert ring for critical */}
      {critical && (
        <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.26, 0.012, 8, 40]} />
          <meshBasicMaterial color={color} transparent opacity={0.85} />
        </mesh>
      )}

      {/* label */}
      <Billboard position={[0, live ? 0.42 : 0.32, 0]}>
        <Text
          font="/GeistMono-Medium.ttf"
          fontSize={0.15}
          color={live ? color : "#6b7796"}
          anchorX="center"
          anchorY="middle"
          letterSpacing={0.08}
          outlineWidth={0.004}
          outlineColor="#070b1c"
        >
          {SHORT_LABEL[system.key] ?? system.key.toUpperCase()}
        </Text>
      </Billboard>
    </group>
  );
}

export function SystemNodes({ systems }: { systems: ShipSystem[] }) {
  return (
    <group>
      {systems.map((s) => {
        const pos = NODE_POS[s.key];
        if (!pos) return null;
        return <SystemNode key={s.key} system={s} position={pos} />;
      })}
    </group>
  );
}
