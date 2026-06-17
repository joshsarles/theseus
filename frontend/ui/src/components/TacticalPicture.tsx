import { useLayoutEffect, useMemo, useRef, useState } from "react";
import DeckGL from "@deck.gl/react";
import { OrthographicView } from "@deck.gl/core";
import { ScatterplotLayer, PathLayer, LineLayer, TextLayer } from "@deck.gl/layers";
import { SectionHead } from "./Hairline";
import { CONTACT_RGB, CONTACT_LABEL } from "../lib/palette";
import { fmtLat, fmtLon } from "../lib/format";
import type { Contact, ContactType } from "../lib/types";

interface TacticalPictureProps {
  contacts: Contact[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const INK: [number, number, number] = [154, 160, 168];
const AMBER: [number, number, number] = [212, 160, 0];
const HAIR: [number, number, number] = [40, 49, 58];

/**
 * Geographic AIS plot in an orthographic projection. The contacts span CONUS
 * coasts, so we project lon/lat into a local equirectangular plane and frame
 * the bounding box. Clean vector symbology — diamonds for suspect/spoof (red),
 * neutral rings for routine tracks. No basemap tiles, no glow.
 */
export function TacticalPicture({ contacts, selectedId, onSelect }: TacticalPictureProps) {
  const [hover, setHover] = useState<Contact | null>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState<{ w: number; h: number }>({ w: 900, h: 520 });

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
    // re-measure after layout settles (flex grid resolves post first paint)
    raf = requestAnimationFrame(measure);
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  const plotted = useMemo(
    () => contacts.filter((c) => typeof c.lat === "number" && typeof c.lon === "number"),
    [contacts],
  );

  const { project, ownShip, bounds, graticule } = useMemo(() => {
    if (plotted.length === 0) {
      return {
        project: (_c: Contact) => [0, 0] as [number, number],
        ownShip: [0, 0] as [number, number],
        bounds: { minX: -1, maxX: 1, minY: -1, maxY: 1 },
        graticule: [] as { x: number; y: number; lon: number; lat: number }[],
      };
    }
    const lons = plotted.map((c) => c.lon as number);
    const lats = plotted.map((c) => c.lat as number);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const cLat = (minLat + maxLat) / 2;
    const cosLat = Math.cos((cLat * Math.PI) / 180);
    // equirectangular: x scales with cos(lat) so aspect is honest
    const proj = (lon: number, lat: number): [number, number] => [
      (lon - (minLon + maxLon) / 2) * cosLat * 60,
      -(lat - (minLat + maxLat) / 2) * 60,
    ];
    const project = (c: Contact) => proj(c.lon as number, c.lat as number);
    // own ship sits at the geographic centroid (notional CIC reference)
    const own = proj((minLon + maxLon) / 2, (minLat + maxLat) / 2);

    const xs = plotted.map((c) => project(c)[0]);
    const ys = plotted.map((c) => project(c)[1]);
    const pad = 80;
    const bounds = {
      minX: Math.min(...xs) - pad,
      maxX: Math.max(...xs) + pad,
      minY: Math.min(...ys) - pad,
      maxY: Math.max(...ys) + pad,
    };

    // graticule: integer-degree grid lines within the frame
    const grat: { x: number; y: number; lon: number; lat: number }[] = [];
    for (let lon = Math.ceil(minLon); lon <= Math.floor(maxLon); lon += 5) {
      const [x] = proj(lon, cLat);
      grat.push({ x, y: 0, lon, lat: NaN });
    }
    for (let lat = Math.ceil(minLat); lat <= Math.floor(maxLat); lat += 5) {
      const [, y] = proj((minLon + maxLon) / 2, lat);
      grat.push({ x: 0, y, lon: NaN, lat });
    }
    return { project, ownShip: own, bounds, graticule: grat };
  }, [plotted]);

  const viewState = useMemo(() => {
    const w = bounds.maxX - bounds.minX || 1;
    const h = bounds.maxY - bounds.minY || 1;
    const target: [number, number, number] = [
      (bounds.minX + bounds.maxX) / 2,
      (bounds.minY + bounds.maxY) / 2,
      0,
    ];
    // fit the world bbox into the measured viewport, in log2 zoom units
    const zoom = Math.log2(Math.min(dims.w / w, dims.h / h));
    return { target, zoom };
  }, [bounds, dims]);

  const grid = useMemo(() => {
    const lines: { sourcePosition: [number, number]; targetPosition: [number, number] }[] = [];
    const labels: { pos: [number, number]; text: string }[] = [];
    graticule.forEach((g) => {
      if (!Number.isNaN(g.lon)) {
        lines.push({
          sourcePosition: [g.x, bounds.minY],
          targetPosition: [g.x, bounds.maxY],
        });
        labels.push({
          pos: [g.x, bounds.maxY],
          text: `${Math.abs(g.lon)}°${g.lon < 0 ? "W" : "E"}`,
        });
      } else {
        lines.push({
          sourcePosition: [bounds.minX, g.y],
          targetPosition: [bounds.maxX, g.y],
        });
        labels.push({
          pos: [bounds.minX, g.y],
          text: `${Math.abs(g.lat)}°${g.lat < 0 ? "S" : "N"}`,
        });
      }
    });
    return { lines, labels };
  }, [graticule, bounds]);

  // own-ship range rings + bearing ticks (CIC theatre, hairline weight)
  const { rings, ringLabels, ticks } = useMemo(() => {
    const span = Math.min(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
    const maxR = (span / 2) * 0.92;
    const steps = [0.34, 0.67, 1].map((f) => maxR * f);
    const seg = 96;
    const rings = steps.map((r, ri) => {
      const path: [number, number][] = [];
      for (let i = 0; i <= seg; i++) {
        const a = (i / seg) * Math.PI * 2;
        path.push([ownShip[0] + Math.cos(a) * r, ownShip[1] + Math.sin(a) * r]);
      }
      return { path, ri };
    });
    // approximate nm: ~60 world units/deg, 60 nm/deg → 1 world unit ≈ 1 nm
    const ringLabels = steps.map((r) => ({
      pos: [ownShip[0], ownShip[1] - r] as [number, number],
      text: `${Math.round(r)} NM`,
    }));
    const ticks: { source: [number, number]; target: [number, number] }[] = [];
    for (let b = 0; b < 360; b += 30) {
      const a = ((b - 90) * Math.PI) / 180;
      const inner = b % 90 === 0 ? maxR * 0.9 : maxR * 0.96;
      ticks.push({
        source: [ownShip[0] + Math.cos(a) * inner, ownShip[1] + Math.sin(a) * inner],
        target: [ownShip[0] + Math.cos(a) * maxR, ownShip[1] + Math.sin(a) * maxR],
      });
    }
    return { rings, ringLabels, ticks };
  }, [bounds, ownShip]);

  const positions = useMemo(
    () => plotted.map((c) => ({ ...c, pos: project(c) })),
    [plotted, project],
  );

  const suspect = positions.filter((c) => c.type === "position_jump");
  const flagged = positions.filter((c) => c.type === "dark_gap" || c.type === "overspeed");
  const routine = positions.filter((c) => c.type === "loiter");

  const layers = [
    // graticule
    new LineLayer({
      id: "graticule",
      data: grid.lines,
      getSourcePosition: (d: { sourcePosition: [number, number] }) => d.sourcePosition,
      getTargetPosition: (d: { targetPosition: [number, number] }) => d.targetPosition,
      getColor: [...HAIR, 130] as [number, number, number, number],
      getWidth: 1,
      widthUnits: "pixels",
    }),
    // graticule degree labels
    new TextLayer({
      id: "graticule-labels",
      data: grid.labels,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getText: (d: { text: string }) => d.text,
      getSize: 8.5,
      getColor: [100, 107, 117] as [number, number, number],
      getPixelOffset: [10, 10],
      fontFamily: "JetBrains Mono, monospace",
      characterSet: "auto",
      getTextAnchor: "start",
      getAlignmentBaseline: "top",
    }),
    // own-ship range rings — hairline, the CIC theatre
    new PathLayer({
      id: "range-rings",
      data: rings,
      getPath: (d: { path: [number, number][] }) => d.path,
      getColor: (d: { ri: number }) =>
        [42, 49, 58, d.ri === 2 ? 200 : 130] as [number, number, number, number],
      getWidth: 1,
      widthUnits: "pixels",
    }),
    // bearing ticks around the outer ring
    new LineLayer({
      id: "bearing-ticks",
      data: ticks,
      getSourcePosition: (d: { source: [number, number] }) => d.source,
      getTargetPosition: (d: { target: [number, number] }) => d.target,
      getColor: [58, 64, 73, 220] as [number, number, number, number],
      getWidth: 1,
      widthUnits: "pixels",
    }),
    // range-ring labels
    new TextLayer({
      id: "ring-labels",
      data: ringLabels,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getText: (d: { text: string }) => d.text,
      getSize: 8,
      getColor: [70, 77, 87] as [number, number, number],
      getPixelOffset: [0, -7],
      fontFamily: "JetBrains Mono, monospace",
      characterSet: "auto",
      getTextAnchor: "middle",
      getAlignmentBaseline: "bottom",
    }),
    // routine tracks — neutral hollow rings (symbology, not blips)
    new ScatterplotLayer({
      id: "routine",
      data: routine,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getRadius: 4.5,
      radiusUnits: "pixels",
      stroked: true,
      filled: true,
      getFillColor: [10, 12, 16, 255] as [number, number, number, number],
      getLineColor: [...INK, 220] as [number, number, number, number],
      lineWidthUnits: "pixels",
      getLineWidth: 1.1,
      pickable: true,
      onClick: (info: { object?: Contact }) => info.object && onSelect(info.object.id),
      onHover: (info: { object?: Contact }) => setHover(info.object ?? null),
    }),
    // flagged (dark gap / overspeed) — amber caution chevrons
    new PathLayer({
      id: "flagged-glyphs",
      data: flagged,
      getPath: (d: { pos: [number, number] }) => chevron(d.pos, 7),
      getColor: AMBER,
      getWidth: 1.4,
      widthUnits: "pixels",
      pickable: true,
      onClick: (info: { object?: Contact }) => info.object && onSelect(info.object.id),
      onHover: (info: { object?: Contact }) => setHover(info.object ?? null),
    }),
    // suspect/spoof — RED diamond (drawn via PathLayer)
    new PathLayer({
      id: "suspect-glyphs",
      data: suspect,
      getPath: (d: { pos: [number, number] }) => diamond(d.pos, 10),
      getColor: CONTACT_RGB.position_jump as [number, number, number],
      getWidth: 1.8,
      widthUnits: "pixels",
      pickable: true,
      onClick: (info: { object?: Contact }) => info.object && onSelect(info.object.id),
      onHover: (info: { object?: Contact }) => setHover(info.object ?? null),
    }),
    // suspect labels — make the spoof/jump beat unmistakable
    new TextLayer({
      id: "suspect-labels",
      data: suspect,
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getText: () => "SPOOF?",
      getSize: 8.5,
      getColor: CONTACT_RGB.position_jump as [number, number, number],
      getPixelOffset: [14, -10],
      fontFamily: "JetBrains Mono, monospace",
      characterSet: "auto",
      getTextAnchor: "start",
      getAlignmentBaseline: "center",
    }),
    // selection bracket
    selectedId
      ? new PathLayer({
          id: "selection",
          data: positions.filter((c) => c.id === selectedId),
          getPath: (d: { pos: [number, number] }) => bracket(d.pos, 13),
          getColor: AMBER,
          getWidth: 1.4,
          widthUnits: "pixels",
        })
      : null,
    // own-ship marker — amber cross-in-circle
    new ScatterplotLayer({
      id: "ownship-ring",
      data: [{ pos: ownShip }],
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getRadius: 7,
      radiusUnits: "pixels",
      stroked: true,
      filled: false,
      getLineColor: AMBER,
      lineWidthUnits: "pixels",
      getLineWidth: 1.4,
    }),
    new TextLayer({
      id: "ownship-label",
      data: [{ pos: ownShip }],
      getPosition: (d: { pos: [number, number] }) => d.pos,
      getText: () => "OWN",
      getSize: 10,
      getColor: AMBER,
      getPixelOffset: [0, -16],
      fontFamily: "JetBrains Mono, monospace",
      characterSet: "auto",
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
    }),
  ].filter(Boolean);

  const counts = {
    suspect: suspect.length,
    flagged: flagged.length,
    routine: routine.length,
  };

  return (
    <section style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      <SectionHead
        index="03"
        title="Tactical Picture · AIS"
        meta={`${plotted.length} TRACKS PLOTTED`}
      />
      <div
        ref={frameRef}
        style={{ position: "relative", flex: 1, minHeight: 0, background: "var(--base)" }}
      >
        <DeckGL
          // re-key on the fitted view so the plot re-fits when the panel resizes
          key={`${dims.w}x${dims.h}-${plotted.length}`}
          views={new OrthographicView({ id: "ortho", flipY: false })}
          initialViewState={viewState}
          controller={{ doubleClickZoom: false }}
          layers={layers}
          width={dims.w}
          height={dims.h}
          style={{ position: "absolute", top: "0", left: "0" }}
          getCursor={({ isHovering }) => (isHovering ? "pointer" : "crosshair")}
        />

        {/* legend — bottom-left, monospace */}
        <Legend counts={counts} />

        {/* hover / select readout — top-right */}
        {hover ? <HoverCard c={hover} /> : null}

        {/* scale/frame ticks */}
        <FrameTicks />
      </div>
    </section>
  );
}

function diamond(pos: [number, number], r: number): [number, number][] {
  const [x, y] = pos;
  // PathLayer paths are in world units; r is tuned to the fitted zoom.
  const s = r;
  return [
    [x, y + s],
    [x + s, y],
    [x, y - s],
    [x - s, y],
    [x, y + s],
  ];
}

/** Hollow upward chevron/triangle — caution glyph for flagged tracks. */
function chevron(pos: [number, number], r: number): [number, number][] {
  const [x, y] = pos;
  const s = r;
  return [
    [x - s, y - s * 0.7],
    [x, y + s],
    [x + s, y - s * 0.7],
    [x - s, y - s * 0.7],
  ];
}

function bracket(pos: [number, number], r: number): [number, number][] {
  // open corner bracket (tactical selection)
  const [x, y] = pos;
  const s = r;
  const a = s * 0.55;
  // single path tracing four corners with gaps — approximate with a square ring
  return [
    [x - s, y - s + a],
    [x - s, y - s],
    [x - s + a, y - s],
    [x + s - a, y - s],
    [x + s, y - s],
    [x + s, y - s + a],
    [x + s, y + s - a],
    [x + s, y + s],
    [x + s - a, y + s],
    [x - s + a, y + s],
    [x - s, y + s],
    [x - s, y + s - a],
  ];
}

function Legend({ counts }: { counts: { suspect: number; flagged: number; routine: number } }) {
  const rows: { glyph: string; color: string; label: string; n: number }[] = [
    { glyph: "◆", color: "var(--critical)", label: "SUSPECT · SPOOF / JUMP", n: counts.suspect },
    { glyph: "○", color: "var(--amber)", label: "FLAGGED · GAP / OVERSPEED", n: counts.flagged },
    { glyph: "○", color: "var(--ink-dim)", label: "ROUTINE · LOITER", n: counts.routine },
    { glyph: "⊕", color: "var(--amber)", label: "OWN SHIP", n: 1 },
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
          <span className="mono" style={{ fontSize: 9.5, color: "var(--ink-dim)", letterSpacing: "0.04em", flex: 1 }}>
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

function HoverCard({ c }: { c: Contact }) {
  const color = c.type === "position_jump" ? "var(--critical)" : "var(--amber)";
  return (
    <div
      style={{
        position: "absolute",
        right: 12,
        top: 12,
        maxWidth: 280,
        border: "1px solid var(--hair-lit)",
        background: "rgba(10,12,16,0.92)",
        padding: "10px 12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color, border: `1px solid ${color}`, padding: "1px 6px" }}>
          {CONTACT_LABEL[c.type as ContactType]}
        </span>
        <span className="num" style={{ fontSize: 11, color: "var(--ink)" }}>
          MMSI {c.mmsi}
        </span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginBottom: 5 }}>
        {fmtLat(c.lat as number)} · {fmtLon(c.lon as number)}
      </div>
      <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-dim)", lineHeight: 1.45 }}>
        {c.why}
      </div>
    </div>
  );
}

function FrameTicks() {
  return (
    <div className="mono" style={{ position: "absolute", left: 12, top: 10, fontSize: 9, color: "var(--muted)", letterSpacing: "0.1em" }}>
      ORTHO · EQUIRECT · CONUS COASTAL
    </div>
  );
}
