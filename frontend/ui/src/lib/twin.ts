import type { Severity, ShipSystem } from "./types";

/**
 * Digital-twin status colors (hex), aligned to the CIC palette. Honest standby
 * is DIM — never green. Caution = command amber. Critical = red. Nominal = green.
 * These drive the emissive hull-light intensity on the procedural warship.
 */
export const TWIN_STATUS: Record<Severity, { hex: string; rgb: [number, number, number]; glow: number }> = {
  nominal: { hex: "#3fb950", rgb: [0.247, 0.725, 0.314], glow: 1.0 },
  warning: { hex: "#d4a000", rgb: [0.831, 0.627, 0.0], glow: 1.15 },
  critical: { hex: "#e5484d", rgb: [0.898, 0.282, 0.302], glow: 1.5 },
  standby: { hex: "#3a4049", rgb: [0.227, 0.251, 0.286], glow: 0.18 },
};

export type TwinZone = "machinery" | "contacts";

/**
 * The two Pi nodes mapped onto hull zones. MACHINERY sits aft (engineering /
 * HM&E); CONTACTS sits forward (the sensor / tactical bow). These are the only
 * two zones lit live from /api/state — everything else is honest standby.
 */
export interface ZoneStatus {
  zone: TwinZone;
  label: string;
  /** node label e.g. "PI-1 · AFT" */
  node: string;
  severity: Severity;
  detail: string;
}

export function deriveZones(systems: ShipSystem[]): ZoneStatus[] {
  const find = (key: string) => systems.find((s) => s.key === key);
  const machinery = find("machinery") ?? find("propulsion");
  const contacts = find("contacts");
  return [
    {
      zone: "machinery",
      label: "MACHINERY · HM&E",
      node: "PI-1 · AFT",
      severity: machinery?.live ? machinery.severity : "standby",
      detail: machinery?.detail ?? "engineering organ",
    },
    {
      zone: "contacts",
      label: "CONTACTS · TACTICAL",
      node: "PI-2 · FWD",
      severity: contacts?.live ? contacts.severity : "standby",
      detail: contacts?.detail ?? "sensor organ",
    },
  ];
}
