import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { TWIN_STATUS, type ZoneStatus } from "../../lib/twin";

/**
 * A procedurally-modeled destroyer-class warship. NO remote/CDN assets — every
 * vertex is generated here so the twin is airgap-clean. Built from primitive
 * geometry composed into a credible hull silhouette: a chined flared hull,
 * tiered superstructure, integrated mast, gun mount, and VLS deck. Hull is matte
 * naval haze-gray; the two subsystem zones (MACHINERY aft, CONTACTS fwd) carry
 * emissive markers driven live from /api/state.
 */

const HULL_GRAY = "#4d545d"; // hull a touch darker for tonal separation
const HULL_DARK = "#363c44";
const DECK_GRAY = "#41474f";
const STEEL = "#737a84"; // superstructure lighter so it reads against the hull

/** A soft radial-gradient glow sprite texture, generated locally (no assets). */
let _glowTex: THREE.Texture | null = null;
function useGlowTexture(): THREE.Texture {
  return useMemo(() => {
    if (_glowTex) return _glowTex;
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const ctx = c.getContext("2d")!;
    const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.25, "rgba(255,255,255,0.6)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
    _glowTex = new THREE.CanvasTexture(c);
    return _glowTex;
  }, []);
}

/** A long faceted hull from an extruded chined cross-section. */
function useHullGeometry() {
  return useMemo(() => {
    // Cross-section of a flared warship hull (looking down the bow): a V-keel
    // rising to a chine then flaring out to the deck edge. Units: half-beam ~0.85.
    const shape = new THREE.Shape();
    shape.moveTo(0, -0.62); // keel
    shape.lineTo(0.46, -0.22); // turn of the bilge
    shape.lineTo(0.85, 0.16); // chine / waterline flare
    shape.lineTo(0.8, 0.5); // deck edge (slight tumblehome)
    shape.lineTo(0, 0.56); // deck centre (camber)
    shape.lineTo(-0.8, 0.5);
    shape.lineTo(-0.85, 0.16);
    shape.lineTo(-0.46, -0.22);
    shape.lineTo(0, -0.62);

    const len = 7.0;
    const geo = new THREE.ExtrudeGeometry(shape, {
      depth: len,
      bevelEnabled: false,
      steps: 64,
      curveSegments: 4,
    });
    geo.translate(0, 0, -len / 2);
    geo.rotateY(Math.PI / 2); // length now runs along +X
    geo.computeVertexNormals();

    // Taper the bow: pinch the +X half toward a fine entry, and rake it up.
    const pos = geo.attributes.position as THREE.BufferAttribute;
    const v = new THREE.Vector3();
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i);
      const t = v.x / (len / 2); // -1 (stern) .. +1 (bow)
      if (t > 0) {
        const pinch = 1 - Math.pow(t, 2.0) * 0.86; // fine bow
        v.z *= pinch;
        v.y += Math.pow(t, 2.6) * 0.34; // sheer rise toward the bow
        if (t > 0.86) v.x += (t - 0.86) * 0.7; // stretch the stem to a point
      } else {
        // square transom stern, slight tuck
        v.z *= 1 + t * 0.06;
      }
      pos.setXYZ(i, v.x, v.y, v.z);
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();
    return geo;
  }, []);
}

function Box({
  pos,
  size,
  color = STEEL,
  rot,
  metalness = 0.45,
  roughness = 0.55,
}: {
  pos: [number, number, number];
  size: [number, number, number];
  color?: string;
  rot?: [number, number, number];
  metalness?: number;
  roughness?: number;
}) {
  return (
    <mesh position={pos} rotation={rot} castShadow receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} metalness={metalness} roughness={roughness} />
    </mesh>
  );
}

