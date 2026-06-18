import type { ConnState } from "../hooks/useShipState";

/**
 * Risk #1 — the demo must NEVER let mock/stale data masquerade as a live link.
 *
 * Whenever the connection is anything other than a truly-live 200 from the
 * THESEUS API, we paint a GIANT, unmissable red banner across the top of the
 * viewport. The header's "LINK LIVE" amber readout is shown ONLY for conn ===
 * "live" (see CommandHeader); this banner is the loud, second, redundant signal
 * so a watch officer (or a judge) cannot mistake a SIM FEED for the real thing.
 */

interface SimFeedBannerProps {
  conn: ConnState;
}

const COPY: Record<Exclude<ConnState, "live">, { headline: string; sub: string }> = {
  mock: {
    headline: "SIM FEED — NOT LIVE",
    sub: "API unreachable · displaying offline mock fixture · no decision is being sealed",
  },
  stale: {
    headline: "SIM FEED — LINK STALE",
    sub: "last good frame is being held · API stopped responding · decisions are NOT reaching the record",
  },
  connecting: {
    headline: "SIM FEED — LINKING …",
    sub: "no live frame confirmed yet · awaiting first 200 from the THESEUS API",
  },
};

export function SimFeedBanner({ conn }: SimFeedBannerProps) {
  // Truly live: render nothing. Only a real 200 from /api/state clears the bar.
  if (conn === "live") return null;

  const { headline, sub } = COPY[conn];

  return (
    <div
      data-sim-banner
      data-conn={conn}
      role="alert"
      aria-live="assertive"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 10000, // above the film grain (9999) — nothing occludes this
        background: "var(--critical)",
        color: "#0a0c10",
        borderBottom: "3px solid #ffffff",
        padding: "12px 22px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 18,
        textAlign: "center",
        animation: "sim-feed-blink 1.1s steps(1, end) infinite",
        boxShadow: "0 2px 0 rgba(0,0,0,0.5)",
      }}
    >
      <span aria-hidden style={{ fontSize: 26, lineHeight: 1 }}>
        ⚠
      </span>
      <div style={{ display: "flex", flexDirection: "column", gap: 3, minWidth: 0 }}>
        <span
          className="display"
          style={{
            fontSize: 26,
            fontWeight: 700,
            letterSpacing: "0.04em",
            lineHeight: 1,
            textTransform: "uppercase",
          }}
        >
          {headline}
        </span>
        <span
          className="mono"
          style={{
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.04em",
            lineHeight: 1.3,
            opacity: 0.9,
          }}
        >
          {sub}
        </span>
      </div>
      <span aria-hidden style={{ fontSize: 26, lineHeight: 1 }}>
        ⚠
      </span>
    </div>
  );
}
