# THESEUS · Combat Information Center

An instrument-grade operations interface for **THESEUS** — the ship-brain
decision-support system. Built in the spirit of Palantir Gotham, Anduril
Lattice, *The Martian* mission control (Territory Studio), Linear, and Teenage
Engineering: the "wow" is craft, density, real data, and a point of view — not
effects.

Standalone Vite + React 19 + TypeScript. Consumes the live API at
`http://localhost:8501/api/state` (polls every 4s; falls back to a small
realistic mock if unreachable).

---

## Design system — "restraint = premium"

- **Color.** Warm off-black base `#0a0c10`. ONE owned accent — **command amber
  `#D4A000`** — used only for live / action / focus / own-ship. Status colors
  carry meaning only: green `#3fb950` nominal, amber caution, red `#e5484d`
  critical (spoof / position-jump). No cyan, neon, gradients, purple, or glow.
- **Type.** Display = **Space Grotesk** (tight negative tracking, authority).
  Data = **JetBrains Mono** with tabular figures for EVERY number — bearings,
  RMSE, leaf counts, coordinates, NM ranges, times, hashes. Both fonts are
  vendored to `src/fonts/*.woff2` (no runtime CDN).
- **Texture.** ~6% SVG fractal-noise film grain over the base (`.grain`).
- **Geometry.** 1px hairlines, sharp orthogonal containers. No glass blur, no
  drop shadows, no uniform rounded corners. No Tailwind — hand-authored CSS.
- **Motion.** GSAP, snap/instant, custom-eased — only on real events (a sealed
  leaf snapping into the spine, a leaf-count count-up). No looping decoration.

## Layout (asymmetric, content-driven)

```
┌ command header — ship · posture · live readouts · UTC · link ───────────────┐
├ 01 SHIP SYSTEMS  │ 03 TACTICAL PICTURE (deck.gl AIS plot) │ TAMPER-EVIDENT  │
│    (7 instruments)│    range rings · bearings · graticule │ RECORD          │
│ ─────────────────│ ─────────────────────────────────────│ CHAIN VERIFIED  │
│ 02 MACHINERY     │ 04 CONTACTS · HUMAN-IN-COMMAND         │ · PASS          │
│    RMSE + trend  │    RECOMMEND → ACCEPT / OVERRIDE       │ growing ledger  │
└──────────────────┴───────────────────────────────────────┴─────────────────┘
```

- **Tactical picture** (`deck.gl` WebGL2, OrthographicView): real AIS contacts
  plotted at their lat/lon in an equirectangular projection — clean vector
  symbology (hollow rings = routine, amber chevrons = flagged, **red diamonds +
  `SPOOF?` = position-jump**), own-ship reference with NM range rings and
  bearing ticks. Accuracy over prettiness.
- **The differentiator — the tamper-evident record spine** (right edge): the
  hash chain rendered as a precise growing ledger. Header `CHAIN VERIFIED ·
  PASS` (green) with leaf count + merkle root + head; each sealed leaf
  (`data_staged · model_trained · model_promoted · ais_anomaly ·
  human_decision`) shown with its short hash, in chain order.
- **Human-in-command climax:** each contact carries a RECOMMEND line plus
  `ACCEPT` / `OVERRIDE`. On click the app POSTs to `/api/decision`
  `{contact_id, verdict, by:"WATCH"}` and seals a `human_decision` leaf into the
  spine (GSAP snap-in + count-up). If the endpoint is not yet live the leaf
  seals locally and is flagged `LOCAL` — tamper-EVIDENT, never silently
  presented as server truth.

## Serve

```bash
cd frontend/ui
npm install          # (already installed; vendors fonts + deck.gl + gsap)
npm run build        # tsc -b && vite build — clean
npm run preview      # http://localhost:5173  (vite preview, host)
# or: npm run dev    # http://localhost:5173  (HMR)
```

Point at a different API with `VITE_THESEUS_API=http://host:port`.

## Self-verify (headless Playwright, isolated profile)

```bash
node scripts/shoot.mjs                       # → /tmp/theseus-shot.png + probe JSON
SHOOT_ACT="ACCEPT:0,OVERRIDE:0" node scripts/shoot.mjs   # exercise the climax
```

The script launches its own temp `--user-data-dir` (never touches any shared
profile), waits for deck.gl + GSAP to settle, screenshots, and reports console
errors, the body font, canvas size, and live leaf-row count.

Rails: decision-support · human-in-command · SWAN-side / unclassified ·
tamper-EVIDENT (not tamper-proof).
