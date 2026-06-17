import { useEffect, useMemo, useRef, useState } from "react";
import { Deck, OrthographicView } from "@deck.gl/core";
import { ScatterplotLayer, LineLayer, TextLayer } from "@deck.gl/layers";
import type { Contact, ContactType } from "../lib/types";
import { CONTACT_RGB, CONTACT_LABEL, COLORS } from "../lib/palette";

interface TacticalPictureProps {
  contacts: Contact[];
  onHover?: (c: Contact | null) => void;
}

interface PlotPoint {
  contact: Contact;
  x: number;
  y: number;
}

/** Equirectangular lat/lon -> normalized plot coords with padding. */
function project(contacts: Contact[]) {
  const pts = contacts.filter(
    (c) => c.lat != null && c.lon != null,
  ) as (Contact & { lat: number; lon: number })[];
  if (pts.length === 0) {
    return { points: [] as PlotPoint[], own: { x: 0, y: 0 } };
  }
  const lats = pts.map((p) => p.lat);
  const lons = pts.map((p) => p.lon);
  let laMin = Math.min(...lats),
    laMax = Math.max(...lats),
    loMin = Math.min(...lons),
    loMax = Math.max(...lons);
  const dla = laMax - laMin || 1;
  const dlo = loMax - loMin || 1;
  const pad = 0.08;
  laMin -= dla * pad;
  laMax += dla * pad;
  loMin -= dlo * pad;
  loMax += dlo * pad;

  // map into a fixed [-100,100] world; deck fits it to the viewport
  const W = 200;
  const H = 130;
  const X = (lon: number) => ((lon - loMin) / (loMax - loMin)) * W - W / 2;
  const Y = (lat: number) => ((lat - laMin) / (laMax - laMin)) * H - H / 2;

  const points: PlotPoint[] = pts.map((c) => ({
    contact: c,
    x: X(c.lon),
    y: Y(c.lat),
  }));
  const own = { x: X((loMin + loMax) / 2), y: Y((laMin + laMax) / 2) };
  return { points, own };
}

const TARGET = [0, 0, 0] as [number, number, number];

