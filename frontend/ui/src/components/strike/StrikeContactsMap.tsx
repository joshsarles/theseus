import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import DeckGL from "@deck.gl/react";
import { OrthographicView } from "@deck.gl/core";
import { ScatterplotLayer, PathLayer, LineLayer, TextLayer } from "@deck.gl/layers";
import { SectionHead } from "../Hairline";
import { fmtLat, fmtLon } from "../../lib/format";
import { useStrikeContacts, type AisContact, type ContactsFeed, type OwnShip } from "../../hooks/useStrikeContacts";

/* ------------------------------------------------------------------ *
 *  THESEUS · STRIKE GROUP — TACTICAL CONTACTS MAP
 *
 *  A deck.gl orthographic AIS plot framing the operating area: ~45
 *  neutral tracks, a handful FLAGGED (spoof / position-jump / loiter /
 *  dark-gap) drawn in amber/red with a pulsing marker + short label, and
 *  the 3 own-ship destroyers (DDG-118/119/120) in a triangular screen
 *  formation as amber friendly markers. Same orthographic equirectangular
 *  projection + clean vector symbology as OPERATIONS · Tactical Picture —
 *  no basemap tiles, no glow, hairline range rings.
 *
 *  Live-vs-fixture honesty mirrors SimFeedBanner: the panel badge says
 *  LIVE only on a real 200 from /api/contacts; otherwise SIM FIXTURE.
 * ------------------------------------------------------------------ */

interface StrikeContactsMapProps {
  /** contacts subsystem severity from /api/destroyer (drives the readout tone) */
  contactsSeverity?: "nominal" | "warning" | "critical" | "standby";
}

const FRIENDLY: [number, number, number] = [212, 160, 0]; // command amber — own ships
const INK: [number, number, number] = [154, 160, 168]; // neutral tracks
const HAIR: [number, number, number] = [40, 49, 58];
const RED: [number, number, number] = [229, 72, 77];
const AMBER: [number, number, number] = [212, 160, 0];

