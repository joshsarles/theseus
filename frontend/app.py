#!/usr/bin/env python3
"""THESEUS — Combat Information Center display (Streamlit).

A live-demo dashboard for THESEUS, the Navy shipboard "onboard ship-systems decision-support":
decision-support, human-in-command. Two perspectives via the sidebar switch:

  • Shipboard Edge (Raspberry Pi)  — the watchstander's CIC board on the node
  • Shore Side Command            — model registry + fleet of edge nodes

Built on Gerardo's skeleton (sidebar perspective switch + naval frame); this fills
both views out against the REAL tamper-evident record and REAL MarineCadastre AIS data.

RAILS (honored everywhere in the UI copy):
  decision-support, NOT autonomous control — Theseus recommends, the watch officer
  decides, nothing is actioned automatically · tamper-EVIDENT, not tamper-proof ·
  SWAN-side / unclassified (real public CC-BY data) · deployable (ATO is the gate),
  not fielded.

  streamlit run frontend/app.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

# ---------------------------------------------------------------------------
# Paths + the data contract (self-contained — no separate API server needed)
# ---------------------------------------------------------------------------
THESEUS_ROOT = Path("/Users/force/Developer/Theseus")
DEMO_DIR = THESEUS_ROOT / "demo"
RECORD_DIR = DEMO_DIR / "out" / "record"
REGISTRY_DIR = DEMO_DIR / "registry" / "theseus-cbm"
AIS_CSV = THESEUS_ROOT / "data" / "datasets" / "marinecadastre_us" / "AIS_2024_01_01.csv"
AIS_MAX_ROWS = 400_000  # cap for speed; all flagged contacts resolve within this slice

# the state builder is the frontend contract (see demo/api.py)
sys.path.insert(0, str(DEMO_DIR))
sys.path.insert(0, str(THESEUS_ROOT))

try:
    from api import build_state  # noqa: E402
except Exception as _e:  # pragma: no cover - surfaced in the UI
    build_state = None
    _BUILD_STATE_ERR = _e
else:
    _BUILD_STATE_ERR = None


# ---------------------------------------------------------------------------
# Page config + naval ops-center theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="THESEUS · CIC",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Threat-level palette — color-codes anomaly types across the whole board.
THREAT = {
    "position_jump": {"label": "POSITION JUMP / SPOOF", "hex": "#ff3b4e", "rgb": [255, 59, 78], "sev": "RED"},
    "spoof":         {"label": "SPOOF",                  "hex": "#ff3b4e", "rgb": [255, 59, 78], "sev": "RED"},
    "loiter":        {"label": "LOITER",                 "hex": "#ffae00", "rgb": [255, 174, 0], "sev": "AMBER"},
    "dark_gap":      {"label": "DARK GAP / AIS-OFF",     "hex": "#ff8c1a", "rgb": [255, 140, 26], "sev": "AMBER"},
    "overspeed":     {"label": "OVERSPEED",              "hex": "#ffe14d", "rgb": [255, 225, 77], "sev": "YELLOW"},
}
DEFAULT_THREAT = {"label": "ANOMALY", "hex": "#39c0ed", "rgb": [57, 192, 237], "sev": "CYAN"}


def threat(t: str) -> dict:
    return THREAT.get((t or "").lower(), DEFAULT_THREAT)


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Rajdhani:wght@500;600;700&display=swap');

:root {
  --navy-0:#040910; --navy-1:#0a121f; --navy-2:#101b2e; --navy-3:#16263f;
  --cyan:#39c0ed; --cyan-dim:#1b6f88; --amber:#ffae00; --green:#22e69a; --red:#ff3b4e;
  --ink:#cfe3f2; --ink-dim:#7d96ad;
}

.stApp {
  background:
    radial-gradient(1200px 600px at 80% -10%, rgba(57,192,237,0.10), transparent 60%),
    radial-gradient(900px 500px at 0% 110%, rgba(34,230,154,0.06), transparent 55%),
    linear-gradient(180deg, var(--navy-0) 0%, var(--navy-1) 100%);
  color: var(--ink);
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--navy-2), var(--navy-1));
  border-right: 1px solid rgba(57,192,237,0.25);
}
h1,h2,h3,h4 { font-family:'Rajdhani',sans-serif !important; letter-spacing:0.04em; color:var(--ink); }
.stApp, p, span, label, div { font-family:'Rajdhani', sans-serif; }
code, .mono, pre { font-family:'JetBrains Mono', monospace !important; }

/* top banner */
.cic-banner {
  border:1px solid rgba(57,192,237,0.35);
  border-radius:10px;
  padding:14px 20px;
  margin-bottom:6px;
  background: linear-gradient(135deg, rgba(16,27,46,0.95), rgba(10,18,31,0.95));
  box-shadow: inset 0 0 30px rgba(57,192,237,0.06), 0 2px 18px rgba(0,0,0,0.5);
  display:flex; align-items:center; justify-content:space-between; gap:18px;
}
.cic-title { font-family:'Rajdhani'; font-size:30px; font-weight:700; letter-spacing:0.18em; color:var(--cyan); margin:0; }
.cic-sub   { font-family:'JetBrains Mono'; font-size:12.5px; color:var(--ink-dim); letter-spacing:0.05em; }
.posture-pill {
  font-family:'JetBrains Mono'; font-size:12px; font-weight:600; letter-spacing:0.06em;
  padding:6px 14px; border-radius:20px; color:var(--green);
  border:1px solid rgba(34,230,154,0.45); background:rgba(34,230,154,0.08);
  white-space:nowrap;
}

/* section rule */
.sec {
  font-family:'Rajdhani'; font-weight:700; font-size:19px; letter-spacing:0.14em;
  color:var(--cyan); text-transform:uppercase;
  border-bottom:1px solid rgba(57,192,237,0.25); padding-bottom:6px; margin:8px 0 12px 0;
}

/* contact recommendation card */
.contact-card {
  border-left:4px solid var(--cyan);
  border-radius:8px; padding:12px 14px; margin-bottom:10px;
  background:linear-gradient(135deg, rgba(16,27,46,0.85), rgba(10,18,31,0.7));
  box-shadow: 0 1px 10px rgba(0,0,0,0.4);
}
.cc-head { font-family:'JetBrains Mono'; font-size:12.5px; font-weight:600; letter-spacing:0.04em; }
.cc-why  { color:var(--ink-dim); font-size:13.5px; margin:5px 0; }
.cc-rec  { font-family:'Rajdhani'; font-weight:600; font-size:14px; color:var(--ink); }
.chip {
  display:inline-block; font-family:'JetBrains Mono'; font-size:10.5px; font-weight:700;
  padding:2px 9px; border-radius:11px; letter-spacing:0.06em; margin-right:6px;
}
.status-tag { font-family:'JetBrains Mono'; font-size:11px; font-weight:700; letter-spacing:0.05em; }

/* status tiles */
.tile {
  border:1px solid rgba(57,192,237,0.22); border-radius:9px; padding:14px 16px;
  background:linear-gradient(135deg, rgba(16,27,46,0.85), rgba(10,18,31,0.7));
}
.tile-led { font-size:13px; font-weight:700; font-family:'JetBrains Mono'; letter-spacing:0.05em; }
.tile-sub { color:var(--ink-dim); font-size:12px; font-family:'JetBrains Mono'; margin-top:4px; }

.hashbox {
  font-family:'JetBrains Mono'; font-size:12px; color:var(--cyan);
  background:rgba(4,9,16,0.7); border:1px solid rgba(57,192,237,0.2);
  border-radius:6px; padding:9px 12px; word-break:break-all;
}
.rails {
  font-family:'JetBrains Mono'; font-size:11px; color:var(--ink-dim);
  border-top:1px dashed rgba(125,150,173,0.3); margin-top:18px; padding-top:10px; line-height:1.7;
}
div[data-testid="stMetric"] {
  background:linear-gradient(135deg, rgba(16,27,46,0.85), rgba(10,18,31,0.6));
  border:1px solid rgba(57,192,237,0.18); border-radius:9px; padding:12px 14px;
}
.stButton>button {
  font-family:'JetBrains Mono'; font-weight:600; letter-spacing:0.04em; border-radius:7px;
}
.blink { animation: blink 1.4s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.35} }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
def load_state() -> dict | None:
    """Build the watchstander board straight from the tamper-evident record."""
    if build_state is None:
        return None
    try:
        return build_state(RECORD_DIR)
    except Exception:
        return None


@st.cache_data(show_spinner="Resolving contact positions from AIS …", ttl=300)
def load_ais_positions(mmsis: tuple[str, ...], max_rows: int = AIS_MAX_ROWS) -> dict:
    """Last-known LAT/LON for each wanted MMSI by streaming the real AIS CSV.

    Streamed + filtered (stdlib csv) so we never hold 800 MB in memory; capped at
    `max_rows` for demo speed. Returns {mmsi: {"lat","lon","sog","cog","name","ts"}}.
    """
    import csv

    if not AIS_CSV.exists():
        return {}
    wanted = set(mmsis)
    if not wanted:
        return {}
    found: dict[str, dict] = {}
    with AIS_CSV.open(newline="") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # header
        except StopIteration:
            return {}
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            if len(row) < 6:
                continue
            mmsi = row[0]
            if mmsi not in wanted:
                continue
            try:
                lat, lon = float(row[2]), float(row[3])
            except (ValueError, IndexError):
                continue
            sog = row[4] if len(row) > 4 else ""
            cog = row[5] if len(row) > 5 else ""
            name = row[7].strip() if len(row) > 7 and row[7].strip() else "—"
            # keep the LAST seen fix (rows are time-ordered per the dataset)
            found[mmsi] = {"lat": lat, "lon": lon, "sog": sog, "cog": cog,
                           "name": name, "ts": row[1] if len(row) > 1 else ""}
    return found


@st.cache_data(ttl=120)
def load_registry() -> list[dict]:
    """Registered model versions from demo/registry/theseus-cbm/v*/meta.json."""
    import json

    out: list[dict] = []
    if not REGISTRY_DIR.exists():
        return out
    vdirs = sorted(
        (p for p in REGISTRY_DIR.glob("v*") if p.name[1:].isdigit()),
        key=lambda p: int(p.name[1:]),
    )
    for vd in vdirs:
        mp = vd / "meta.json"
        if not mp.exists():
            continue
        try:
            m = json.loads(mp.read_text())
        except Exception:
            continue
        out.append({
            "version": m.get("version", vd.name),
            "framework": m.get("framework", "?"),
            "rmse": m.get("rmse"),
            "target": m.get("target", "?"),
            "n_train": m.get("n_train"),
            "n_test": m.get("n_test"),
            "sha": (m.get("model_sha256") or "")[:16],
            "trained_unix": m.get("trained_unix"),
        })
    return out


def live_verify() -> tuple[bool, object, str]:
    """Re-run the offline verifier live (anyone can run this; no trust in us)."""
    try:
        from referee.chain import verify_dir
        if not (RECORD_DIR / "chain.jsonl").exists():
            return False, None, "no record on node"
        return verify_dir(RECORD_DIR)
    except Exception as e:
        return False, None, f"verify error: {e}"


# ---------------------------------------------------------------------------
# Session state (human-in-command decisions + DDIL cord)
# ---------------------------------------------------------------------------
def _init_state():
    st.session_state.setdefault("decisions", {})   # contact id -> accepted | overridden
    st.session_state.setdefault("cord_cut", False)  # DDIL shore link cut
    st.session_state.setdefault("last_refresh", datetime.now(timezone.utc))


_init_state()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


# ---------------------------------------------------------------------------
# SIDEBAR — perspective switch (Gerardo's frame)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚓ THESEUS")
    st.caption("onboard ship-systems decision-support · decision-support")
    st.divider()
    perspective = st.radio(
        "PERSPECTIVE",
        ["Shipboard Edge (Raspberry Pi)", "Shore Side Command"],
        index=0,
        help="Switch between the on-node watchstander board and the shore registry/fleet view.",
    )
    st.divider()

    # auto-refresh control
    auto = st.toggle("Auto-refresh (5s)", value=False,
                     help="Live CIC tick. Re-reads the record + state on an interval.")
    if st.button("↻ Refresh now", use_container_width=True):
        st.session_state["last_refresh"] = datetime.now(timezone.utc)
        st.cache_data.clear()
        st.rerun()

    st.caption(f"last tick · {_stamp()}")
    st.divider()
    st.markdown(
        "<div class='rails'>"
        "RAILS<br>"
        "• decision-support, NOT autonomous control<br>"
        "• Theseus recommends · the watch decides<br>"
        "• tamper-EVIDENT, not tamper-proof<br>"
        "• SWAN-side / unclassified (real CC-BY data)<br>"
        "• deployable — ATO is the gate, not fielded"
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Shared header banner
# ---------------------------------------------------------------------------
def render_banner(state: dict | None, node_label: str):
    ship = (state or {}).get("ship", "THESEUS")
    posture = (state or {}).get("posture", "decision-support · human-in-command · SWAN-side")
    st.markdown(
        f"""
        <div class="cic-banner">
          <div>
            <div class="cic-title">⚓ {ship} &nbsp;·&nbsp; COMBAT INFORMATION CENTER</div>
            <div class="cic-sub">{node_label} &nbsp;•&nbsp; {_stamp()}</div>
          </div>
          <div class="posture-pill">{posture}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def no_record_warning():
    st.error(
        "**No sealed record on this node yet.** Populate the demo first:\n\n"
        "```bash\nbash demo/run_full.sh && python3 demo/ais_pol.py --rows 400000\n```",
        icon="⚓",
    )
    if _BUILD_STATE_ERR is not None:
        st.caption(f"state-builder import note: {_BUILD_STATE_ERR}")


