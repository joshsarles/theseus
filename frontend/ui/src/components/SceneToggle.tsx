import type { SceneMode } from "../lib/types";

interface SceneToggleProps {
  mode: SceneMode;
  onChange: (m: SceneMode) => void;
}

const TABS: { id: SceneMode; label: string; sub: string }[] = [
  { id: "operations", label: "OPERATIONS", sub: "one ship · live" },
  { id: "fleet", label: "FLEET LEARNING", sub: "the flywheel" },
];

/**
 * Instrument-grade segmented control to switch between the working one-ship CIC
 * (the digital twin + tactical picture) and the fleet-learning flywheel. Sharp,
 * hairline, command-amber active state — no pill, no glow.
 */
export function SceneToggle({ mode, onChange }: SceneToggleProps) {
  return (
    <div
      role="tablist"
      aria-label="scene"
      style={{ display: "flex", borderLeft: "1px solid var(--hair)", borderRight: "1px solid var(--hair)" }}
    >
      {TABS.map((t) => {
        const active = mode === t.id;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onChange(t.id)}
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              gap: 4,
              padding: "0 18px",
              minWidth: 132,
              height: "100%",
              background: active ? "var(--amber-wash)" : "transparent",
              border: "none",
              borderBottom: active ? "2px solid var(--amber)" : "2px solid transparent",
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            <span
              className="display"
              style={{
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.05em",
                color: active ? "var(--amber)" : "var(--ink-dim)",
                lineHeight: 1,
              }}
            >
              {t.label}
            </span>
            <span className="mono" style={{ fontSize: 8.5, color: "var(--muted)", letterSpacing: "0.1em" }}>
              {t.sub}
            </span>
          </button>
        );
      })}
    </div>
  );
}
