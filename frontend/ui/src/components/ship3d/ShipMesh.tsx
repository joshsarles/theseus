import { useMemo } from "react";
import * as THREE from "three";

const HULL_COLOR = "#3c4a72";
const HULL_DARK = "#283354";
const DECK_COLOR = "#46567f";
const MAST_COLOR = "#52639a";

/** Reusable PBR-ish material for hull plating, with a faint cool emissive so edges catch the rim light. */
function hullMaterial(color: string, opts?: { metal?: number; rough?: number }) {
  return (
    <meshStandardMaterial
      color={color}
      metalness={opts?.metal ?? 0.7}
      roughness={opts?.rough ?? 0.34}
      emissive="#0b1c3a"
      emissiveIntensity={0.35}
      envMapIntensity={0.9}
    />
  );
}

/**
 * Procedural low-poly warship from primitives only (no external .glb):
 * a tapered hull, raked bow, layered superstructure, funnel, mast, and gun.
 * Oriented bow toward +Z, sitting on the y=0 plane (waterline).
 */
export function ShipMesh() {
  // Tapered hull built from a lathe-free extruded shape for a believable destroyer profile.
  const hullGeo = useMemo(() => {
    const shape = new THREE.Shape();
    // side profile (X = length, Y = height) — sheer line + raked bow + transom stern
    shape.moveTo(-3.4, 0);
    shape.lineTo(3.0, 0);
    shape.lineTo(3.9, 0.55); // bow rise
    shape.lineTo(3.95, 1.05);
    shape.lineTo(2.6, 1.0);
    shape.lineTo(-3.0, 0.78);
    shape.lineTo(-3.4, 0.5);
    shape.closePath();

    const geo = new THREE.ExtrudeGeometry(shape, {
      depth: 1.5,
      bevelEnabled: true,
      bevelThickness: 0.12,
      bevelSize: 0.18,
      bevelSegments: 2,
      steps: 1,
    });
    geo.center();
    geo.computeVertexNormals();
    return geo;
  }, []);

  return (
    <group rotation={[0, Math.PI / 2, 0]} position={[0, 0, 0]}>
      {/* HULL — extruded profile, beam along Z */}
      <mesh geometry={hullGeo} castShadow receiveShadow>
        {hullMaterial(HULL_COLOR, { metal: 0.5, rough: 0.5 })}
      </mesh>

      {/* taper the beam by overlaying a slightly narrower deck plate */}
      <mesh position={[0, 0.62, 0]}>
        <boxGeometry args={[6.2, 0.06, 1.15]} />
        {hullMaterial(DECK_COLOR, { metal: 0.4, rough: 0.6 })}
      </mesh>

      {/* MAIN DECKHOUSE — tumblehome (inward-sloping) superstructure block.
          A 4-sided cylinder frustum gives faceted, stealth-angled sides;
          scaled along X to elongate fore-aft. */}
      <mesh
        position={[0.2, 1.0, 0]}
        rotation={[0, Math.PI / 4, 0]}
        scale={[2.0, 1, 0.78]}
        castShadow
      >
        <cylinderGeometry args={[1.0, 1.3, 0.7, 4]} />
        {hullMaterial(HULL_DARK, { metal: 0.45, rough: 0.42 })}
      </mesh>
      {/* second tier */}
      <mesh
        position={[0.55, 1.58, 0]}
        rotation={[0, Math.PI / 4, 0]}
        scale={[1.7, 1, 0.7]}
        castShadow
      >
        <cylinderGeometry args={[0.6, 0.82, 0.6, 4]} />
        {hullMaterial(DECK_COLOR, { metal: 0.5, rough: 0.4 })}
      </mesh>
      {/* bridge pilot house — angled face */}
      <mesh position={[0.92, 2.05, 0]} rotation={[0, Math.PI / 4, 0]} castShadow>
        <cylinderGeometry args={[0.34, 0.5, 0.42, 4]} />
        {hullMaterial("#3e4d76", { metal: 0.55, rough: 0.36 })}
      </mesh>
      {/* bridge windscreen — emissive strip */}
      <mesh position={[1.15, 2.08, 0]} rotation={[0, 0, 0.18]}>
        <boxGeometry args={[0.04, 0.14, 0.42]} />
        <meshStandardMaterial
          color="#0a2a3a"
          emissive="#0aa6cf"
          emissiveIntensity={0.7}
          metalness={0.2}
          roughness={0.3}
        />
      </mesh>

      {/* angled phased-array radar faces on the deckhouse (Aegis-style) */}
      <mesh position={[1.32, 1.6, 0.18]} rotation={[0, -0.35, 0.15]}>
        <boxGeometry args={[0.04, 0.5, 0.5]} />
        <meshStandardMaterial
          color="#0c2436"
          metalness={0.2}
          roughness={0.3}
          emissive="#06303f"
          emissiveIntensity={0.5}
        />
      </mesh>
      <mesh position={[1.32, 1.6, -0.18]} rotation={[0, 0.35, 0.15]}>
        <boxGeometry args={[0.04, 0.5, 0.5]} />
        <meshStandardMaterial
          color="#0c2436"
          metalness={0.2}
          roughness={0.3}
          emissive="#06303f"
          emissiveIntensity={0.5}
        />
      </mesh>

      {/* INTEGRATED MAST — tapered tower with cross spar */}
      <mesh position={[0.55, 2.7, 0]}>
        <cylinderGeometry args={[0.07, 0.16, 1.5, 6]} />
        {hullMaterial(MAST_COLOR, { metal: 0.6, rough: 0.4 })}
      </mesh>
      <mesh position={[0.55, 3.0, 0]}>
        <boxGeometry args={[0.08, 0.08, 0.9]} />
        {hullMaterial(MAST_COLOR)}
      </mesh>
      {/* SPS-style rotating spinner suggestion */}
      <mesh position={[0.55, 3.5, 0]} rotation={[0, 0, 0]}>
        <boxGeometry args={[0.7, 0.05, 0.12]} />
        {hullMaterial("#46557d", { metal: 0.7, rough: 0.3 })}
      </mesh>

      {/* FUNNEL / exhaust uptake */}
      <mesh position={[-0.7, 1.45, 0]} rotation={[0, 0, -0.08]}>
        <boxGeometry args={[0.7, 0.95, 0.62]} />
        {hullMaterial("#222d49", { metal: 0.4, rough: 0.6 })}
      </mesh>

      {/* AFT hangar */}
      <mesh position={[-1.7, 1.05, 0]} castShadow>
        <boxGeometry args={[1.1, 0.6, 0.85]} />
        {hullMaterial(HULL_DARK, { metal: 0.35, rough: 0.55 })}
      </mesh>

      {/* FORWARD gun mount */}
      <mesh position={[2.35, 0.78, 0]} castShadow>
        <boxGeometry args={[0.55, 0.32, 0.5]} />
        {hullMaterial("#39456a")}
      </mesh>
      <mesh
        position={[2.85, 0.86, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[0.04, 0.04, 0.6, 8]} />
        {hullMaterial("#52608a", { metal: 0.8, rough: 0.25 })}
      </mesh>

      {/* VLS cell grid forward of bridge — emissive hint */}
      {Array.from({ length: 4 }).flatMap((_, i) =>
        Array.from({ length: 2 }).map((__, j) => (
          <mesh
            key={`vls-${i}-${j}`}
            position={[1.95 - i * 0.16, 0.84, -0.18 + j * 0.36]}
          >
            <boxGeometry args={[0.12, 0.03, 0.12]} />
            <meshStandardMaterial
              color="#0e2a38"
              emissive="#0a3b4d"
              emissiveIntensity={0.6}
              metalness={0.3}
              roughness={0.4}
            />
          </mesh>
        )),
      )}

      {/* glowing deck-edge sheer lines (signature neon) */}
      {[0.56, -0.56].map((z) => (
        <mesh key={`sheer-${z}`} position={[-0.1, 0.66, z]}>
          <boxGeometry args={[6.0, 0.012, 0.02]} />
          <meshBasicMaterial color="#00d9ff" transparent opacity={0.7} />
        </mesh>
      ))}

      {/* waterline glow strip */}
      <mesh position={[0, 0.06, 0]}>
        <boxGeometry args={[7.2, 0.02, 1.58]} />
        <meshBasicMaterial color="#0a6a8d" transparent opacity={0.6} />
      </mesh>
    </group>
  );
}
