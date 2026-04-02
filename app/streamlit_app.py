import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
import io

# ──────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────
st.set_page_config(
    page_title="Digital Twin – Groundwater",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────
# GLOBAL CSS
# ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d1117;
    color: #c9d1d9;
}

/* ── HEADER BAND ── */
.header-band {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px 20px;
    margin-bottom: 16px;
}
.pump-badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 6px;
    display: inline-block;
}
.pump-on  { background: #0f7a35; color: #86efac; border: 1px solid #22c55e; }
.pump-off { background: #7c1d1d; color: #fca5a5; border: 1px solid #ef4444; }
.pump-mixed { background: #78350f; color: #fcd34d; border: 1px solid #f59e0b; }

.level-badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    background: #1c2128;
    border: 1px solid #388bfd;
    color: #79c0ff;
    padding: 6px 14px;
    border-radius: 6px;
}

/* ── DOTS NAV ── */
.dots-nav {
    display: flex;
    gap: 12px;
    align-items: center;
}
.dot-nav {
    width: 14px; height: 14px;
    border-radius: 50%;
    background: #30363d;
    border: 2px solid #58a6ff;
    cursor: pointer;
    transition: all 0.2s;
}
.dot-nav.active { background: #58a6ff; }

/* ── STATUS CARDS ── */
.status-block {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
}
.status-block.running { border-left: 4px solid #22c55e; }
.status-block.stopped { border-left: 4px solid #ef4444; }

/* ── PUMP SCHEMA ── */
.pump-schema {
    background: #1c2128;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px;
    margin: 8px 0;
}

/* ── SIDEBAR style override ── */
[data-testid="stSidebar"] {
    background-color: #0d1117;
    border-right: 1px solid #30363d;
}
[data-testid="stSidebar"] * {
    color: #c9d1d9 !important;
}

/* ── METRIC override ── */
[data-testid="stMetric"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px;
}

div[data-testid="stTabs"] button {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
}

/* ── Plotly background ── */
.js-plotly-plot .plotly { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# DATA GENERATION (simulated if no CSV)
# ──────────────────────────────────────────
@st.cache_data
def load_or_simulate():
    try:
        df = pd.read_csv("data/processed/dataset_daily.csv")
        df["date"] = pd.to_datetime(df["date"])
    except Exception:
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", "2025-12-31", freq="D")
        n = len(dates)
        trend = np.linspace(0, -1.5, n)
        seasonal = 3.5 * np.sin(np.arange(n) * 2 * np.pi / 365 + 1.2)
        noise = np.random.normal(0, 0.3, n)
        level = 115.0 + trend + seasonal + noise
        df = pd.DataFrame({
            "date": dates,
            "niveau_nappe": level,
            "pluie_mm": np.random.exponential(4, n),
            "etp_mm": np.random.exponential(3, n)
        })
    return df

@st.cache_data
def load_or_simulate_forecast(df):
    try:
        fc = pd.read_csv("data/processed/forecast_scenarios.csv")
        fc["date"] = pd.to_datetime(fc["date"])
    except Exception:
        last_val = float(df["niveau_nappe"].iloc[-1])
        last_date = df["date"].max()
        fut_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=365, freq="D")
        rows = []
        for sc, delta in [("dry", +1.2), ("medium", 0.0), ("wet", -0.8)]:
            t = np.linspace(0, delta, 365)
            s = 1.5 * np.sin(np.arange(365) * 2 * np.pi / 365 + 1.2)
            noise = np.random.normal(0, 0.2, 365)
            vals = last_val + t + s + noise
            for d, v in zip(fut_dates, vals):
                rows.append({"date": d, "scenario": sc, "niveau_nappe": v})
        fc = pd.DataFrame(rows)
    return fc

df = load_or_simulate()
fc = load_or_simulate_forecast(df)

# ──────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────
defaults = {
    "pump1": True,
    "pump2": False,
    "control_mode": "Automatic",
    "control_log": [],
    "view": "live",          # live | forecast | history
    "sim_running": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Control Panel")
    st.markdown("---")

    # Threshold
    threshold = st.number_input("🎯 Critical Threshold (m)", value=114.2, step=0.1, format="%.1f")

    # Simulation speed (pour la vue live)
    sim_speed = st.slider("⚡ Simulation Speed (days/s)", 1, 60, 15)

    st.markdown("---")
    st.markdown("### 🔧 Pump Control")

    # Mode
    mode = st.radio("Operation Mode", ["Automatic", "Manual"],
                    index=0 if st.session_state.control_mode == "Automatic" else 1,
                    horizontal=True)
    st.session_state.control_mode = mode

    # Pump selection
    st.markdown("**Select Active Pump(s)**")
    p1 = st.checkbox("💧 Pump 1", value=st.session_state.pump1)
    p2 = st.checkbox("💧 Pump 2", value=st.session_state.pump2)
    st.session_state.pump1 = p1
    st.session_state.pump2 = p2

    # Manual controls
    if mode == "Manual":
        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶ Start", use_container_width=True):
                if st.session_state.pump1: st.session_state["pump1_running"] = True
                if st.session_state.pump2: st.session_state["pump2_running"] = True
                st.session_state.control_log.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "action": "Manual START",
                    "pumps": f"P1={'ON' if p1 else 'OFF'} P2={'ON' if p2 else 'OFF'}",
                    "level": float(df["niveau_nappe"].iloc[-1])
                })
        with c2:
            if st.button("■ Stop", use_container_width=True):
                if st.session_state.pump1: st.session_state["pump1_running"] = False
                if st.session_state.pump2: st.session_state["pump2_running"] = False
                st.session_state.control_log.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "action": "Manual STOP",
                    "pumps": f"P1={'ON' if p1 else 'OFF'} P2={'ON' if p2 else 'OFF'}",
                    "level": float(df["niveau_nappe"].iloc[-1])
                })

    # ── Pump Schema (SVG mini-map) ──
    st.markdown("---")
    st.markdown("### 🗺️ Site Overview")

    p1_color = "#22c55e" if st.session_state.pump1 else "#ef4444"
    p2_color = "#22c55e" if st.session_state.pump2 else "#ef4444"
    p1_label = "ON" if st.session_state.pump1 else "OFF"
    p2_label = "ON" if st.session_state.pump2 else "OFF"

    st.markdown(f"""
    <svg viewBox="0 0 220 160" xmlns="http://www.w3.org/2000/svg"
         style="width:100%; background:#1c2128; border-radius:8px; border:1px solid #30363d;">
      <!-- Ground -->
      <rect x="0" y="100" width="220" height="60" fill="#1a2e1a" opacity="0.6"/>
      <!-- Water table -->
      <rect x="10" y="110" width="200" height="20" rx="4" fill="#1d4ed8" opacity="0.5"/>
      <text x="110" y="124" text-anchor="middle" fill="#93c5fd" font-size="8" font-family="monospace">Water Table</text>
      <!-- Surface -->
      <rect x="0" y="85" width="220" height="15" fill="#374151" opacity="0.8"/>
      <text x="10" y="96" fill="#6b7280" font-size="7" font-family="monospace">Ground Level</text>
      <!-- Control center -->
      <rect x="85" y="30" width="50" height="35" rx="4" fill="#1e3a5f" stroke="#58a6ff" stroke-width="1.5"/>
      <text x="110" y="50" text-anchor="middle" fill="#93c5fd" font-size="7" font-family="monospace">Control</text>
      <text x="110" y="60" text-anchor="middle" fill="#93c5fd" font-size="7" font-family="monospace">Center</text>
      <!-- Pipe to pump1 -->
      <line x1="90" y1="65" x2="50" y2="100" stroke="#475569" stroke-width="2"/>
      <!-- Pipe to pump2 -->
      <line x1="130" y1="65" x2="170" y2="100" stroke="#475569" stroke-width="2"/>
      <!-- PUMP 1 -->
      <circle cx="40" cy="100" r="12" fill="{p1_color}" opacity="0.85" stroke="#fff" stroke-width="1"/>
      <text x="40" y="104" text-anchor="middle" fill="white" font-size="7" font-weight="bold">P1</text>
      <text x="40" y="118" text-anchor="middle" fill="{p1_color}" font-size="7" font-family="monospace">{p1_label}</text>
      <!-- PUMP 2 -->
      <circle cx="180" cy="100" r="12" fill="{p2_color}" opacity="0.85" stroke="#fff" stroke-width="1"/>
      <text x="180" y="104" text-anchor="middle" fill="white" font-size="7" font-weight="bold">P2</text>
      <text x="180" y="118" text-anchor="middle" fill="{p2_color}" font-size="7" font-family="monospace">{p2_label}</text>
      <!-- Piezometer -->
      <rect x="105" y="88" width="10" height="25" fill="#78350f" stroke="#f59e0b" stroke-width="1"/>
      <text x="110" y="80" text-anchor="middle" fill="#fbbf24" font-size="7" font-family="monospace">Piezo</text>
      <!-- Aquifer extraction arrows -->
      <line x1="40" y1="112" x2="40" y2="128" stroke="{p1_color}" stroke-width="1.5" stroke-dasharray="2,2"/>
      <line x1="180" y1="112" x2="180" y2="128" stroke="{p2_color}" stroke-width="1.5" stroke-dasharray="2,2"/>
    </svg>
    """, unsafe_allow_html=True)

    # ── PDF Report ──
    st.markdown("---")
    st.markdown("### 📄 Automatic Report")
    if st.button("📥 Generate PDF Report", use_container_width=True):
        # Simple text report as placeholder
        report_lines = [
            "GROUNDWATER DIGITAL TWIN – AUTO REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 40,
            f"Current Level : {df['niveau_nappe'].iloc[-1]:.2f} m",
            f"Critical Threshold : {threshold:.2f} m",
            f"Pump 1 : {'ACTIVE' if p1 else 'INACTIVE'}",
            f"Pump 2 : {'ACTIVE' if p2 else 'INACTIVE'}",
            f"Mode : {mode}",
            "",
            "ACTION LOG (last 10):",
        ]
        for entry in st.session_state.control_log[-10:]:
            report_lines.append(f"  {entry.get('time','')} | {entry.get('action','')} | Level={entry.get('level', ''):.2f}m")

        report_text = "\n".join(report_lines)
        st.download_button(
            "⬇️ Download Report (.txt)",
            data=report_text,
            file_name=f"groundwater_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True
        )

# ──────────────────────────────────────────
# CURRENT STATE COMPUTATION
# ──────────────────────────────────────────
current_level = float(df["niveau_nappe"].iloc[-1])
current_date  = df["date"].iloc[-1]
is_safe = current_level > threshold

any_pump_active = st.session_state.pump1 or st.session_state.pump2

if mode == "Automatic":
    pump_on = is_safe and any_pump_active
else:
    pump_on = any_pump_active  # manual decides

# Pump status label
if not any_pump_active:
    pump_label = "ALL PUMPS OFF"
    pump_cls   = "pump-off"
elif st.session_state.pump1 and st.session_state.pump2:
    pump_label = "PUMP 1 + 2 ON" if pump_on else "PUMP 1 + 2 – STOPPED"
    pump_cls   = "pump-on" if pump_on else "pump-off"
elif st.session_state.pump1:
    pump_label = "PUMP 1 ON" if pump_on else "PUMP 1 – STOPPED"
    pump_cls   = "pump-on" if pump_on else "pump-off"
else:
    pump_label = "PUMP 2 ON" if pump_on else "PUMP 2 – STOPPED"
    pump_cls   = "pump-on" if pump_on else "pump-off"

# ──────────────────────────────────────────
# HEADER BAND
# ──────────────────────────────────────────
view_labels = {"live": "1", "forecast": "2", "history": "3"}
view_names  = ["live", "forecast", "history"]

dots_html = ""
for vn in view_names:
    active_cls = "active" if st.session_state.view == vn else ""
    dots_html += f'<div class="dot-nav {active_cls}" title="{vn}"></div>'

st.markdown(f"""
<div class="header-band">
    <div>
        <span class="pump-badge {pump_cls}">⚡ {pump_label}</span>
    </div>
    <div class="dots-nav">
        {dots_html}
        <span style="font-family:monospace;font-size:0.72rem;color:#58a6ff;margin-left:6px;">
            view {view_labels.get(st.session_state.view,'?')}
        </span>
    </div>
    <div>
        <span class="level-badge">
            📅 {current_date.strftime('%Y-%m-%d')} &nbsp;|&nbsp; 💧 {current_level:.2f} m
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# VIEW SELECTOR (radio → 3 views)
# ──────────────────────────────────────────
view_choice = st.radio(
    "Select view",
    ["📡 Live (1 year)", "📈 Forecasting", "📋 Full History"],
    horizontal=True,
    label_visibility="collapsed"
)
view_map = {"📡 Live (1 year)": "live", "📈 Forecasting": "forecast", "📋 Full History": "history"}
st.session_state.view = view_map[view_choice]

# ──────────────────────────────────────────
# PLOTLY THEME HELPER
# ──────────────────────────────────────────
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0d1117",
    font=dict(family="IBM Plex Mono", color="#c9d1d9", size=11),
    xaxis=dict(gridcolor="#21262d", zeroline=False, showline=True, linecolor="#30363d"),
    yaxis=dict(gridcolor="#21262d", zeroline=False, showline=True, linecolor="#30363d"),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#30363d", borderwidth=1,
                font=dict(family="IBM Plex Mono", size=10))
)

def apply_theme(fig):
    fig.update_layout(**PLOT_LAYOUT)
    return fig

def add_threshold_line(fig, thr):
    fig.add_hline(
        y=thr, line_dash="dash", line_color="#ef4444", line_width=1.5,
        annotation_text=f"Threshold {thr:.1f} m",
        annotation_font=dict(color="#ef4444", size=10),
        annotation_position="top left"
    )
    return fig

# ──────────────────────────────────────────
# ── VIEW 1 : LIVE SIMULATION ──
# ──────────────────────────────────────────
if st.session_state.view == "live":
    st.markdown("### 📡 Water Level – Live Simulation (1 year)")

    sim_start = pd.Timestamp("2025-01-01")
    sim_end   = sim_start + pd.Timedelta(days=365)
    sim_df    = df[(df["date"] >= sim_start) & (df["date"] <= sim_end)].copy()

    col_chart, col_status = st.columns([3, 1])

    with col_status:
        st.markdown("#### System Status")
        pump_color = "#22c55e" if pump_on else "#ef4444"
        pump_text  = "RUNNING" if pump_on else "STOPPED"
        st.markdown(f"""
        <div class="status-block {'running' if pump_on else 'stopped'}">
            <div style="color:{pump_color};font-size:1.1rem;">● {pump_text}</div>
            <div style="color:#8b949e;margin-top:4px;">Level: {current_level:.2f} m</div>
            <div style="color:#8b949e;">Threshold: {threshold:.1f} m</div>
            <div style="color:#8b949e;">Mode: {mode}</div>
        </div>
        """, unsafe_allow_html=True)

        # Metrics
        st.metric("Pump 1", "🟢 ON" if st.session_state.pump1 else "🔴 OFF")
        st.metric("Pump 2", "🟢 ON" if st.session_state.pump2 else "🔴 OFF")

        if st.session_state.control_log:
            st.markdown("**Last actions**")
            for entry in reversed(st.session_state.control_log[-4:]):
                st.markdown(f"""
                <div style="font-family:monospace;font-size:0.68rem;
                            background:#161b22;padding:5px 8px;border-radius:5px;margin:3px 0;
                            border-left:3px solid #388bfd;">
                    {entry.get('time','')} {entry.get('action','')}
                </div>
                """, unsafe_allow_html=True)

    with col_chart:
        start_btn = st.button("▶️ Start Live Simulation", type="primary")

        chart_ph = st.empty()

        # Static preview before simulation
        fig_static = go.Figure()
        fig_static.add_trace(go.Scatter(
            x=sim_df["date"], y=sim_df["niveau_nappe"],
            mode="lines", name="Historical",
            line=dict(color="#388bfd", width=2), opacity=0.6
        ))
        add_threshold_line(fig_static, threshold)
        apply_theme(fig_static)
        fig_static.update_layout(height=420, title="Water Level 2025 (click ▶️ to animate)")
        chart_ph.plotly_chart(fig_static, use_container_width=True)

        if start_btn and not sim_df.empty:
            log_ph = st.empty()
            state_log = []
            cur_state = None
            period_start = None

            for i, row in sim_df.iterrows():
                today     = row["date"]
                lvl       = row["niveau_nappe"]
                safe_now  = lvl > threshold
                dam_state = "Running" if (safe_now and any_pump_active) else "Stopped"

                if dam_state != cur_state:
                    if cur_state is not None:
                        state_log.append({
                            "Status": cur_state,
                            "From": period_start.strftime("%Y-%m-%d"),
                            "To": (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                            "Days": (today - period_start).days,
                        })
                        log_ph.dataframe(pd.DataFrame(state_log), use_container_width=True)
                    cur_state    = dam_state
                    period_start = today

                sub = sim_df[sim_df["date"] <= today]
                color_line = "#22c55e" if dam_state == "Running" else "#ef4444"

                fig = go.Figure()
                # Full grey background
                fig.add_trace(go.Scatter(
                    x=sim_df["date"], y=sim_df["niveau_nappe"],
                    mode="lines", name="Full year",
                    line=dict(color="#30363d", width=1.5), opacity=0.4
                ))
                # Animated progress
                fig.add_trace(go.Scatter(
                    x=sub["date"], y=sub["niveau_nappe"],
                    mode="lines", name="Simulation",
                    line=dict(color=color_line, width=2.5)
                ))
                # Current day marker
                fig.add_trace(go.Scatter(
                    x=[today], y=[lvl],
                    mode="markers+text",
                    marker=dict(size=10, color="#f59e0b", symbol="circle"),
                    text=[f"{lvl:.2f}m"], textposition="top center",
                    textfont=dict(color="#f59e0b", size=10),
                    name="Now"
                ))
                add_threshold_line(fig, threshold)

                # Day banner annotation
                fig.add_annotation(
                    x=today, y=1.05, xref="x", yref="paper",
                    text=f"📅 {today.strftime('%Y-%m-%d')} | {dam_state}",
                    showarrow=False,
                    font=dict(size=11, color="#f59e0b", family="IBM Plex Mono"),
                    bgcolor="rgba(0,0,0,0.6)", borderpad=4, xanchor="center"
                )
                apply_theme(fig)
                fig.update_layout(height=420, showlegend=True,
                                  xaxis=dict(range=[sim_df["date"].min(), sim_df["date"].max()]))
                chart_ph.plotly_chart(fig, use_container_width=True)
                time.sleep(1.0 / sim_speed)

            # Final summary
            total_run  = sum(x["Days"] for x in state_log if x["Status"] == "Running")
            total_stop = sum(x["Days"] for x in state_log if x["Status"] == "Stopped")
            st.success(f"✅ Simulation complete — **{total_run} days running** / **{total_stop} days stopped**")

# ──────────────────────────────────────────
# ── VIEW 2 : FORECASTING ──
# ──────────────────────────────────────────
elif st.session_state.view == "forecast":
    st.markdown("### 📈 Forecasting – Scenario Analysis")

    last_hist_date = df["date"].max()
    fc_future = fc[fc["date"] > last_hist_date].copy()

    # Controls row
    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        scenario_choice = st.multiselect(
            "Active Scenarios",
            ["dry", "medium", "wet"],
            default=["dry", "medium", "wet"]
        )
    with fc2:
        add_stop_point = st.checkbox("➕ Add extra data point", value=False)
    with fc3:
        if add_stop_point:
            extra_date  = st.date_input("Extra date", value=last_hist_date.date())
            extra_level = st.number_input("Level (m)", value=float(df["niveau_nappe"].iloc[-1]), step=0.1)

    # ── TOP: historical + forecast ──
    fig_top = go.Figure()
    # Historical
    fig_top.add_trace(go.Scatter(
        x=df["date"], y=df["niveau_nappe"],
        mode="lines", name="Historical",
        line=dict(color="#388bfd", width=2)
    ))

    sc_colors = {"dry": "#94a3b8", "medium": "#f59e0b", "wet": "#34d399"}
    for sc in scenario_choice:
        sc_data = fc_future[fc_future["scenario"] == sc]
        if not sc_data.empty:
            fig_top.add_trace(go.Scatter(
                x=sc_data["date"], y=sc_data["niveau_nappe"],
                mode="lines", name=f"Forecast: {sc.capitalize()}",
                line=dict(color=sc_colors[sc], width=2, dash="dot"), opacity=0.9
            ))

    # Extra point if added
    if add_stop_point:
        extra_ts = pd.Timestamp(extra_date)
        fig_top.add_trace(go.Scatter(
            x=[extra_ts], y=[extra_level],
            mode="markers", name="Extra point",
            marker=dict(size=12, color="#f43f5e", symbol="star")
        ))

    add_threshold_line(fig_top, threshold)
    apply_theme(fig_top)
    fig_top.update_layout(height=350, title="Historical + Forecast Scenarios")
    st.plotly_chart(fig_top, use_container_width=True)

    # ── BOTTOM: forecast-only zoomed window ──
    st.markdown("#### 🔍 Forecast Detail Window")
    if not fc_future.empty:
        fig_bot = go.Figure()
        for sc in scenario_choice:
            sc_data = fc_future[fc_future["scenario"] == sc]
            if not sc_data.empty:
                # Confidence band
                band_w = 0.4
                fig_bot.add_trace(go.Scatter(
                    x=pd.concat([sc_data["date"], sc_data["date"][::-1]]),
                    y=pd.concat([sc_data["niveau_nappe"] + band_w,
                                 sc_data["niveau_nappe"][::-1] - band_w]),
                    fill="toself", fillcolor=sc_colors[sc],
                    opacity=0.12, line=dict(width=0),
                    name=f"{sc.capitalize()} band", showlegend=False
                ))
                fig_bot.add_trace(go.Scatter(
                    x=sc_data["date"], y=sc_data["niveau_nappe"],
                    mode="lines", name=f"{sc.capitalize()}",
                    line=dict(color=sc_colors[sc], width=2)
                ))

        # Recalculated forecast if extra point added
        if add_stop_point:
            extra_ts = pd.Timestamp(extra_date)
            extra_lv = float(extra_level)
            recompute_dates = fc_future[fc_future["date"] >= extra_ts]["date"].unique()
            for sc, delta in [("dry", +0.8), ("medium", 0.0), ("wet", -0.6)]:
                if sc in scenario_choice:
                    t2 = np.linspace(0, delta, len(recompute_dates))
                    vals2 = extra_lv + t2 + np.random.normal(0, 0.15, len(recompute_dates))
                    fig_bot.add_trace(go.Scatter(
                        x=recompute_dates, y=vals2,
                        mode="lines", name=f"{sc.capitalize()} (recalc.)",
                        line=dict(color=sc_colors[sc], width=1.5, dash="dashdot"),
                        opacity=0.7
                    ))
            fig_bot.add_trace(go.Scatter(
                x=[extra_ts], y=[extra_lv],
                mode="markers", name="Extra point",
                marker=dict(size=12, color="#f43f5e", symbol="star")
            ))

        add_threshold_line(fig_bot, threshold)
        apply_theme(fig_bot)
        fig_bot.update_layout(height=300, title="Forecast-Only Window (with uncertainty bands)")
        st.plotly_chart(fig_bot, use_container_width=True)
    else:
        st.info("No future forecast data available.")

    # Summary metrics
    if not fc_future.empty:
        st.markdown("#### 📊 End-of-Period Forecast Summary")
        mc1, mc2, mc3 = st.columns(3)
        for col_m, sc in zip([mc1, mc2, mc3], ["dry", "medium", "wet"]):
            sc_end = fc_future[fc_future["scenario"] == sc]
            if not sc_end.empty:
                val = sc_end["niveau_nappe"].iloc[-1]
                delta_val = val - current_level
                col_m.metric(f"{sc.capitalize()} Scenario", f"{val:.2f} m",
                             delta=f"{delta_val:+.2f} m vs now")

# ──────────────────────────────────────────
# ── VIEW 3 : FULL HISTORY ──
# ──────────────────────────────────────────
elif st.session_state.view == "history":
    st.markdown("### 📋 Full Historical Record")

    h1, h2 = st.columns([3, 1])

    with h1:
        # Date range filter
        date_range = st.date_input(
            "Date range",
            value=[df["date"].min().date(), df["date"].max().date()],
            min_value=df["date"].min().date(),
            max_value=df["date"].max().date()
        )
        if len(date_range) == 2:
            filtered = df[(df["date"] >= pd.Timestamp(date_range[0])) &
                          (df["date"] <= pd.Timestamp(date_range[1]))]
        else:
            filtered = df.copy()

        fig_hist = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                 row_heights=[0.7, 0.3],
                                 subplot_titles=["Water Level (m)", "Rainfall (mm)"])
        fig_hist.add_trace(go.Scatter(
            x=filtered["date"], y=filtered["niveau_nappe"],
            mode="lines", name="Water Level",
            line=dict(color="#388bfd", width=1.8)
        ), row=1, col=1)
        fig_hist.add_hline(y=threshold, line_dash="dash", line_color="#ef4444",
                           annotation_text="Threshold", annotation_position="top left",
                           row=1, col=1)
        if "pluie_mm" in filtered.columns:
            fig_hist.add_trace(go.Bar(
                x=filtered["date"], y=filtered["pluie_mm"],
                name="Rainfall", marker_color="#34d399", opacity=0.6
            ), row=2, col=1)

        fig_hist.update_layout(
            height=500,
            **{k: v for k, v in PLOT_LAYOUT.items() if k not in ("xaxis", "yaxis")}
        )
        fig_hist.update_xaxes(gridcolor="#21262d", linecolor="#30363d")
        fig_hist.update_yaxes(gridcolor="#21262d", linecolor="#30363d")
        st.plotly_chart(fig_hist, use_container_width=True)

    with h2:
        st.markdown("#### 📊 Stats")
        if not filtered.empty:
            st.metric("Min Level", f"{filtered['niveau_nappe'].min():.2f} m")
            st.metric("Max Level", f"{filtered['niveau_nappe'].max():.2f} m")
            st.metric("Mean Level", f"{filtered['niveau_nappe'].mean():.2f} m")
            days_below = (filtered["niveau_nappe"] < threshold).sum()
            st.metric("Days below threshold", f"{days_below} d")
            pct = days_below / len(filtered) * 100 if len(filtered) > 0 else 0
            st.metric("% time critical", f"{pct:.1f}%")

        st.markdown("---")
        st.markdown("#### 📥 Export Data")
        csv = filtered.to_csv(index=False)
        st.download_button("⬇️ Download CSV", data=csv,
                           file_name="groundwater_history.csv", mime="text/csv",
                           use_container_width=True)

    # Action log
    if st.session_state.control_log:
        st.markdown("#### 📋 Control Action Log")
        log_df = pd.DataFrame(st.session_state.control_log)
        st.dataframe(log_df[::-1], use_container_width=True)
        csv_log = log_df.to_csv(index=False)
        st.download_button("⬇️ Export Action Log", data=csv_log,
                           file_name="action_log.csv", mime="text/csv")
    else:
        st.info("No control actions recorded yet.")