export function StrikeContactsMap({ contactsSeverity = "critical" }: StrikeContactsMapProps) {
  const { feed, conn } = useStrikeContacts();
  const [hover, setHover] = useState<AisContact | null>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState<{ w: number; h: number }>({ w: 900, h: 460 });

  // --- pulse clock: a 0..1 sawtooth ramp driving the flagged-marker pulse ---
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    let raf = 0;
    let alive = true;
    const start = performance.now();
    const tick = (t: number) => {
      if (!alive) return;
      // ~1.4s period sine, mapped to 0..1
      const phase = ((t - start) / 1400) % 1;
      setPulse(0.5 - 0.5 * Math.cos(phase * Math.PI * 2));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
    };
  }, []);

  // --- measure the frame so the ortho plot fits the panel (TacticalPicture pattern) ---
  useLayoutEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    let raf = 0;
    const measure = () => {
      const r = el.getBoundingClientRect();
      if (r.width > 1 && r.height > 1) {
        setDims((prev) =>
          Math.abs(prev.w - r.width) > 1 || Math.abs(prev.h - r.height) > 1
            ? { w: r.width, h: r.height }
            : prev,
        );
      }
    };
    measure();
    raf = requestAnimationFrame(measure);
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  const contacts = feed.contacts;
  const ownShips = feed.ownShips;

  // --- equirectangular projection fitted to the operating area bbox ---
  const { project, bounds, centroid, graticule } = useMemo(() => {
    const lons = [...contacts.map((c) => c.lon), ...ownShips.map((s) => s.lon)];
    const lats = [...contacts.map((c) => c.lat), ...ownShips.map((s) => s.lat)];
    if (lons.length === 0) {
      return {
        project: (_lon: number, _lat: number) => [0, 0] as [number, number],
        bounds: { minX: -1, maxX: 1, minY: -1, maxY: 1 },
        centroid: [0, 0] as [number, number],
        graticule: [] as { x: number; y: number; lon: number; lat: number }[],
      };
    }
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const cLon = (minLon + maxLon) / 2;
    const cLat = (minLat + maxLat) / 2;
    const cosLat = Math.cos((cLat * Math.PI) / 180);
    // x scales with cos(lat) so the aspect ratio is geographically honest
    const project = (lon: number, lat: number): [number, number] => [
      (lon - cLon) * cosLat * 60,
      -(lat - cLat) * 60,
    ];
    const xs = lons.map((lon, i) => project(lon, lats[i])[0]);
    const ys = lons.map((lon, i) => project(lon, lats[i])[1]);
    const pad = 70;
    const bounds = {
      minX: Math.min(...xs) - pad,
      maxX: Math.max(...xs) + pad,
      minY: Math.min(...ys) - pad,
      maxY: Math.max(...ys) + pad,
    };
    const grat: { x: number; y: number; lon: number; lat: number }[] = [];
    const lonStep = Math.max(0.25, Math.round((maxLon - minLon) / 4 / 0.25) * 0.25);
    const latStep = Math.max(0.25, Math.round((maxLat - minLat) / 4 / 0.25) * 0.25);
    for (let lon = Math.ceil(minLon / lonStep) * lonStep; lon <= maxLon; lon += lonStep) {
      grat.push({ x: project(lon, cLat)[0], y: 0, lon, lat: NaN });
    }
    for (let lat = Math.ceil(minLat / latStep) * latStep; lat <= maxLat; lat += latStep) {
      grat.push({ x: 0, y: project(cLon, lat)[1], lon: NaN, lat });
    }
    return { project, bounds, centroid: project(cLon, cLat), graticule: grat };
  }, [contacts, ownShips]);

  const viewState = useMemo(() => {
    const w = bounds.maxX - bounds.minX || 1;
    const h = bounds.maxY - bounds.minY || 1;
    const target: [number, number, number] = [
      (bounds.minX + bounds.maxX) / 2,
      (bounds.minY + bounds.maxY) / 2,
      0,
    ];
    // guard against a degenerate frame (dims not measured yet) producing a
    // -Infinity / NaN zoom that flashes a blank/jumped plot on first paint
    const fit = Math.min(dims.w / w, dims.h / h);
    const zoom = Number.isFinite(fit) && fit > 0 ? Math.log2(fit) : 0;
    return { target, zoom };
  }, [bounds, dims]);

  // --- graticule lines + degree labels ---
  const grid = useMemo(() => {
    const lines: { source: [number, number]; target: [number, number] }[] = [];
    const labels: { pos: [number, number]; text: string }[] = [];
    graticule.forEach((g) => {
      if (!Number.isNaN(g.lon)) {
        lines.push({ source: [g.x, bounds.minY], target: [g.x, bounds.maxY] });
        labels.push({ pos: [g.x, bounds.maxY], text: `${Math.abs(g.lon).toFixed(2)}°${g.lon < 0 ? "W" : "E"}` });
      } else {
        lines.push({ source: [bounds.minX, g.y], target: [bounds.maxX, g.y] });
        labels.push({ pos: [bounds.minX, g.y], text: `${Math.abs(g.lat).toFixed(2)}°${g.lat < 0 ? "S" : "N"}` });
      }
    });
    return { lines, labels };
  }, [graticule, bounds]);

  // --- own-ship range rings around the formation centroid ---
  const rings = useMemo(() => {
    const span = Math.min(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
    const maxR = (span / 2) * 0.9;
    const seg = 96;
    return [0.4, 0.7, 1].map((f, ri) => {
      const r = maxR * f;
      const path: [number, number][] = [];
      for (let i = 0; i <= seg; i++) {
        const a = (i / seg) * Math.PI * 2;
        path.push([centroid[0] + Math.cos(a) * r, centroid[1] + Math.sin(a) * r]);
      }
      return { path, ri };
    });
  }, [bounds, centroid]);

  // --- projected positions ---
  const placed = useMemo(
    () => contacts.map((c) => ({ ...c, pos: project(c.lon, c.lat) })),
    [contacts, project],
  );
  const placedOwn = useMemo(
    () => ownShips.map((s) => ({ ...s, pos: project(s.lon, s.lat) })),
    [ownShips, project],
  );

  const neutral = placed.filter((c) => !c.flagged);
  const flagged = placed.filter((c) => c.flagged);

  // formation tie-lines so the three hulls read as one screen
  const formationLines = useMemo(() => {
    const lines: { source: [number, number]; target: [number, number] }[] = [];
    for (let i = 0; i < placedOwn.length; i++) {
      for (let j = i + 1; j < placedOwn.length; j++) {
        lines.push({ source: placedOwn[i].pos, target: placedOwn[j].pos });
      }
    }
    return lines;
  }, [placedOwn]);

  // pulsing geometry for flagged tracks — ring radius breathes with the clock
  const pulseRadius = 8 + pulse * 9;
  const pulseAlpha = Math.round(200 - pulse * 150);

  const layers = [
    // graticule
    new LineLayer({
      id: "sc-graticule",
      data: grid.lines,
      getSourcePosition: (d: { source: [number, number] }) => d.source,
      getTargetPosition: (d: { target: [number, number] }) => d.target,
      getColor: [...HAIR, 110] as [number, number, number, number],
      getWidth: 1,
      widthUnits: "pixels",
    }),
    new TextLayer({
      id: "sc-graticule-labels",
      data: grid.labels,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getText: (d: { text: string }) => d.text,
      getSize: 8.5,
      getColor: [100, 107, 117] as [number, number, number],
      getPixelOffset: [9, 9],
      fontFamily: "JetBrains Mono, monospace",
      characterSet: "auto",
      getTextAnchor: "start",
      getAlignmentBaseline: "top",
    }),
    // own-ship range rings — hairline CIC theatre
    new PathLayer({
      id: "sc-range-rings",
      data: rings,
      getPath: (d: { path: [number, number][] }) => d.path,
      getColor: (d: { ri: number }) =>
        [42, 49, 58, d.ri === 2 ? 190 : 120] as [number, number, number, number],
      getWidth: 1,
      widthUnits: "pixels",
    }),
    // formation tie-lines (amber-dim)
    new LineLayer({
      id: "sc-formation",
      data: formationLines,
      getSourcePosition: (d: { source: [number, number] }) => d.source,
      getTargetPosition: (d: { target: [number, number] }) => d.target,
      getColor: [111, 84, 16, 150] as [number, number, number, number],
      getWidth: 1,
      widthUnits: "pixels",
    }),
    // neutral tracks — hollow ink rings (vector symbology, not blips)
    new ScatterplotLayer({
      id: "sc-neutral",
      data: neutral,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getRadius: 3.6,
      radiusUnits: "pixels",
      stroked: true,
      filled: true,
      getFillColor: [10, 12, 16, 255] as [number, number, number, number],
      getLineColor: [...INK, 200] as [number, number, number, number],
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      pickable: true,
      onHover: (info: { object?: AisContact }) => setHover(info.object ?? null),
    }),
    // flagged pulse halo — breathing ring (red for spoof/jump, amber otherwise)
    new ScatterplotLayer({
      id: "sc-flagged-pulse",
      data: flagged,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getRadius: pulseRadius,
      radiusUnits: "pixels",
      stroked: true,
      filled: false,
      getLineColor: (d: AisContact) =>
        [...(isHot(d) ? RED : AMBER), pulseAlpha] as [number, number, number, number],
      lineWidthUnits: "pixels",
      getLineWidth: 1.4,
      updateTriggers: { getRadius: pulseRadius, getLineColor: pulseAlpha },
    }),
    // flagged core marker
    new ScatterplotLayer({
      id: "sc-flagged-core",
      data: flagged,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getRadius: 5,
      radiusUnits: "pixels",
      stroked: true,
      filled: true,
      getFillColor: (d: AisContact) =>
        [...(isHot(d) ? RED : AMBER), 230] as [number, number, number, number],
      getLineColor: [10, 12, 16, 255] as [number, number, number, number],
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      pickable: true,
      onHover: (info: { object?: AisContact }) => setHover(info.object ?? null),
    }),
    // flagged labels — "MMSI … · POSSIBLE SPOOF"
    new TextLayer({
      id: "sc-flagged-labels",
      data: flagged,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getText: (d: AisContact) => `MMSI ${d.mmsi} · ${reasonShort(d)}`,
      getSize: 8.5,
      getColor: (d: AisContact) => (isHot(d) ? RED : AMBER) as [number, number, number],
      getPixelOffset: [13, -12],
      fontFamily: "JetBrains Mono, monospace",
      characterSet: "auto",
      getTextAnchor: "start",
      getAlignmentBaseline: "center",
    }),
    // own-ship friendly markers — amber chevrons (formation screen)
    new PathLayer({
      id: "sc-own-glyphs",
      data: placedOwn,
      getPath: (d: { pos: [number, number] }) => friendlyGlyph(d.pos, 9),
      getColor: FRIENDLY,
      getWidth: 1.6,
      widthUnits: "pixels",
      pickable: false,
    }),
    new TextLayer({
      id: "sc-own-labels",
      data: placedOwn,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getText: (d: OwnShip) => `${d.hull}${d.flagship ? " ◆" : ""}`,
      getSize: 9,
      getColor: FRIENDLY,
      getPixelOffset: [0, 15],
      fontFamily: "JetBrains Mono, monospace",
      characterSet: "auto",
      getTextAnchor: "middle",
      getAlignmentBaseline: "top",
    }),
  ];

  const flaggedN = flagged.length;
  const readoutTone =
    contactsSeverity === "critical"
      ? "var(--critical)"
      : contactsSeverity === "warning"
        ? "var(--caution)"
        : "var(--nominal)";

  return (
    <section style={{ display: "flex", flexDirection: "column", minHeight: 0, background: "var(--base)" }}>
      <SectionHead
        index="04"
        title="Tactical Contacts · AIS"
        meta={`${contacts.length} TRACKS · ${flagged.length} FLAGGED`}
      />
      <div
        ref={frameRef}
        style={{ position: "relative", height: 460, minHeight: 0, background: "var(--base)" }}
      >
        <DeckGL
          key={`${dims.w}x${dims.h}-${contacts.length}-${ownShips.length}`}
          views={new OrthographicView({ id: "sc-ortho", flipY: false })}
          initialViewState={viewState}
          controller={{ doubleClickZoom: false }}
          layers={layers}
          width={dims.w}
          height={dims.h}
          style={{ position: "absolute", top: "0", left: "0" }}
          getCursor={({ isHovering }) => (isHovering ? "pointer" : "crosshair")}
        />

        {/* frame caption + live/fixture badge — top-left */}
        <div className="mono" style={{ position: "absolute", left: 12, top: 10, fontSize: 9, color: "var(--muted)", letterSpacing: "0.1em", display: "flex", alignItems: "center", gap: 10 }}>
          <span>ORTHO · EQUIRECT · OPERATING AREA</span>
          <FeedBadge conn={conn} />
        </div>

        {/* N tracks · M flagged readout — top-right */}
        <div
          style={{
            position: "absolute",
            right: 12,
            top: 10,
            border: "1px solid var(--hair)",
            background: "rgba(10,12,16,0.82)",
            padding: "6px 10px",
            display: "flex",
            alignItems: "baseline",
            gap: 8,
          }}
        >
          <span className="num" style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>
            {contacts.length}
          </span>
          <span className="mono" style={{ fontSize: 9, color: "var(--muted)", letterSpacing: "0.08em" }}>
            TRACKS
          </span>
          <span className="mono" style={{ fontSize: 9, color: "var(--muted)" }}>·</span>
          <span className="num" style={{ fontSize: 15, fontWeight: 500, color: flaggedN ? readoutTone : "var(--muted)" }}>
            {flaggedN}
          </span>
          <span className="mono" style={{ fontSize: 9, color: flaggedN ? readoutTone : "var(--muted)", letterSpacing: "0.08em" }}>
            FLAGGED
          </span>
        </div>

        {/* legend — bottom-left */}
        <Legend
          friendly={ownShips.length}
          neutral={neutral.length}
          flagged={flaggedN}
          hot={flagged.some(isHot)}
        />

        {/* hover readout — bottom-right */}
        {hover ? <HoverCard c={hover} /> : null}
      </div>
    </section>
  );
}