/** A pulsing emissive subsystem marker on the hull, color = live status. */
function ZoneMarker({
  position,
  status,
}: {
  position: [number, number, number];
  status: ZoneStatus;
}) {
  const ring = useRef<THREE.Mesh>(null);
  const core = useRef<THREE.MeshStandardMaterial>(null);
  const s = TWIN_STATUS[status.severity];
  const color = useMemo(() => new THREE.Color(s.hex), [s.hex]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    // critical pulses faster + harder; standby barely breathes
    const speed = status.severity === "critical" ? 4.2 : status.severity === "standby" ? 0.9 : 2.0;
    const depth = status.severity === "standby" ? 0.12 : 0.5;
    const pulse = 0.7 + Math.sin(t * speed) * depth;
    if (core.current) core.current.emissiveIntensity = s.glow * pulse * 2.2;
    if (ring.current) {
      const sc = 1 + ((Math.sin(t * speed) + 1) / 2) * (status.severity === "standby" ? 0.08 : 0.55);
      ring.current.scale.set(sc, sc, sc);
      const mat = ring.current.material as THREE.MeshBasicMaterial;
      mat.opacity = status.severity === "standby" ? 0.18 : 0.55 * (1.3 - sc);
    }
  });

  return (
    <group position={position}>
      {/* emissive core beacon */}
      <mesh>
        <sphereGeometry args={[0.092, 24, 24]} />
        <meshStandardMaterial
          ref={core}
          color={color}
          emissive={color}
          emissiveIntensity={s.glow * 2.6}
          toneMapped={false}
        />
      </mesh>
      {/* soft billboarded glow halo so the live beacon pops from any angle —
          tightened so it reads as a precise beacon, not a blob */}
      <sprite scale={[0.42, 0.42, 0.42]}>
        <spriteMaterial
          map={useGlowTexture()}
          color={color}
          transparent
          opacity={status.severity === "standby" ? 0.1 : 0.42}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </sprite>
      {/* expanding radar-ping ring (flat on the deck plane) */}
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.04, 0]}>
        <ringGeometry args={[0.13, 0.17, 48]} />
        <meshBasicMaterial color={color} transparent opacity={0.55} side={THREE.DoubleSide} toneMapped={false} />
      </mesh>
      {/* a slim beacon stalk + soft volumetric halo so the zone reads from any
          orbit angle without looking like a toy antenna */}
      <mesh position={[0, 0.34, 0]}>
        <cylinderGeometry args={[0.006, 0.01, 0.68, 8]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={s.glow * 0.7} toneMapped={false} />
      </mesh>
      {/* point light tints the surrounding hull plates with the live status */}
      <pointLight color={color} intensity={status.severity === "standby" ? 0.12 : 0.9} distance={2.2} decay={2} position={[0, 0.15, 0]} />
    </group>
  );
}

