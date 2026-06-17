import type { ContactType, Severity } from "./types";

/** Single source of truth for colors (hex + rgb tuples for canvas/deck.gl). */
export const COLORS = {
  base: "#0a0e27",
  cyan: "#00d9ff",
  danger: "#e63946",
  nominal: "#1aba45",
  warning: "#f4a261",
  ink: "#e8eef7",
  muted: "#8a92a8",
  faint: "#5a6a8a",
} as const;

export const SEVERITY_COLOR: Record<Severity, string> = {
  nominal: COLORS.nominal,
  warning: COLORS.warning,
  critical: COLORS.danger,
  standby: COLORS.faint,
};

export const SEVERITY_RGB: Record<Severity, [number, number, number]> = {
  nominal: [26, 186, 69],
  warning: [244, 162, 97],
  critical: [230, 57, 70],
  standby: [90, 106, 138],
};

export const CONTACT_COLOR: Record<ContactType, string> = {
  position_jump: COLORS.danger,
  dark_gap: COLORS.warning,
  loiter: COLORS.cyan,
  overspeed: "#e9c46a",
};

export const CONTACT_RGB: Record<ContactType, [number, number, number]> = {
  position_jump: [230, 57, 70],
  dark_gap: [244, 162, 97],
  loiter: [0, 217, 255],
  overspeed: [233, 196, 106],
};

/** Sort weight — most urgent first. */
export const CONTACT_ORDER: Record<ContactType, number> = {
  position_jump: 0,
  dark_gap: 1,
  overspeed: 2,
  loiter: 3,
};

export const CONTACT_LABEL: Record<ContactType, string> = {
  position_jump: "POSITION JUMP",
  dark_gap: "DARK GAP",
  overspeed: "OVERSPEED",
  loiter: "LOITER",
};
