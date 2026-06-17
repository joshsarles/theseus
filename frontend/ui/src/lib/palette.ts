import type { ContactType, Severity } from "./types";

/**
 * THESEUS · Combat Information Center palette.
 * Warm off-black base, ONE owned accent (command amber), and status colors
 * that carry MEANING ONLY. No cyan, no neon, no gradients, no glow.
 */
export const COLORS = {
  base: "#0a0c10", // warm off-black
  panel: "#0d1015",
  hairline: "#1e232b",
  hairlineLit: "#2b3138",

  amber: "#d4a000", // command amber — live / action / focus ONLY
  amberDim: "#7a5e0c",

  nominal: "#3fb950", // green — meaning: nominal
  caution: "#d4a000", // amber doubles as caution per spec
  critical: "#e5484d", // red — meaning: critical / spoof / jump

  ink: "#e6e8ea", // primary text
  inkDim: "#9aa0a8", // secondary text
  muted: "#646b75", // tertiary / labels
  faint: "#3a4049", // standby / disabled
} as const;

export const SEVERITY_COLOR: Record<Severity, string> = {
  nominal: COLORS.nominal,
  warning: COLORS.caution,
  critical: COLORS.critical,
  standby: COLORS.faint,
};

export const SEVERITY_RGB: Record<Severity, [number, number, number]> = {
  nominal: [63, 185, 80],
  warning: [212, 160, 0],
  critical: [229, 72, 77],
  standby: [58, 64, 73],
};

/**
 * Contact symbology color. Spoof/jump are RED. Everything else is rendered in
 * neutral ink on the plot (vector symbology, not colored blips) — color is
 * reserved for the things that actually demand attention.
 */
export const CONTACT_COLOR: Record<ContactType, string> = {
  position_jump: COLORS.critical,
  dark_gap: COLORS.caution,
  overspeed: COLORS.caution,
  loiter: COLORS.inkDim,
};

export const CONTACT_RGB: Record<ContactType, [number, number, number]> = {
  position_jump: [229, 72, 77],
  dark_gap: [212, 160, 0],
  overspeed: [212, 160, 0],
  loiter: [154, 160, 168],
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

/** MIL-STD-ish glyph hint per contact type for the symbology legend. */
export const CONTACT_GLYPH: Record<ContactType, string> = {
  position_jump: "◆", // diamond = unknown / suspect
  dark_gap: "▽",
  overspeed: "△",
  loiter: "○",
};