# ===========================================================================
# VIEW 1 — SHIPBOARD EDGE (Raspberry Pi)
# ===========================================================================
def view_shipboard_edge():
    state = load_state()
    render_banner(state, "SHIPBOARD EDGE NODE · Raspberry Pi · SWAN-side")

    if not state or state.get("record", {}).get("leaf_count", 0) == 0:
        no_record_warning()
        return

    machinery = state.get("machinery") or {}
    contacts = state.get("contacts") or []
    record = state.get("record") or {}
    hic = state.get("human_in_command") or {}

    # Assign a stable, unique key per card. Contact ids can collide (e.g. the same
    # MMSI flagged in two ais_pol passes), so suffix the index to keep widget keys
    # unique while one decision still maps per distinct contact id.
    for i, c in enumerate(contacts):
        c["uid"] = f"{c.get('id', 'contact')}#{i}"

    # ----- top-line metrics -------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    pending_now = sum(1 for c in contacts
                      if st.session_state["decisions"].get(c["uid"], "pending") == "pending")
    decided = len(contacts) - pending_now
    link_state = "CUT" if st.session_state["cord_cut"] else "CONNECTED"
    c1.metric("CONTACTS FLAGGED", len(contacts), help="Real AIS Pattern-of-Life detections, cold-start.")
    c2.metric("WATCH DECISIONS", f"{decided}/{len(contacts)}",
              delta=f"{pending_now} pending", delta_color="inverse")
    c3.metric("CBM MODEL", f"v{machinery.get('version', '?')}",
              delta=f"RMSE {machinery.get('rmse', '?')}")
    c4.metric("SHORE LINK", link_state,
              delta="serving last-good" if st.session_state["cord_cut"] else "online",
              delta_color="off" if st.session_state["cord_cut"] else "normal")

    st.markdown("")

    # ----- MACHINERY / HM&E -------------------------------------------------
    st.markdown("<div class='sec'>⚙ Machinery / HM&E — Condition-Based Maintenance</div>",
                unsafe_allow_html=True)
    m1, m2, m3 = st.columns([1.2, 1, 1.4])
    with m1:
        st.metric("MODEL VERSION", f"theseus-cbm v{machinery.get('version','?')}",
                  delta=f"{machinery.get('promotions', 0)} promotion(s) on record")
        st.metric("RMSE (held-out)", f"{machinery.get('rmse','?')}",
                  help="Gas-turbine compressor-decay regressor on real UCI #316.")
    with m2:
        st.metric("FRAMEWORK", machinery.get("framework", "?"))
        st.metric("TARGET", "GT compressor decay", help="UCI Condition-Based Maintenance of Naval Propulsion #316")
    with m3:
        status = (machinery.get("status") or "nominal").upper()
        led = "var(--green)" if status == "NOMINAL" else "var(--amber)"
        st.markdown(
            f"""
            <div class="tile" style="border-color:rgba(34,230,154,0.4)">
              <div class="tile-led" style="color:{led}">● HM&E STATUS — {status}</div>
              <div class="tile-sub">Compressor-decay model serving on-node.<br>
              No fault indicated · advisory CBM only.</div>
              <div style="margin-top:10px;height:8px;border-radius:5px;
                   background:linear-gradient(90deg,var(--green) 0%,var(--green) 88%,rgba(34,230,154,0.15) 88%);"></div>
              <div class="tile-sub" style="margin-top:5px">confidence envelope · nominal band</div>
            </div>
            """, unsafe_allow_html=True,
        )

    st.markdown("")

    # ----- CONTACTS / Pattern-of-Life --------------------------------------
    st.markdown("<div class='sec'>🛰 Contacts / Pattern-of-Life — Real AIS</div>",
                unsafe_allow_html=True)

    mmsis = tuple(str(c["mmsi"]) for c in contacts if c.get("mmsi"))
    positions = load_ais_positions(mmsis)

    map_rows = []
    for c in contacts:
        mmsi = str(c.get("mmsi"))
        pos = positions.get(mmsi)
        if not pos:
            continue  # MMSI not found in the AIS slice → skip gracefully
        th = threat(c["type"])
        decision = st.session_state["decisions"].get(c["uid"], "pending")
        map_rows.append({
            "mmsi": mmsi,
            "lat": pos["lat"], "lon": pos["lon"],
            "name": pos.get("name", "—"),
            "type": c["type"], "type_label": th["label"], "sev": th["sev"],
            "vessel_class": c.get("vessel_class", "?"),
            "confidence": c.get("confidence", 0),
            "why": c.get("why", ""),
            "recommended_action": c.get("recommended_action", ""),
            "decision": decision.upper(),
            "color": th["rgb"] + [200],
            "radius": 1600 + 5200 * float(c.get("confidence", 0) or 0),
        })

    mapcol, listcol = st.columns([1.55, 1])

    with mapcol:
        if map_rows:
            df = pd.DataFrame(map_rows)
            view = pdk.ViewState(
                latitude=float(df["lat"].mean()),
                longitude=float(df["lon"].mean()),
                zoom=3.4, pitch=35, bearing=0,
            )
            scatter = pdk.Layer(
                "ScatterplotLayer", data=df,
                get_position=["lon", "lat"],
                get_fill_color="color",
                get_radius="radius",
                radius_min_pixels=5, radius_max_pixels=40,
                pickable=True, opacity=0.85, stroked=True,
                get_line_color=[255, 255, 255, 120], line_width_min_pixels=1,
            )
            halo = pdk.Layer(
                "ScatterplotLayer", data=df,
                get_position=["lon", "lat"],
                get_fill_color="[color[0], color[1], color[2], 30]",
                get_radius="radius * 2.4",
                radius_min_pixels=10, radius_max_pixels=80, opacity=0.25,
            )
            text = pdk.Layer(
                "TextLayer", data=df,
                get_position=["lon", "lat"],
                get_text="mmsi", get_size=11, get_color=[207, 227, 242, 220],
                get_alignment_baseline="'bottom'", get_pixel_offset=[0, -14],
            )
            tooltip = {
                "html": "<b>⚓ MMSI {mmsi}</b> &nbsp;<i>{name}</i><br/>"
                        "<b style='color:#39c0ed'>{type_label}</b> · {sev} · {vessel_class}<br/>"
                        "conf {confidence}<br/>"
                        "<span style='color:#ffae00'>WHY:</span> {why}<br/>"
                        "<span style='color:#22e69a'>RECOMMEND:</span> {recommended_action}<br/>"
                        "watch: <b>{decision}</b>",
                "style": {"backgroundColor": "rgba(10,18,31,0.95)", "color": "#cfe3f2",
                          "fontSize": "12px", "border": "1px solid #39c0ed",
                          "borderRadius": "6px", "maxWidth": "330px"},
            }
            st.pydeck_chart(
                pdk.Deck(
                    layers=[halo, scatter, text], initial_view_state=view, tooltip=tooltip,
                    map_style="dark", map_provider="carto",
                ),
                use_container_width=True, height=440,
            )
            # legend
            leg = " &nbsp; ".join(
                f"<span class='chip' style='background:{v['hex']}22;color:{v['hex']};"
                f"border:1px solid {v['hex']}'>{v['label']}</span>"
                for v in [THREAT["position_jump"], THREAT["loiter"],
                          THREAT["dark_gap"], THREAT["overspeed"]]
            )
            st.markdown(f"<div style='margin-top:6px'>{leg}</div>", unsafe_allow_html=True)
            st.caption(f"{len(map_rows)} flagged contacts plotted · positions from real "
                       f"MarineCadastre AIS (2024-01-01) · hover for the WHY + recommendation.")
        else:
            st.info("No flagged contacts resolved to AIS positions in the loaded slice.")

    with listcol:
        st.markdown(
            f"<div class='tile' style='border-color:rgba(255,174,0,0.4)'>"
            f"<div class='tile-led' style='color:var(--amber)'>👤 HUMAN-IN-COMMAND</div>"
            f"<div class='tile-sub'>{pending_now} of {len(contacts)} pending watch ACCEPT / OVERRIDE.<br>"
            f"{hic.get('note','Theseus recommends; the watch officer decides.')}</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown("")
        # severity-ordered recommendation cards
        sev_rank = {"RED": 0, "AMBER": 1, "YELLOW": 2, "CYAN": 3}
        ordered = sorted(contacts, key=lambda c: (sev_rank.get(threat(c["type"])["sev"], 9),
                                                   -float(c.get("confidence", 0) or 0)))
        st.markdown("**RECOMMENDATION CARDS** — watch officer decides")
        cardbox = st.container(height=430)
        with cardbox:
            for c in ordered:
                _render_contact_card(c)

    st.markdown("")

    # ----- DDIL status ------------------------------------------------------
    st.markdown("<div class='sec'>📡 DDIL — Disconnected / Degraded / Intermittent / Low-bandwidth</div>",
                unsafe_allow_html=True)
    d1, d2 = st.columns([1, 1.4])
    with d1:
        cut = st.toggle("⛓️‍💥 Pull the cord (cut shore link)", value=st.session_state["cord_cut"],
                        help="Simulate a severed shore link. The node must keep serving.")
        if cut != st.session_state["cord_cut"]:
            st.session_state["cord_cut"] = cut
            st.rerun()
    with d2:
        if st.session_state["cord_cut"]:
            st.markdown(
                f"""
                <div class="tile" style="border-color:rgba(255,59,78,0.5)">
                  <div class="tile-led blink" style="color:var(--red)">● SHORE LINK — CUT</div>
                  <div class="tile-sub">
                    Node operating <b>DISCONNECTED</b>.<br>
                    • still serving last-good model · <b>theseus-cbm v{machinery.get('version','?')}</b><br>
                    • record intact on-node · <b>{record.get('leaf_count', 0)} leaves</b>, verify holds<br>
                    • no shore round-trip required — promote/rollback run locally
                  </div>
                </div>
                """, unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="tile" style="border-color:rgba(34,230,154,0.4)">
                  <div class="tile-led" style="color:var(--green)">● SHORE LINK — CONNECTED</div>
                  <div class="tile-sub">
                    Tailscale tunnel up · model-delivery sync available.<br>
                    Node is autonomous-capable: cut the cord to prove disconnected operation.
                  </div>
                </div>
                """, unsafe_allow_html=True,
            )

    st.markdown("")

    # ----- RECORD INTEGRITY -------------------------------------------------
    st.markdown("<div class='sec'>🔒 Record Integrity — Tamper-Evident Ledger (the moat)</div>",
                unsafe_allow_html=True)
    r1, r2 = st.columns([1, 1.5])
    with r1:
        if st.button("🔁 Verify record (live)", use_container_width=True, type="primary"):
            ok, bad, msg = live_verify()
            st.session_state["_live_verify"] = (ok, bad, msg, _stamp())
        lv = st.session_state.get("_live_verify")
        ok = record.get("verify_ok", False)
        msg = record.get("message", "")
        if lv:
            ok, bad, msg, when = lv
            st.caption(f"live re-verify · {when}")
        if ok:
            st.success("✅ VERIFY PASS — chain + Merkle root hold", icon="✅")
        else:
            st.error(f"🟥 SNAP — {msg}", icon="🟥")
        st.metric("LEDGER LEAVES", record.get("leaf_count", 0))
    with r2:
        st.markdown(f"<div class='hashbox'>{msg}</div>", unsafe_allow_html=True)
        events = record.get("events", {}) or {}
        if events:
            ev_df = pd.DataFrame(
                [{"event kind": k, "sealed": v} for k, v in sorted(events.items())]
            )
            st.dataframe(ev_df, use_container_width=True, hide_index=True, height=180)
        st.caption("SHA-256 prev-hash chain + Merkle root · offline-verifiable by anyone, "
                   "no trust in us required · tamper-EVIDENT, not tamper-proof.")

    _rails_footer()


def _render_contact_card(c: dict):
    th = threat(c["type"])
    cid = c.get("uid", c.get("id", "contact"))
    decision = st.session_state["decisions"].get(cid, "pending")
    dtag = {
        "accepted": "<span class='status-tag' style='color:var(--green)'>✔ ACCEPTED</span>",
        "overridden": "<span class='status-tag' style='color:var(--amber)'>✖ OVERRIDDEN</span>",
        "pending": "<span class='status-tag' style='color:var(--ink-dim)'>… PENDING</span>",
    }[decision]
    st.markdown(
        f"""
        <div class="contact-card" style="border-left-color:{th['hex']}">
          <div class="cc-head">
            <span class="chip" style="background:{th['hex']}22;color:{th['hex']};border:1px solid {th['hex']}">
              {th['sev']} · {th['label']}</span>
            <span style="color:var(--cyan)">MMSI {c.get('mmsi')}</span>
            <span style="color:var(--ink-dim)"> · {c.get('vessel_class','?')} · conf {c.get('confidence')}</span>
            &nbsp;{dtag}
          </div>
          <div class="cc-why">WHY · {c.get('why','')}</div>
          <div class="cc-rec">RECOMMEND → {c.get('recommended_action','')}</div>
        </div>
        """, unsafe_allow_html=True,
    )
    b1, b2, _ = st.columns([1, 1, 2.4])
    if b1.button("ACCEPT", key=f"acc_{cid}", use_container_width=True):
        st.session_state["decisions"][cid] = "accepted"
        st.rerun()
    if b2.button("OVERRIDE", key=f"ovr_{cid}", use_container_width=True):
        st.session_state["decisions"][cid] = "overridden"
        st.rerun()


# ===========================================================================
# VIEW 2 — SHORE SIDE COMMAND
# ===========================================================================
def view_shore_side():
    state = load_state()
    render_banner(state, "SHORE SIDE COMMAND · model registry · fleet C2")

    registry = load_registry()

    # ----- top-line ---------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    latest = registry[-1] if registry else {}
    c1.metric("REGISTERED MODELS", len(registry))
    c2.metric("CURRENT VERSION", f"v{latest.get('version','?')}",
              delta=f"RMSE {latest.get('rmse','?')}" if latest else None)
    c3.metric("EDGE NODES", "2 / 2 online", delta="Pi-1 · Pi-2")
    c4.metric("DELIVERY", "UDS / Zarf", delta="airgap-capable", delta_color="off")

    st.markdown("")

    # ----- Model registry ---------------------------------------------------
    st.markdown("<div class='sec'>📦 Model Registry — theseus-cbm</div>", unsafe_allow_html=True)
    if registry:
        reg_df = pd.DataFrame([
            {
                "version": f"v{r['version']}",
                "framework": r["framework"],
                "RMSE": r["rmse"],
                "target": r["target"],
                "n_train": r.get("n_train"),
                "n_test": r.get("n_test"),
                "model_sha256": r["sha"] + "…",
                "status": "★ CURRENT" if r is registry[-1] else "archived",
            } for r in registry
        ])
        st.dataframe(reg_df, use_container_width=True, hide_index=True)
        st.caption("Read from demo/registry/theseus-cbm/v*/meta.json · every train/promote is "
                   "also sealed in the tamper-evident record.")
    else:
        st.warning("No registered models found. Run `bash demo/run_full.sh` to populate the registry.")

    st.markdown("")

    # ----- Stage to edge (UDS) ----------------------------------------------
    st.markdown("<div class='sec'>🚀 Stage Model → Edge (UDS / Zarf, airgap)</div>",
                unsafe_allow_html=True)
    s1, s2 = st.columns([1, 1.7])
    with s1:
        target_v = f"v{latest.get('version','?')}" if latest else "v?"
        st.write(f"Selected: **theseus-cbm {target_v}** → edge bundle")
        staged = st.button("📦 Stage model → edge bundle", use_container_width=True, type="primary")
        st.caption("Builds the airgap package the Pi cluster pulls. (Demo presents the flow; "
                   "does not run zarf here.)")
    with s2:
        if staged:
            st.markdown(
                f"""
                <div class="hashbox">
# from repo root — build the airgap package (SBOM auto-generated)
$ zarf package create deploy/uds/ -o deploy/uds/dist --confirm
# wrap as a UDS bundle (STRICT mTLS, default-deny egress, Keycloak human-in-command authn)
$ uds create deploy/uds/ -o deploy/uds/dist --confirm
# deploy to the edge Pi k3d cluster (airgapped — no shore round-trip)
$ uds deploy deploy/uds/dist/uds-bundle-theseus-{target_v}-*.tar.zst --confirm
<span style="color:var(--green)">  ✔ package: theseus {target_v} · base image digest-pinned · SBOM attached
  ✔ in-cluster Job swaps model → prints sealed record → offline verify PASS</span>
                </div>
                """, unsafe_allow_html=True,
            )
            st.success(f"Edge bundle staged for theseus-cbm {target_v}. "
                       "Pull/promote/verify run on-node, disconnected.", icon="📦")
        else:
            st.info("Press **Stage model → edge bundle** to render the airgap delivery flow.")

    st.markdown("")

    # ----- Fleet ------------------------------------------------------------
    st.markdown("<div class='sec'>🛰 Fleet — Edge Nodes (Raspberry Pi)</div>", unsafe_allow_html=True)
    machinery = (state or {}).get("machinery") or {}
    contacts = (state or {}).get("contacts") or []
    nodes = [
        {"id": "Pi-1", "role": "MACHINERY / HM&E", "cell": "CBM gas-turbine",
         "detail": f"theseus-cbm v{machinery.get('version','?')} · RMSE {machinery.get('rmse','?')}",
         "online": True},
        {"id": "Pi-2", "role": "CONTACTS / Pattern-of-Life", "cell": "AIS POL cell",
         "detail": f"{len(contacts)} contacts flagged · cold-start",
         "online": True},
    ]
    fcols = st.columns(2)
    for col, n in zip(fcols, nodes):
        led = "var(--green)" if n["online"] else "var(--red)"
        state_txt = "ONLINE" if n["online"] else "OFFLINE"
        with col:
            st.markdown(
                f"""
                <div class="tile" style="border-color:rgba(34,230,154,0.4)">
                  <div class="tile-led" style="color:{led}">● {n['id']} — {state_txt}</div>
                  <div style="font-family:'Rajdhani';font-weight:700;font-size:16px;
                       color:var(--cyan);margin-top:4px">{n['role']}</div>
                  <div class="tile-sub">{n['cell']}<br>{n['detail']}<br>
                  <span style="color:var(--ink-dim)">edge · SWAN-side · Raspberry Pi</span></div>
                </div>
                """, unsafe_allow_html=True,
            )
    st.caption("Status tiles shown static for the demo; in deployment these are live-polled over "
               "Tailscale from each Pi node's local state API.")

    _rails_footer()


# ---------------------------------------------------------------------------
def _rails_footer():
    st.markdown(
        "<div class='rails'>"
        "⚓ THESEUS — decision-support, NOT autonomous ship control. "
        "Theseus recommends; the watch officer decides; nothing is actioned automatically. "
        "Tamper-EVIDENT, not tamper-proof · SWAN-side / unclassified (real public CC-BY data) · "
        "deployable — ATO is the gate, not fielded. Built on Gerardo's skeleton."
        "</div>", unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Auto-refresh fragment wrapper + dispatch
# ---------------------------------------------------------------------------
def render(perspective: str):
    if perspective.startswith("Shipboard"):
        view_shipboard_edge()
    else:
        view_shore_side()


if auto:
    # st.fragment(run_every=...) gives a true CIC tick without a 3rd-party dep.
    @st.fragment(run_every=5)
    def _tick():
        st.session_state["last_refresh"] = datetime.now(timezone.utc)
        render(perspective)
    _tick()
else:
    render(perspective)
