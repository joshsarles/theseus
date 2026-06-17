/** Truncate a long hex string to head…tail form for display. */
export function shortHash(hex: string, head = 6, tail = 4): string {
  if (!hex) return "";
  if (hex.length <= head + tail + 1) return hex;
  return `${hex.slice(0, head)}…${hex.slice(-tail)}`;
}

/** Pull merkle / head hashes out of the record message string. */
export function parseRecordMessage(message: string): {
  head?: string;
  merkle?: string;
} {
  const head = /head ([0-9a-f]+)/i.exec(message)?.[1];
  const merkle = /merkle ([0-9a-f]+)/i.exec(message)?.[1];
  return { head, merkle };
}

/** Latitude to N/S DMS-ish compact string. */
export function fmtLat(lat: number): string {
  const h = lat >= 0 ? "N" : "S";
  return `${Math.abs(lat).toFixed(4)}°${h}`;
}

export function fmtLon(lon: number): string {
  const h = lon >= 0 ? "E" : "W";
  return `${Math.abs(lon).toFixed(4)}°${h}`;
}

export function fmtPct(v: number): string {
  return `${Math.round(v * 100)}%`;
}
