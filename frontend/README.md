# THESEUS — Combat Information Center (Streamlit)

A live-demo dashboard for **THESEUS**, the Navy shipboard "self-controlled ship
brain": **decision-support, human-in-command**. It renders the watchstander board
straight from the tamper-evident record and plots flagged contacts on real AIS data.

> Built on **Gerardo's skeleton** (the sidebar perspective switch + naval frame) —
> this fills both perspectives out fully against the real record + real AIS.

## Run it

```bash
# from the repo root (/Users/force/Developer/Theseus)
streamlit run frontend/app.py
```

Then open the Local URL Streamlit prints (default <http://localhost:8501>).

The app is **self-contained** — it does **not** require the `demo/api.py` server to
be running. It imports the state builder directly (`from api import build_state`) and
reads the sealed record + the AIS CSV off disk.

### Populate the record first (if empty)

If the dashboard shows *"No sealed record on this node yet,"* generate the demo data
once:

```bash
bash demo/run_full.sh && python3 demo/ais_pol.py --rows 400000
```

`run_full.sh` runs the full story in order — stage → retrain → promote (machinery
CBM) and the AIS Pattern-of-Life cell — and seals every step into the
tamper-evident record. Each step is offline-verifiable.

## The two perspectives (sidebar switch)

### ⚓ Shipboard Edge (Raspberry Pi)
The watchstander's CIC board, as it runs on the edge node:

1. **Header** — ship + posture banner (decision-support · human-in-command · SWAN-side).
2. **Machinery / HM&E** — the CBM model card (version, RMSE, framework, nominal status gauge).
3. **Contacts / Pattern-of-Life** — a **pydeck map** of every flagged contact, plotted
   at its last-known position from the **real MarineCadastre AIS** feed
   (`data/datasets/marinecadastre_us/AIS_2024_01_01.csv`), color-coded by anomaly type,
   with hover tooltips showing the *why* + recommended action. Alongside it, the contacts
   appear as **RECOMMEND → [ACCEPT] [OVERRIDE]** cards — the human-in-command beat
   (decisions persist in session state; nothing is actioned automatically).
4. **DDIL status** — a SHORE LINK indicator + a **"Pull the cord"** toggle that proves
   disconnected operation (still serving last-good model · record intact on-node).
5. **Record integrity** — the moat: verify PASS/SNAP, leaf count, the Merkle/chain head,
   the sealed-events breakdown, and a **"Verify record (live)"** button that re-runs the
   offline verifier (`referee.chain.verify_dir`) on demand.

### Shore Side Command
1. **Model registry** — the registered `theseus-cbm` versions read from
   `demo/registry/theseus-cbm/v*/meta.json` (version, RMSE, framework, target).
2. **Stage to edge (UDS)** — a **"Stage model → edge bundle"** button that presents the
   airgap **Zarf / UDS** delivery flow (`zarf package create deploy/uds/ …`). The demo
   shows the flow; it does not run zarf.
3. **Fleet** — the two Raspberry Pi edge nodes (Pi-1 MACHINERY, Pi-2 CONTACTS) as status
   tiles (shown static for the demo; live-polled over Tailscale in deployment).

## Data sources (real, not synthetic)

| What | Source |
| --- | --- |
| Watchstander board / record | `demo/api.py:build_state(demo/out/record)` — the tamper-evident SHA-256 chain + Merkle root |
| Contact positions (map) | `data/datasets/marinecadastre_us/AIS_2024_01_01.csv` — real public-domain MarineCadastre US AIS (streamed/filtered, capped at ~400k rows, `@st.cache_data`) |
| Model registry | `demo/registry/theseus-cbm/v*/meta.json` |
| Live record verify | `referee.chain.verify_dir` |

The map shows **real AIS**; the anomalies are **real detections** from the cold-start
Pattern-of-Life cell. A flagged MMSI not present in the loaded AIS slice is skipped
gracefully.

## Polish / theme

- Naval ops-center dark theme — cyan/amber accents, monospace for the record hashes,
  a CIC banner, posture pill, severity-ordered recommendation cards.
- **Threat colors:** red = position_jump / spoof · amber = loiter / dark_gap ·
  yellow = overspeed.
- `st.metric` deltas, an **auto-refresh toggle** (a true CIC tick via `st.fragment`,
  no third-party dependency) plus a manual **"Refresh now"** button.

## Rails (honored throughout the UI)

- **Decision-support, NOT autonomous control** — Theseus *recommends*, the watch officer
  *decides*, nothing is actioned automatically.
- **Tamper-EVIDENT**, not tamper-proof.
- **SWAN-side / unclassified** — real public CC-BY data.
- **Deployable — ATO is the gate**, not fielded.

## Notes

- Built/verified on Streamlit 1.58, pydeck 0.9, pandas 2.3, Python 3.14.
- `streamlit_autorefresh` is not required — auto-refresh uses `st.fragment(run_every=…)`.
- Paths are pinned to this checkout (`/Users/force/Developer/Theseus`).