/* ---------------- helpers ---------------- */

/** Hot = red beat (spoof / position-jump). Everything else flagged is amber. */
function isHot(c: AisContact): boolean {
  return c.reason === "spoof" || c.reason === "position_jump";
}

const REASON_SHORT: Record<NonNullable<AisContact["reason"]>, string> = {
  spoof: "POSSIBLE SPOOF",
  position_jump: "POSITION JUMP",
  loiter: "LOITER",
  dark_gap: "DARK GAP",
};

function reasonShort(c: AisContact): string {
  return c.reason ? REASON_SHORT[c.reason] : "FLAGGED";
}

const REASON_LABEL = REASON_SHORT;

/** A small upward chevron-in-bar — friendly own-ship glyph (NTDS-ish). */
function friendlyGlyph(pos: [number, number], r: number): [number, number][] {
  const [x, y] = pos;
  // semicircle-ish "friendly" arc rendered as a chevron + base
  return [
    [x - r, y + r * 0.5],
    [x - r, y - r * 0.2],
    [x, y - r],
    [x + r, y - r * 0.2],
    [x + r, y + r * 0.5],
  ];
}

function FeedBadge({ conn }: { conn: ContactsFeed["conn"] }) {
  const live = conn === "live";
  const color = live ? "var(--nominal)" : "var(--caution)";
  return (
    <span
      className="mono"
      style={{
        fontSize: 8,
        letterSpacing: "0.12em",
        color,
        border: `1px solid ${color}`,
        padding: "1px 6px",
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
      }}
    >
      <span style={{ width: 5, height: 5, background: color, display: "inline-block" }} />
      {live ? "LIVE · /api/contacts" : "SIM FIXTURE"}
    </span>
  );
}