export function Warship({
  zones,
  autoRotate = true,
}: {
  zones: ZoneStatus[];
  autoRotate?: boolean;
}) {
  const hull = useHullGeometry();
  const group = useRef<THREE.Group>(null);

  // cinematic idle rotation about the vertical axis
  useFrame((_, dt) => {
    if (autoRotate && group.current) group.current.rotation.y += dt * 0.12;
  });

  const machinery = zones.find((z) => z.zone === "machinery");
  const contacts = zones.find((z) => z.zone === "contacts");

  return (
    <group ref={group} position={[0, 0, 0]}>
      {/* ─── HULL ─── (length runs along X: stern -X, bow +X) */}
      <mesh geometry={hull} castShadow receiveShadow>
        <meshStandardMaterial color={HULL_GRAY} metalness={0.5} roughness={0.48} envMapIntensity={0.9} />
      </mesh>

      {/* boot-topping / waterline stripe (darker band at the waterline) */}
      <mesh position={[0.1, -0.04, 0]}>
        <boxGeometry args={[6.7, 0.12, 1.74]} />
        <meshStandardMaterial color="#23272d" metalness={0.15} roughness={0.85} />
      </mesh>
      {/* red draft/anti-fouling hint below the boot-topping */}
      <mesh position={[0.1, -0.16, 0]}>
        <boxGeometry args={[6.4, 0.12, 1.66]} />
        <meshStandardMaterial color="#3a2326" metalness={0.1} roughness={0.9} />
      </mesh>

      {/* main deck plate (flat reference so superstructure seats cleanly) */}
      <mesh position={[0, 0.57, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[6.4, 1.5]} />
        <meshStandardMaterial color={DECK_GRAY} metalness={0.3} roughness={0.7} />
      </mesh>

      {/* ─── FORE GUN MOUNT (bow) ─── */}
      <group position={[2.05, 0.62, 0]}>
        <Box pos={[0, 0.12, 0]} size={[0.5, 0.24, 0.5]} color={STEEL} />
        <mesh position={[0, 0.18, 0]} rotation={[0, 0, 0]}>
          <cylinderGeometry args={[0.05, 0.06, 0.34, 12]} />
          <meshStandardMaterial color="#7a818a" metalness={0.6} roughness={0.4} />
        </mesh>
        {/* barrel */}
        <mesh position={[0.42, 0.2, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.022, 0.022, 0.7, 10]} />
          <meshStandardMaterial color="#3c424b" metalness={0.7} roughness={0.3} />
        </mesh>
      </group>

      {/* ─── FWD VLS DECK (forward of bridge) ─── */}
      <group position={[1.35, 0.64, 0]}>
        <Box pos={[0, 0.05, 0]} size={[0.6, 0.1, 0.7]} color={HULL_DARK} roughness={0.85} />
        {[-0.18, -0.06, 0.06, 0.18].map((z) =>
          [-0.16, 0, 0.16].map((x) => (
            <mesh key={`${x}-${z}`} position={[x, 0.1, z]}>
              <boxGeometry args={[0.07, 0.04, 0.07]} />
              <meshStandardMaterial color="#2b3138" metalness={0.5} roughness={0.5} />
            </mesh>
          )),
        )}
      </group>

      {/* ─── BRIDGE / FORWARD SUPERSTRUCTURE (tiered) ─── */}
      <group position={[0.55, 0.6, 0]}>
        <Box pos={[0, 0.28, 0]} size={[1.5, 0.56, 1.05]} color={STEEL} />
        <Box pos={[-0.1, 0.72, 0]} size={[1.0, 0.34, 0.86]} color="#646b75" />
        {/* bridge windows: a thin dark band */}
        <Box pos={[0.55, 0.7, 0]} size={[0.16, 0.16, 0.78]} color="#1b2027" metalness={0.1} roughness={0.9} />
        {/* enclosed mast / sensor tower */}
        <Box pos={[-0.15, 1.15, 0]} size={[0.46, 0.6, 0.46]} color="#586069" />
        <mesh position={[-0.15, 1.6, 0]}>
          <cylinderGeometry args={[0.03, 0.07, 0.5, 8]} />
          <meshStandardMaterial color="#6b727b" metalness={0.55} roughness={0.45} />
        </mesh>
        {/* phased-array radar panel (canted) */}
        <mesh position={[0.18, 0.55, 0.45]} rotation={[0, -0.5, 0]}>
          <boxGeometry args={[0.34, 0.34, 0.04]} />
          <meshStandardMaterial color="#2f3741" metalness={0.4} roughness={0.5} />
        </mesh>
        <mesh position={[0.18, 0.55, -0.45]} rotation={[0, 0.5, 0]}>
          <boxGeometry args={[0.34, 0.34, 0.04]} />
          <meshStandardMaterial color="#2f3741" metalness={0.4} roughness={0.5} />
        </mesh>
      </group>

      {/* ─── SINGLE STACK / FUNNEL (amidships) ─── */}
      <group position={[-0.7, 0.62, 0]}>
        <Box pos={[0, 0.35, 0]} size={[0.7, 0.7, 0.74]} color="#586069" />
        <Box pos={[0, 0.78, 0]} size={[0.42, 0.3, 0.46]} color="#4a5158" rot={[0, 0, -0.12]} />
      </group>

      {/* ─── AFT SUPERSTRUCTURE + HANGAR + FLIGHT DECK ─── */}
      <group position={[-1.9, 0.6, 0]}>
        <Box pos={[0, 0.3, 0]} size={[1.1, 0.6, 0.95]} color={STEEL} />
        <Box pos={[-0.1, 0.66, 0]} size={[0.8, 0.2, 0.8]} color="#646b75" />
        {/* aft mast */}
        <mesh position={[0.35, 0.95, 0]}>
          <cylinderGeometry args={[0.025, 0.05, 0.46, 8]} />
          <meshStandardMaterial color="#6b727b" metalness={0.55} roughness={0.45} />
        </mesh>
      </group>

      {/* flight deck (stern) with hash markings */}
      <group position={[-2.85, 0.6, 0]}>
        <mesh position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.95, 1.1]} />
          <meshStandardMaterial color="#41474f" metalness={0.25} roughness={0.8} />
        </mesh>
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.22, 0.26, 32]} />
          <meshStandardMaterial color="#d4a000" emissive="#d4a000" emissiveIntensity={0.15} roughness={0.6} />
        </mesh>
      </group>

      {/* deck-edge rail hint (thin dark line down both sides) */}
      <Box pos={[0.1, 0.6, 0.74]} size={[6.2, 0.02, 0.02]} color="#2b3138" />
      <Box pos={[0.1, 0.6, -0.74]} size={[6.2, 0.02, 0.02]} color="#2b3138" />

      {/* ─── LIVE SUBSYSTEM ZONE MARKERS ─── */}
      {machinery ? <ZoneMarker position={[-1.9, 1.0, 0.0]} status={machinery} /> : null}
      {contacts ? <ZoneMarker position={[1.55, 1.05, 0.0]} status={contacts} /> : null}
    </group>
  );
}
