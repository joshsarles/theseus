# THESEUS · Ship-Brain Operations Console

A premium, futuristic operations dashboard for **THESEUS** — a self-controlled
warship "ship brain." Dark mission-control aesthetic in the spirit of Anduril
Lattice / Palantir / SpaceX mission control / Linear.

This is a standalone Vite + React 19 + TypeScript app. It does **not** touch the
existing `frontend/cic.html` or `demo/api.py`; it consumes the same live API.

---

## What it shows

| Region | Content |
| --- | --- |
| **Top command bar** | ⚓ THESEUS wordmark, posture tagline, pulsing `COMMS · DDIL / AIR-GAP` badge, `HULL` status, `RECORD ✓` chip, live `LINK` state, ticking UTC clock |
| **Hero center** | A procedural low-poly **warship in 3D** (react-three-fiber, built from primitives — hull, tumblehome superstructure, mast, funnel, VLS, gun; no external `.glb`), slowly rotating, with the **7 ship-system nodes** glowing on the hull, color-coded by severity |
| **Tactical picture** | A **deck.gl** contact plot on a dark-ocean canvas (no MapLibre basemap — offline-clean) at real lat/lon: own-ship reticle + ~50–100 contacts color-coded by anomaly type, spoof/jump in glowing red, radar sweep, hover tooltip showing *why* + *recommended action* |
| **Left rail** | The 7 ship systems as glass cards (live = cyan/severity accent + glow; standby = dim — honest, no fake greens) |
| **Machinery / HM&E** | A Recharts telemetry panel: RMSE-driven health gauge + gas-turbine decay-coefficient trend |
| **Right rail** | Flagged-contact feed sorted with `position_jump` first; each a glass card with `RECOMMEND →` and **ACCEPT / OVERRIDE** buttons (human-in-command — clicking records the watch-officer verdict in place) |
| **Tamper-evident record** | `CHAIN VERIFIED · PASS` (green) or `SNAP` (red), leaf count, Merkle root, chain head, logged-event tape |

### Doctrine rails honored in the UI copy

decision-support · human-in-command (THESEUS recommends, the watch officer
decides, nothing is auto-actioned) · SWAN-side / unclassified ·
tamper-**evident** (not tamper-proof).

---

## Stack

- **Vite 6 + React 19 + TypeScript** (strict)
- **Tailwind CSS 3** — glassmorphism, animated gradient-mesh background, neon-cyan accent system
- **Framer Motion** — spring/fade entrance on cards, button feedback, layout transitions
- **react-three-fiber + drei** — the hero 3D warship + glowing system nodes
- **deck.gl** (`ScatterplotLayer` / `LineLayer` / `TextLayer` on an `OrthographicView`) — the tactical contact picture
- **Recharts** — machinery telemetry
- **Geist Sans / Geist Mono** — vendored as woff2 (sans/mono) + ttf (3D labels); **no runtime CDN**, fully offline

---

## Data

Polls `http://localhost:8501/api/state` every **4 seconds** (CORS-enabled).
If the API is unreachable on first load, it falls back to a realistic mock that
matches the live contract so the console is never empty; the `LINK` chip shows
`LIVE` / `STALE` / `OFFLINE` accordingly.

Override the endpoint with an env var:

```bash
VITE_THESEUS_API="http://some-host:8501/api/state" npm run dev
```

Contract (abridged):

```ts
{
  ship, posture,
  systems: [{ key, label, live, severity, detail }],          // 7
  machinery: { model, version, rmse, framework, promotions },
  contacts: [{ id, mmsi, type, vessel_class, confidence,
               why, recommended_action, lat, lon, status }],   // ~50–100
  human_in_command: { pending, note },
  record: { verify_ok, first_bad_leaf, message, leaf_count, events }
}
```

---

## Develop / build / serve

From `frontend/ui/`:

```bash
npm install          # one-time

npm run dev          # dev server with HMR  -> http://localhost:5173
# or, production:
npm run build        # type-check + bundle into dist/
npm run preview      # serve the built dist/ -> http://localhost:5173
```

Make sure the THESEUS API is running on `:8501` first (the existing
`demo/api.py`), or the console will render with mock data.

Requires Node 20+ (built and verified on Node 25).

---

## Self-verification

The `scripts/` folder contains Playwright helpers used during development to
screenshot the running app, assert **zero console/page errors**, confirm the
3D + deck.gl canvases mount, and exercise the ACCEPT/OVERRIDE + tactical-hover
interactions:

```bash
node scripts/shoot.mjs      # screenshot + console-error report  -> /tmp/theseus-shot.png
node scripts/interact.mjs   # click ACCEPT/OVERRIDE, hover tooltip
```

---

## Notes

- The 3D warship is **procedural** — every surface is a three.js primitive
  (extruded hull profile, 4-sided cylinder frustums for the tumblehome
  superstructure, mast, funnel, VLS cells, gun). No model files are fetched.
- The ocean canvas deliberately has **no map basemap** to stay offline-clean;
  contacts are projected equirectangularly and fit to the viewport.
- Severity colors are honest: standby systems are dim, never shown as green.
