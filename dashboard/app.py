"""Tare Flight Recorder - Streamlit + Plotly (brand kit v1.1)."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "brand" / "tare"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from recorder.db import FlightRecorder  # noqa: E402

FAVICON = BRAND / "logos" / "favicon-32.png"
LOCKUP = BRAND / "logos" / "tare-lockup-dark.png"
TOKENS_CSS = BRAND / "tokens" / "tokens.css"

st.set_page_config(
    page_title="tare - Flight Recorder",
    layout="wide",
    page_icon=str(FAVICON) if FAVICON.exists() else "⚖️",
)


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


_tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
_lockup_img = (
    f'<img src="data:image/png;base64,{_b64(LOCKUP)}" alt="tare" '
    f'style="height:36px;width:auto;display:block;" />'
    if LOCKUP.exists()
    else '<span class="tare-wordmark">tare</span>'
)

st.markdown(
    f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Poppins:wght@700&display=swap" rel="stylesheet">
    <style>
    {_tokens}
    .stApp {{
      background-color: var(--bg-canvas, #0A0A0A);
      color: var(--text-primary, #F0F0F0);
      font-family: var(--font-ui, "IBM Plex Sans", Inter, sans-serif);
    }}
    h1, h2, h3 {{
      color: var(--accent-neutral, #FFFFFF) !important;
      letter-spacing: var(--tracking-display, -0.03em);
      font-family: var(--font-ui, "IBM Plex Sans", sans-serif) !important;
      font-weight: 600 !important;
    }}
    .tare-wordmark {{
      font-family: var(--font-display, Poppins, sans-serif);
      font-weight: 700;
      letter-spacing: -0.03em;
      font-size: 1.75rem;
      color: #fff;
    }}
    .tare-header {{
      display: flex; align-items: center; gap: 1rem;
      margin-bottom: 0.35rem;
    }}
    .tare-tagline {{
      color: var(--text-muted, #A3A3A3);
      font-size: 0.95rem;
      margin: 0 0 1.25rem 0;
    }}
    div[data-testid="stMetricValue"] {{
      color: var(--accent-neutral, #FFFFFF);
      font-variant-numeric: tabular-nums;
      font-family: var(--font-mono, "IBM Plex Mono", monospace);
    }}
    div[data-testid="stMetricLabel"] {{
      color: var(--text-muted, #A3A3A3);
    }}
    [data-testid="stSidebar"] {{
      background: var(--bg-panel, #111111);
      border-right: 1px solid var(--border-subtle, #222);
    }}
    .veto-flash {{
      background: var(--accent-danger-deep, #7F1D1D);
      color: var(--text-primary, #F0F0F0);
      padding: 0.75rem 1rem;
      border: 1px solid var(--accent-danger, #EF4444);
      border-radius: var(--radius, 4px);
      margin-bottom: 1rem;
      font-family: var(--font-mono, "IBM Plex Mono", monospace);
      font-size: 0.9rem;
      animation: tare-pulse 1.2s ease-in-out infinite;
    }}
    @keyframes tare-pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.75}} }}
    .tare-status-pill {{
      display: inline-block;
      padding: 0.15rem 0.55rem;
      border: 1px solid var(--border-strong, #333);
      border-radius: var(--radius, 4px);
      font-family: var(--font-mono, monospace);
      font-size: 0.75rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .tare-status-pill.running {{ color: var(--accent-guarded, #22C55E); border-color: var(--accent-guarded, #22C55E); }}
    .tare-status-pill.halted, .tare-status-pill.kill-switch, .tare-status-pill.stopped {{
      color: var(--accent-danger, #EF4444); border-color: var(--accent-danger, #EF4444);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

from dotenv import load_dotenv  # noqa: E402

from core.config import db_path  # noqa: E402

load_dotenv(ROOT / ".env")
DB_PATH = db_path()  # same database the live loop writes (TARE_DB or settings.yaml)
RESULTS_PATH = ROOT / "docs" / "attack_metrics.json"


@st.cache_resource
def get_recorder(path: str) -> FlightRecorder:
    return FlightRecorder(path)


def overconfidence_gauge(stated: float, calibrated: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Indicator(
            mode="gauge+number+delta",
            value=stated,
            delta={"reference": calibrated, "increasing": {"color": "#ef4444"}},
            title={"text": "Stated confidence vs calibrated p"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#ffffff"},
                "steps": [
                    {"range": [0, calibrated], "color": "#1a1a1a"},
                    {"range": [calibrated, 100], "color": "#331111"},
                ],
                "threshold": {
                    "line": {"color": "#22c55e", "width": 3},
                    "thickness": 0.8,
                    "value": calibrated,
                },
            },
            number={"suffix": "%"},
        )
    )
    fig.update_layout(
        paper_bgcolor="#0a0a0a",
        font={"color": "#f0f0f0"},
        height=280,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def equity_figure(guarded: pd.DataFrame, shadow: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not guarded.empty:
        fig.add_trace(
            go.Scatter(
                x=pd.to_datetime(guarded["ts"]),
                y=guarded["equity"],
                name="Guarded",
                line=dict(color="#22c55e", width=2),
            )
        )
    if not shadow.empty:
        fig.add_trace(
            go.Scatter(
                x=pd.to_datetime(shadow["ts"]),
                y=shadow["equity"],
                name="Shadow (unguarded)",
                line=dict(color="#ef4444", width=2),
            )
        )
    fig.update_layout(
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#111111",
        font_color="#f0f0f0",
        legend=dict(orientation="h"),
        height=360,
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(gridcolor="#222"),
        yaxis=dict(gridcolor="#222", title="Equity"),
    )
    return fig


def reliability_figure(cal_rows: list[dict]) -> go.Figure:
    fig = go.Figure()
    if cal_rows:
        # cell like "70-79|mid"
        buckets = []
        stated = []
        actual = []
        ns = []
        for r in cal_rows:
            cell = r["cell"]
            bucket = cell.split("|")[0]
            lo, hi = bucket.split("-")
            mid = (int(lo) + int(hi)) / 2
            n = r["n"] or 0
            wins = r["wins"] or 0
            buckets.append(bucket)
            stated.append(mid)
            actual.append((wins / n * 100) if n else 0)
            ns.append(n)
        fig.add_trace(
            go.Scatter(
                x=stated,
                y=actual,
                mode="markers+text",
                text=[f"n={n}" for n in ns],
                textposition="top center",
                marker=dict(size=[max(8, min(40, n / 2)) for n in ns], color="#ffffff"),
                name="Empirical",
            )
        )
    fig.add_trace(
        go.Scatter(x=[50, 100], y=[50, 100], mode="lines", name="Perfect", line=dict(color="#666", dash="dash"))
    )
    fig.update_layout(
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#111111",
        font_color="#f0f0f0",
        height=360,
        xaxis_title="Stated confidence",
        yaxis_title="Actual hit rate %",
        xaxis=dict(range=[45, 105], gridcolor="#222"),
        yaxis=dict(range=[0, 100], gridcolor="#222"),
    )
    return fig


def main() -> None:
    st.markdown(
        f'<div class="tare-header">{_lockup_img}</div>'
        '<p class="tare-tagline">Zero the confidence. Weigh the record. - Flight Recorder</p>',
        unsafe_allow_html=True,
    )

    if LOCKUP.exists():
        st.sidebar.image(str(LOCKUP), use_container_width=True)
    else:
        st.sidebar.markdown("**tare**")
    st.sidebar.caption("Color is a verdict. Green = guarded. Red = shadow / veto.")
    db = st.sidebar.text_input("SQLite path", str(DB_PATH))
    refresh = st.sidebar.number_input("Auto-refresh (s)", 5, 120, 15)
    st.sidebar.markdown("[Brand kit](../brand/tare/README.md) · tokens v1.1")

    rec = get_recorder(db)
    status = rec.get_status()
    decisions = rec.fetch_recent_decisions(80)
    eq_g = pd.DataFrame(rec.fetch_equity("guarded"))
    eq_s = pd.DataFrame(rec.fetch_equity("shadow"))
    cal = rec.fetch_calibration()

    status_raw = str(status.get("status", "unknown")).lower().replace(" ", "-")
    # Header strip
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.caption("Bot status")
        st.markdown(
            f'<span class="tare-status-pill {status_raw}">{status.get("status", "unknown")}</span>',
            unsafe_allow_html=True,
        )
    last_g = float(eq_g["equity"].iloc[-1]) if not eq_g.empty else 10_000.0
    first_g = float(eq_g["equity"].iloc[0]) if not eq_g.empty else last_g
    c2.metric("Equity (guarded)", f"{last_g:,.2f}", f"{last_g - first_g:+.2f}")
    last_s = float(eq_s["equity"].iloc[-1]) if not eq_s.empty else last_g
    c3.metric("Equity (shadow)", f"{last_s:,.2f}")
    open_approx = sum(1 for d in decisions[:20] if d.get("kind") in ("approve", "shrink"))
    c4.metric("Recent approvals", open_approx)

    # Veto flash
    if decisions and decisions[0].get("kind") == "veto":
        d0 = decisions[0]
        st.markdown(
            f'<div class="veto-flash"><b>VETO</b> - {d0.get("reason")} '
            f'(p_adj={d0.get("p_adj")} · p_be={d0.get("p_be")} · anomaly={d0.get("anomaly")})</div>',
            unsafe_allow_html=True,
        )

    tab_live, tab_attack, tab_results = st.tabs(["Live", "Attack Lab", "Results"])

    with tab_live:
        left, right = st.columns(2)
        with left:
            st.subheader("Overconfidence dial")
            if decisions:
                stated = float(decisions[0].get("confidence") or 0)
                p_cal = decisions[0].get("p_cal")
                calibrated = float(p_cal) * 100 if p_cal is not None else stated * 0.5
                st.plotly_chart(overconfidence_gauge(stated, calibrated), use_container_width=True)
            else:
                st.info("No proposals yet. Run the live loop or seed demo data.")

            st.subheader("Bucket overconfidence gap")
            if cal:
                gaps = []
                for r in cal:
                    bucket = r["cell"].split("|")[0]
                    lo, hi = map(int, bucket.split("-"))
                    mid = (lo + hi) / 2
                    n = r["n"] or 0
                    hit = (r["wins"] / n * 100) if n else 0
                    gaps.append({"bucket": bucket, "gap": mid - hit, "n": n})
                gdf = pd.DataFrame(gaps)
                fig = go.Figure(go.Bar(x=gdf["bucket"], y=gdf["gap"], marker_color="#ffffff"))
                fig.update_layout(
                    paper_bgcolor="#0a0a0a",
                    plot_bgcolor="#111111",
                    font_color="#f0f0f0",
                    height=260,
                    yaxis_title="Stated midpoint − hit rate",
                )
                st.plotly_chart(fig, use_container_width=True)

        with right:
            st.subheader("Equity: guarded vs shadow")
            st.plotly_chart(equity_figure(eq_g, eq_s), use_container_width=True)
            st.subheader("Reliability diagram")
            st.plotly_chart(reliability_figure(cal), use_container_width=True)

        st.subheader("Decision log")
        if decisions:
            df = pd.DataFrame(decisions)
            show = df[
                [
                    c
                    for c in [
                        "cycle_ts",
                        "symbol",
                        "side",
                        "action",
                        "confidence",
                        "kind",
                        "reason",
                        "p_adj",
                        "anomaly",
                        "risk_frac",
                        "size",
                    ]
                    if c in df.columns
                ]
            ]
            st.dataframe(show, use_container_width=True, height=320)
            with st.expander("Anomaly breakdown (latest)"):
                raw = decisions[0].get("anomaly_breakdown_json")
                st.json(json.loads(raw) if raw else {})
        else:
            st.write("Empty.")

    with tab_attack:
        st.subheader("Attack Lab")
        st.caption("Replay a scenario through G0 / G1 / G2A / G2.")
        demo_path = ROOT / "docs" / "attack_lab_demo.json"
        if demo_path.exists():
            payload = json.loads(demo_path.read_text())
            demo = payload.get("rows", []) if isinstance(payload, dict) else payload
            trader = payload.get("meta", {}).get("trader") if isinstance(payload, dict) else "demo"
            if trader == "sim" or trader == "demo":
                st.warning(f"Trader = {trader}: not evidence. Run run_attacks.py --llm real.")
            else:
                st.caption(f"Measured with {trader}")
            scenario = st.selectbox("Scenario", sorted({d["scenario_id"] for d in demo}))
            attack = st.selectbox("Attack", sorted({d["attack"] for d in demo}, key=lambda a: (a != "clean", a)))
            rows = [d for d in demo if d["scenario_id"] == scenario and d.get("attack") == attack]
            gates = ["G0", "G1", "G2A", "G2"]
            cols = st.columns(len(gates))
            for i, gate in enumerate(gates):
                g = next((r for r in rows if r.get("gate_config") == gate), None)
                with cols[i]:
                    st.markdown(f"**{gate}**")
                    if g:
                        st.write("APPROVED" if g.get("approved") else "VETO/SKIP")
                        st.write(g.get("reason", ""))
                        st.write(f"confidence={g.get('confidence')} ablated={g.get('ablation_confidence')}")
                        st.write(f"anomaly={round(g.get('anomaly') or 0, 3)} true={g.get('true_result')}")
                        if g.get("checks_fired"):
                            st.write("Checks:", ", ".join(g["checks_fired"]))
                    else:
                        st.write("-")
        else:
            st.warning("No attack_lab_demo.json yet. Run `python scripts/run_attacks.py`.")

        runs = rec.fetch_attack_runs()
        if runs:
            st.dataframe(pd.DataFrame(runs), use_container_width=True, height=300)

    with tab_results:
        st.subheader("HAR table")
        if RESULTS_PATH.exists():
            payload = json.loads(RESULTS_PATH.read_text())
            st.dataframe(pd.DataFrame(payload.get("summary", [])), use_container_width=True)
            with st.expander("Raw rows"):
                st.dataframe(pd.DataFrame(payload.get("rows", [])), use_container_width=True)
        else:
            attack_runs = rec.fetch_attack_runs()
            if attack_runs:
                st.dataframe(pd.DataFrame(attack_runs), use_container_width=True)
            else:
                st.info("Run the attack harness to populate results.")

    st.caption(f"tare · refresh {refresh}s · DB `{db}` · green = net after tare · red = gross / veto")
    # lightweight auto-refresh
    try:
        from streamlit_autorefresh import st_autorefresh  # type: ignore

        st_autorefresh(interval=refresh * 1000, key="rf")
    except Exception:
        pass


if __name__ == "__main__":
    main()