export function TacticalPicture({ contacts, onHover }: TacticalPictureProps) {
  const ref = useRef<HTMLDivElement>(null);
  const deckRef = useRef<Deck<OrthographicView> | null>(null);
  const [hovered, setHovered] = useState<{
    c: Contact;
    x: number;
    y: number;
  } | null>(null);

  const { points, own } = useMemo(() => project(contacts), [contacts]);

  // grid lines as a LineLayer (world coords)
  const gridData = useMemo(() => {
    const lines: { from: [number, number]; to: [number, number] }[] = [];
    for (let i = -100; i <= 100; i += 20)
      lines.push({ from: [i, -65], to: [i, 65] });
    for (let j = -60; j <= 60; j += 20)
      lines.push({ from: [-100, j], to: [100, j] });
    return lines;
  }, []);

  // own-ship reticle cross
  const reticle = useMemo(
    () => [
      { from: [own.x - 7, own.y], to: [own.x + 7, own.y] },
      { from: [own.x, own.y - 7], to: [own.x, own.y + 7] },
    ],
    [own],
  );

  useEffect(() => {
    if (!ref.current) return;
    const deck = new Deck({
      parent: ref.current,
      views: new OrthographicView({ flipY: true }),
      initialViewState: { target: TARGET, zoom: 1.6, minZoom: 0, maxZoom: 6 },
      controller: { dragRotate: false, scrollZoom: true },
      style: { position: "absolute", inset: "0", background: "transparent" },
      getCursor: ({ isHovering }) => (isHovering ? "pointer" : "default"),
      layers: [],
    });
    deckRef.current = deck;
    return () => {
      deck.finalize();
      deckRef.current = null;
    };
  }, []);

  useEffect(() => {
    const deck = deckRef.current;
    if (!deck) return;

    const haloLayer = new ScatterplotLayer<PlotPoint>({
      id: "halo",
      data: points,
      getPosition: (d) => [d.x, d.y, 0],
      getRadius: (d) =>
        d.contact.type === "position_jump"
          ? 5.5
          : d.contact.type === "dark_gap"
            ? 4.2
            : 3.2,
      radiusUnits: "common",
      getFillColor: (d) => {
        const [r, g, b] = CONTACT_RGB[d.contact.type];
        return [r, g, b, 60];
      },
      stroked: false,
      pickable: false,
      updateTriggers: { getFillColor: points.length },
    });

    const contactLayer = new ScatterplotLayer<PlotPoint>({
      id: "contacts",
      data: points,
      getPosition: (d) => [d.x, d.y, 0],
      getRadius: (d) => (d.contact.type === "position_jump" ? 2.4 : 1.7),
      radiusUnits: "common",
      radiusMinPixels: 3,
      radiusMaxPixels: 14,
      getFillColor: (d) => [...CONTACT_RGB[d.contact.type], 235],
      getLineColor: (d) => {
        const [r, g, b] = CONTACT_RGB[d.contact.type];
        return [Math.min(r + 60, 255), Math.min(g + 60, 255), Math.min(b + 60, 255), 255];
      },
      lineWidthUnits: "common",
      getLineWidth: 0.4,
      stroked: true,
      pickable: true,
      onHover: (info) => {
        if (info.object) {
          const p = info.object as PlotPoint;
          setHovered({ c: p.contact, x: info.x, y: info.y });
          onHover?.(p.contact);
        } else {
          setHovered(null);
          onHover?.(null);
        }
      },
      updateTriggers: { getFillColor: points.length },
    });

    const gridLayer = new LineLayer({
      id: "grid",
      data: gridData,
      getSourcePosition: (d) => [...d.from, 0] as [number, number, number],
      getTargetPosition: (d) => [...d.to, 0] as [number, number, number],
      getColor: [255, 255, 255, 14],
      getWidth: 1,
    });

    const reticleLayer = new LineLayer({
      id: "reticle",
      data: reticle,
      getSourcePosition: (d) => [...d.from, 0] as [number, number, number],
      getTargetPosition: (d) => [...d.to, 0] as [number, number, number],
      getColor: [0, 217, 255, 230],
      getWidth: 1.5,
    });

    const ownLayer = new ScatterplotLayer({
      id: "own",
      data: [{ position: [own.x, own.y, 0] as [number, number, number] }],
      getPosition: (d) => d.position,
      getRadius: 5,
      radiusUnits: "common",
      stroked: true,
      filled: false,
      getLineColor: [0, 217, 255, 255],
      lineWidthUnits: "common",
      getLineWidth: 0.5,
    });

    const ownLabel = new TextLayer({
      id: "own-label",
      data: [{ position: [own.x + 8, own.y + 6, 0] as [number, number, number] }],
      getPosition: (d) => d.position,
      getText: () => "OWN SHIP",
      getSize: 11,
      getColor: [0, 217, 255, 230],
      getTextAnchor: "start",
      getAlignmentBaseline: "center",
      fontFamily: "Geist Mono, monospace",
      characterSet: "auto",
    });

    deck.setProps({
      layers: [
        gridLayer,
        haloLayer,
        reticleLayer,
        ownLayer,
        contactLayer,
        ownLabel,
      ],
    });
  }, [points, gridData, reticle, own, onHover]);

  const typeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const ct of contacts) c[ct.type] = (c[ct.type] ?? 0) + 1;
    return c;
  }, [contacts]);

  return (
    <div className="relative h-full w-full">
      {/* deck canvas mount */}
      <div
        ref={ref}
        className="absolute inset-0 overflow-hidden rounded-lg"
        style={{
          background:
            "radial-gradient(120% 120% at 50% 40%, #0c1a36 0%, #070d20 70%, #050a18 100%)",
          border: "1px solid rgba(0,217,255,0.10)",
        }}
      />

      {/* radar sweep accent */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden rounded-lg">
        <div
          className="h-[140%] w-[140%] animate-sweep opacity-40"
          style={{
            background:
              "conic-gradient(from 0deg, rgba(0,217,255,0.16) 0deg, rgba(0,217,255,0) 42deg, rgba(0,217,255,0) 360deg)",
            borderRadius: "50%",
            maskImage:
              "radial-gradient(circle, black 0%, black 60%, transparent 72%)",
            WebkitMaskImage:
              "radial-gradient(circle, black 0%, black 60%, transparent 72%)",
          }}
        />
      </div>

      {/* type legend */}
      <div className="pointer-events-none absolute left-2.5 top-2.5 flex flex-col gap-1">
        {(Object.keys(typeCounts) as ContactType[]).map((t) => (
          <div key={t} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{
                backgroundColor: `rgb(${CONTACT_RGB[t].join(",")})`,
                boxShadow:
                  t === "position_jump"
                    ? `0 0 7px rgb(${CONTACT_RGB[t].join(",")})`
                    : "none",
              }}
            />
            <span className="num text-[9px] tracking-[0.1em] text-faint">
              {CONTACT_LABEL[t]}
              <span className="ml-1 text-muted">{typeCounts[t]}</span>
            </span>
          </div>
        ))}
      </div>

      {/* equirectangular note */}
      <div className="num pointer-events-none absolute bottom-2 right-3 text-[8px] tracking-[0.14em] text-faint/70">
        EQUIRECTANGULAR · CONUS AIS · OFFLINE
      </div>

      {/* hover tooltip */}
      {hovered && (
        <div
          className="glass pointer-events-none absolute z-30 max-w-[280px] rounded-lg p-2.5"
          style={{
            left: Math.min(hovered.x + 14, (ref.current?.clientWidth ?? 400) - 290),
            top: Math.max(hovered.y - 10, 6),
            borderColor: `rgb(${CONTACT_RGB[hovered.c.type].join(",")})`,
          }}
        >
          <div className="flex items-center justify-between gap-3">
            <span
              className="num text-[10px] font-semibold tracking-[0.12em]"
              style={{ color: `rgb(${CONTACT_RGB[hovered.c.type].join(",")})` }}
            >
              {CONTACT_LABEL[hovered.c.type]}
            </span>
            <span className="num text-[9px] text-muted">
              MMSI {hovered.c.mmsi} · {Math.round(hovered.c.confidence * 100)}%
            </span>
          </div>
          <p className="mt-1.5 text-[11px] leading-snug text-ink/90">
            {hovered.c.why}
          </p>
          <p
            className="mt-1.5 text-[10.5px] leading-snug"
            style={{ color: COLORS.cyan }}
          >
            ▸ {hovered.c.recommended_action}
          </p>
        </div>
      )}
    </div>
  );
}