function Legend({ friendly, neutral, flagged, hot }: { friendly: number; neutral: number; flagged: number; hot: boolean }) {
  // flagged swatch is honest: red only when a hot beat (spoof/jump) is present,
  // otherwise amber — matching the marker color actually drawn on the plot
  const flaggedColor = flagged === 0 ? "var(--muted)" : hot ? "var(--critical)" : "var(--amber)";
  const rows: { glyph: string; color: string; label: string; n: number }[] = [
    { glyph: "△", color: "var(--amber)", label: "FRIENDLY · OWN SHIP", n: friendly },
    { glyph: "○", color: "var(--ink-dim)", label: "NEUTRAL · AIS TRACK", n: neutral },
    { glyph: "◉", color: flaggedColor, label: "FLAGGED · ANOMALY", n: flagged },
  ];
  return (
    <div
      style={{
        position: "absolute",
        left: 12,
        bottom: 12,
        border: "1px solid var(--hair)",
        background: "rgba(10,12,16,0.82)",
        padding: "9px 11px",
      }}
    >
      <div className="eyebrow" style={{ marginBottom: 7, fontSize: 9 }}>
        Symbology
      </div>
      {rows.map((r) => (
        <div key={r.label} style={{ display: "flex", alignItems: "center", gap: 9, padding: "2px 0" }}>
          <span className="mono" style={{ color: r.color, fontSize: 11, width: 12, textAlign: "center" }}>
            {r.glyph}
          </span>
          <span
            className="mono"
            style={{ fontSize: 9.5, color: "var(--ink-dim)", letterSpacing: "0.04em", flex: 1 }}
          >
            {r.label}
          </span>
          <span className="num" style={{ fontSize: 10.5, color: "var(--ink)", marginLeft: 12 }}>
            {String(r.n).padStart(2, "0")}
          </span>
        </div>
      ))}
    </div>
  );
}

function HoverCard({ c }: { c: AisContact }) {
  const color = c.flagged ? (isHot(c) ? "var(--critical)" : "var(--amber)") : "var(--ink-dim)";
  return (
    <div
      style={{
        position: "absolute",
        right: 12,
        bottom: 12,
        maxWidth: 290,
        border: "1px solid var(--hair-lit)",
        background: "rgba(10,12,16,0.92)",
        padding: "10px 12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span
          className="mono"
          style={{
            fontSize: 9,
            letterSpacing: "0.12em",
            color,
            border: `1px solid ${color}`,
            padding: "1px 6px",
          }}
        >
          {c.flagged && c.reason ? REASON_LABEL[c.reason] : c.vessel_class.toUpperCase()}
        </span>
        <span className="num" style={{ fontSize: 11, color: "var(--ink)" }}>
          MMSI {c.mmsi}
        </span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginBottom: c.why ? 5 : 0 }}>
        {fmtLat(c.lat)} · {fmtLon(c.lon)}
      </div>
      {c.why ? (
        <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-dim)", lineHeight: 1.45 }}>
          {c.why}
        </div>
      ) : null}
    </div>
  );
}
