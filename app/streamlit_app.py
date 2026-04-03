import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
import io

st.set_page_config(
    page_title="Digital Twin – Groundwater",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #f4f7fb;
    color: #1a2233;
}
.header-band {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #ffffff;
    border: 1px solid #d0d9e8;
    border-radius: 10px;
    padding: 12px 20px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
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
.level-badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    background: #e8f0fe;
    border: 1px solid #4a80f5;
    color: #1a56db;
    padding: 6px 14px;
    border-radius: 6px;
}
.dots-nav { display: flex; gap: 12px; align-items: center; }
.dot-nav {
    width: 14px; height: 14px;
    border-radius: 50%;
    background: #d0d9e8;
    border: 2px solid #4a80f5;
}
.dot-nav.active { background: #4a80f5; }
.status-block {
    background: #ffffff;
    border: 1px solid #d0d9e8;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #1a2233;
}
.status-block.running { border-left: 4px solid #16a34a; }
.status-block.stopped { border-left: 4px solid #dc2626; }
[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #d0d9e8; }
[data-testid="stSidebar"] * { color: #1a2233 !important; }
[data-testid="stMetric"] {
    background: #ffffff; border: 1px solid #d0d9e8;
    border-radius: 8px; padding: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

# ── DATA ──
@st.cache_data
def load_or_simulate():
    try:
        df = pd.read_csv("data/processed/dataset_daily.csv")
        df["date"] = pd.to_datetime(df["date"])
    except Exception:
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", "2025-12-31", freq="D")
        n = len(dates)
        level = 115.0 + np.linspace(0, -1.5, n) + 3.5*np.sin(np.arange(n)*2*np.pi/365+1.2) + np.random.normal(0,0.3,n)
        df = pd.DataFrame({
            "date": dates, "niveau_nappe": level,
            "pluie_mm": np.random.exponential(4, n),
            "etp_mm":   np.random.exponential(3, n)
        })
    return df

@st.cache_data
def load_or_simulate_forecast(df):
    try:
        fc = pd.read_csv("data/processed/forecast_scenarios.csv")
        fc["date"] = pd.to_datetime(fc["date"])
    except Exception:
        last_val  = float(df["niveau_nappe"].iloc[-1])
        last_date = df["date"].max()
        fut_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=365, freq="D")
        rows = []
        for sc, delta in [("dry", +1.2), ("medium", 0.0), ("wet", -0.8)]:
            t = np.linspace(0, delta, 365)
            s = 1.5 * np.sin(np.arange(365) * 2*np.pi/365 + 1.2)
            noise = np.random.normal(0, 0.2, 365)
            for d, v in zip(fut_dates, last_val + t + s + noise):
                rows.append({"date": d, "scenario": sc, "niveau_nappe": v})
        fc = pd.DataFrame(rows)
    return fc

df = load_or_simulate()
fc = load_or_simulate_forecast(df)

# ── SESSION STATE ──
defaults = {
    "pump1": True, "pump2": False,
    "control_mode": "Automatic",
    "control_log": [],
    "view": "live",
    "sim_running": False,
    "live_stopped_at": None,
    "live_stopped_level": None,
    "auto_forecast": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── SIDEBAR ──
with st.sidebar:
    st.markdown("### ⚙️ Control Panel")
    st.markdown("---")
    threshold = st.number_input("🎯 Critical Threshold (m)", value=114.2, step=0.1, format="%.1f")
    sim_speed = st.slider("⚡ Simulation Speed (days/s)", 1, 60, 15)
    st.markdown("---")
    st.markdown("### 🔧 Pump Control")
    mode = st.radio("Operation Mode", ["Automatic", "Manual"],
                    index=0 if st.session_state.control_mode == "Automatic" else 1,
                    horizontal=True)
    st.session_state.control_mode = mode

    st.markdown("**Select Active Pump(s)**")
    p1 = st.checkbox("💧 Pump 1", value=st.session_state.pump1)
    p2 = st.checkbox("💧 Pump 2", value=st.session_state.pump2)
    st.session_state.pump1 = p1
    st.session_state.pump2 = p2

    st.markdown("---")
    st.markdown("### ▶️ Live Simulation")
    sb1, sb2 = st.columns(2)
    with sb1:
        if st.button("▶ Start", use_container_width=True, type="primary"):
            st.session_state.sim_running = True
            st.session_state.auto_forecast = False
            st.session_state.live_stopped_at = None
            st.session_state.live_stopped_level = None
            st.session_state.view = "live"
            st.session_state.control_log.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "action": "Live START",
                "pumps": f"P1={'ON' if p1 else 'OFF'} P2={'ON' if p2 else 'OFF'}",
                "level": float(df["niveau_nappe"].iloc[-1])
            })
    with sb2:
        if st.button("■ Stop", use_container_width=True):
            st.session_state.sim_running = False
            st.session_state.live_stopped_at    = st.session_state.get("live_stopped_at") or df["date"].iloc[-1]
            st.session_state.live_stopped_level = st.session_state.get("live_stopped_level") or float(df["niveau_nappe"].iloc[-1])
            st.session_state.auto_forecast = True
            st.session_state.control_log.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "action": "Live STOP → Forecast",
                "pumps": f"P1={'ON' if p1 else 'OFF'} P2={'ON' if p2 else 'OFF'}",
                "level": st.session_state.live_stopped_level
            })
            st.rerun()

    if mode == "Manual":
        st.markdown("**Manual Pump Override**")
        mc1, mc2 = st.columns(2)
        with mc1:
            if st.button("💧 Pump ON", use_container_width=True):
                st.session_state.control_log.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "action": "Manual pump ON",
                    "pumps": f"P1={'ON' if p1 else 'OFF'} P2={'ON' if p2 else 'OFF'}",
                    "level": float(df["niveau_nappe"].iloc[-1])
                })
        with mc2:
            if st.button("🚫 Pump OFF", use_container_width=True):
                st.session_state.control_log.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "action": "Manual pump OFF",
                    "pumps": f"P1={'ON' if p1 else 'OFF'} P2={'ON' if p2 else 'OFF'}",
                    "level": float(df["niveau_nappe"].iloc[-1])
                })

    # ── Mini-map SVG (dynamique selon état des pompes) ──
    st.markdown("---")
    st.markdown("### 🗺️ Site Overview")

    p1_col = "#16a34a" if st.session_state.pump1 else "#dc2626"
    p2_col = "#16a34a" if st.session_state.pump2 else "#dc2626"
    p1_lbl = "ON"  if st.session_state.pump1 else "OFF"
    p2_lbl = "ON"  if st.session_state.pump2 else "OFF"

    st.markdown(f"""
    <svg viewBox="0 0 260 230" xmlns="http://www.w3.org/2000/svg"
         style="width:100%;border-radius:8px;border:1px solid #d0d9e8;background:#eef4e8;">
      <!-- Contours topo -->
      <ellipse cx="130" cy="118" rx="118" ry="90" fill="none" stroke="#c8d8a8" stroke-width="0.8" stroke-dasharray="4,3"/>
      <ellipse cx="130" cy="118" rx="85"  ry="65" fill="none" stroke="#bece98" stroke-width="0.8" stroke-dasharray="4,3"/>
      <ellipse cx="130" cy="118" rx="52"  ry="40" fill="none" stroke="#b4c488" stroke-width="0.8" stroke-dasharray="4,3"/>
      <!-- Route D120 -->
      <path d="M12 72 Q130 78 248 70" fill="none" stroke="#f5c842" stroke-width="7" opacity="0.85"/>
      <text x="130" y="67" text-anchor="middle" fill="#78620a" font-size="7" font-family="monospace">D120</text>
      <!-- Station traitement -->
      <rect x="110" y="18" width="40" height="28" rx="3" fill="#94a3b8" stroke="#64748b" stroke-width="0.5"/>
      <rect x="118" y="14" width="24" height="7" rx="1" fill="#64748b"/>
      <text x="130" y="56" text-anchor="middle" fill="#475569" font-size="6" font-family="monospace">Station</text>
      <!-- Ligne de sol -->
      <line x1="12" y1="130" x2="248" y2="130" stroke="#94a3b8" stroke-width="0.8" stroke-dasharray="5,3"/>
      <text x="16" y="127" fill="#64748b" font-size="6" font-family="monospace">Sol</text>
      <!-- Aquifere -->
      <ellipse cx="130" cy="185" rx="105" ry="30" fill="#bfdbfe" opacity="0.5"/>
      <text x="130" y="189" text-anchor="middle" fill="#1e40af" font-size="6" font-family="monospace">Aquifere / Nappe phréatique</text>
      <!-- PUMP 1 forage -->
      <rect x="64" y="130" width="4" height="50" rx="2" fill="#6b7280" opacity="0.7"/>
      <rect x="58" y="148" width="3" height="32" rx="1" fill="#92400e" opacity="0.6"/>
      <!-- PUMP 1 tête -->
      <rect x="50" y="114" width="32" height="17" rx="3" fill="{p1_col}" stroke="white" stroke-width="1"/>
      <text x="66" y="126" text-anchor="middle" fill="white" font-size="6" font-weight="bold" font-family="monospace">P1 {p1_lbl}</text>
      <!-- Tuyau P1 → Station -->
      <path d="M66 114 L66 95 L118 95 L118 46" fill="none" stroke="{p1_col}" stroke-width="1.8"/>
      <polygon points="115,46 118,40 121,46" fill="{p1_col}"/>
      <!-- Ondes P1 -->
      <ellipse cx="66" cy="170" rx="14" ry="6" fill="{p1_col}" opacity="0.25"/>
      <ellipse cx="66" cy="178" rx="10" ry="4" fill="{p1_col}" opacity="0.15"/>
      <!-- PUMP 2 forage -->
      <rect x="192" y="130" width="4" height="50" rx="2" fill="#6b7280" opacity="0.7"/>
      <rect x="198" y="148" width="3" height="32" rx="1" fill="#92400e" opacity="0.6"/>
      <!-- PUMP 2 tête -->
      <rect x="178" y="114" width="32" height="17" rx="3" fill="{p2_col}" stroke="white" stroke-width="1"/>
      <text x="194" y="126" text-anchor="middle" fill="white" font-size="6" font-weight="bold" font-family="monospace">P2 {p2_lbl}</text>
      <!-- Tuyau P2 → Station -->
      <path d="M194 114 L194 95 L142 95 L142 46" fill="none" stroke="{p2_col}" stroke-width="1.8"/>
      <polygon points="139,46 142,40 145,46" fill="{p2_col}"/>
      <!-- Ondes P2 -->
      <ellipse cx="194" cy="170" rx="14" ry="6" fill="{p2_col}" opacity="0.25"/>
      <ellipse cx="194" cy="178" rx="10" ry="4" fill="{p2_col}" opacity="0.15"/>
      <!-- Nord -->
      <text x="20" y="100" fill="#334155" font-size="9" font-weight="bold" font-family="monospace">N</text>
      <line x1="23" y1="103" x2="23" y2="114" stroke="#334155" stroke-width="1.2"/>
      <polygon points="20,114 23,120 26,114" fill="#334155"/>
      <!-- Légende -->
      <rect x="14" y="196" width="105" height="26" rx="3" fill="white" stroke="#e2e8f0" stroke-width="0.5" opacity="0.9"/>
      <rect x="20" y="203" width="9" height="9" rx="2" fill="#16a34a"/>
      <text x="33" y="211" fill="#334155" font-size="6" font-family="monospace">Active</text>
      <rect x="60" y="203" width="9" height="9" rx="2" fill="#dc2626"/>
      <text x="73" y="211" fill="#334155" font-size="6" font-family="monospace">Inactive</text>
      <rect x="20" y="213" width="3" height="8" rx="1" fill="#92400e" opacity="0.7"/>
      <text x="27" y="220" fill="#334155" font-size="6" font-family="monospace">Piézomètre</text>
    </svg>
    """, unsafe_allow_html=True)

    # ── Rapport ──
    st.markdown("---")
    st.markdown("### 📄 Automatic Report")
    if st.button("📥 Generate PDF Report", use_container_width=True):
        report_lines = [
            "GROUNDWATER DIGITAL TWIN – AUTO REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 40,
            f"Current Level : {df['niveau_nappe'].iloc[-1]:.2f} m",
            f"Critical Threshold : {threshold:.2f} m",
            f"Pump 1 : {'ACTIVE' if p1 else 'INACTIVE'}",
            f"Pump 2 : {'ACTIVE' if p2 else 'INACTIVE'}",
            f"Mode : {mode}", "",
            "ACTION LOG (last 10):",
        ]
        for entry in st.session_state.control_log[-10:]:
            report_lines.append(f"  {entry.get('time','')} | {entry.get('action','')} | Level={entry.get('level',''):.2f}m")
        st.download_button(
            "⬇️ Download Report (.txt)",
            data="\n".join(report_lines),
            file_name=f"groundwater_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain", use_container_width=True
        )

# ── CURRENT STATE ──
current_level = float(df["niveau_nappe"].iloc[-1])
current_date  = df["date"].iloc[-1]
is_safe       = current_level > threshold
any_pump_active = st.session_state.pump1 or st.session_state.pump2
pump_on = (is_safe and any_pump_active) if mode == "Automatic" else any_pump_active

if not any_pump_active:
    pump_label, pump_cls = "ALL PUMPS OFF", "pump-off"
elif st.session_state.pump1 and st.session_state.pump2:
    pump_label = "PUMP 1 + 2 ON" if pump_on else "PUMP 1 + 2 – STOPPED"
    pump_cls   = "pump-on" if pump_on else "pump-off"
elif st.session_state.pump1:
    pump_label = "PUMP 1 ON" if pump_on else "PUMP 1 – STOPPED"
    pump_cls   = "pump-on" if pump_on else "pump-off"
else:
    pump_label = "PUMP 2 ON" if pump_on else "PUMP 2 – STOPPED"
    pump_cls   = "pump-on" if pump_on else "pump-off"

# ── HEADER BAND ──
view_labels = {"live": "1", "forecast": "2", "history": "3"}
dots_html = "".join(
    f'<div class="dot-nav {"active" if st.session_state.view == vn else ""}" title="{vn}"></div>'
    for vn in ["live", "forecast", "history"]
)
st.markdown(f"""
<div class="header-band">
    <div><span class="pump-badge {pump_cls}">⚡ {pump_label}</span></div>
    <div class="dots-nav">
        {dots_html}
        <span style="font-family:monospace;font-size:0.72rem;color:#4a80f5;margin-left:6px;">
            view {view_labels.get(st.session_state.view,'?')}
        </span>
    </div>
    <div><span class="level-badge">📅 {current_date.strftime('%Y-%m-%d')} &nbsp;|&nbsp; 💧 {current_level:.2f} m</span></div>
</div>
""", unsafe_allow_html=True)

# ── VIEW SELECTOR ──
# FIX: use st.columns + st.button (no raw HTML rendering issue)
nav1, nav2, nav3 = st.columns(3)
with nav1:
    if st.button("📡 Live", use_container_width=True,
                 type="primary" if st.session_state.view == "live" else "secondary"):
        st.session_state.view = "live"
with nav2:
    if st.button("📈 Forecasting", use_container_width=True,
                 type="primary" if st.session_state.view == "forecast" else "secondary"):
        st.session_state.view = "forecast"
with nav3:
    if st.button("📋 History", use_container_width=True,
                 type="primary" if st.session_state.view == "history" else "secondary"):
        st.session_state.view = "history"

# Pump status badges (clean, no raw HTML)
b1, b2 = st.columns(2)
p1_color = "#16a34a" if st.session_state.pump1 else "#dc2626"
p2_color = "#16a34a" if st.session_state.pump2 else "#dc2626"
p1_state = "ON" if st.session_state.pump1 else "OFF"
p2_state = "ON" if st.session_state.pump2 else "OFF"
with b1:
    st.markdown(
        f'<div style="background:{p1_color};color:white;padding:6px 10px;border-radius:6px;'
        f'font-family:monospace;font-size:0.8rem;text-align:center;">⚡ Pump 1 {p1_state}</div>',
        unsafe_allow_html=True
    )
with b2:
    st.markdown(
        f'<div style="background:{p2_color};color:white;padding:6px 10px;border-radius:6px;'
        f'font-family:monospace;font-size:0.8rem;text-align:center;">⚡ Pump 2 {p2_state}</div>',
        unsafe_allow_html=True
    )

st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)

# Auto-switch after Stop
if st.session_state.auto_forecast:
    st.session_state.view = "forecast"
    st.session_state.auto_forecast = False

# ── PLOTLY THEME ──
PLOT_LAYOUT = dict(
    paper_bgcolor="#ffffff", plot_bgcolor="#f8fafd",
    font=dict(family="IBM Plex Mono", color="#1a2233", size=11),
    xaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
    yaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor="#d0d9e8", borderwidth=1,
                font=dict(family="IBM Plex Mono", size=10))
)
def apply_theme(fig):
    fig.update_layout(**PLOT_LAYOUT); return fig

def add_threshold_line(fig, thr):
    fig.add_hline(y=thr, line_dash="dash", line_color="#ef4444", line_width=1.5,
                  annotation_text=f"Threshold {thr:.1f} m",
                  annotation_font=dict(color="#ef4444", size=10),
                  annotation_position="top left")
    return fig

# ════════════════════════════════
# VIEW 1 : LIVE
# ════════════════════════════════
if st.session_state.view == "live":
    st.markdown("### 📡 Water Level – Live Simulation (1 year)")
    sim_start = pd.Timestamp("2025-01-01")
    sim_end   = sim_start + pd.Timedelta(days=365)
    sim_df    = df[(df["date"] >= sim_start) & (df["date"] <= sim_end)].copy()

    col_chart, col_status = st.columns([3, 1])

    with col_status:
        st.markdown("#### System Status")
        pump_color = "#16a34a" if pump_on else "#dc2626"
        pump_text  = "RUNNING" if pump_on else "STOPPED"
        st.markdown(f"""
        <div class="status-block {'running' if pump_on else 'stopped'}">
            <div style="color:{pump_color};font-size:1.1rem;">● {pump_text}</div>
            <div style="color:#475569;margin-top:4px;">Level: {current_level:.2f} m</div>
            <div style="color:#475569;">Threshold: {threshold:.1f} m</div>
            <div style="color:#475569;">Mode: {mode}</div>
        </div>
        """, unsafe_allow_html=True)
        st.metric("Pump 1", "🟢 ON" if st.session_state.pump1 else "🔴 OFF")
        st.metric("Pump 2", "🟢 ON" if st.session_state.pump2 else "🔴 OFF")
        if st.session_state.control_log:
            st.markdown("**Last actions**")
            for entry in reversed(st.session_state.control_log[-4:]):
                st.markdown(
                    f'<div style="font-family:monospace;font-size:0.68rem;background:#f0f6ff;'
                    f'padding:5px 8px;border-radius:5px;margin:3px 0;border-left:3px solid #4a80f5;color:#1a2233;">'
                    f'{entry.get("time","")} {entry.get("action","")}</div>',
                    unsafe_allow_html=True
                )

    with col_chart:
        start_btn = st.button("▶️ Start Live Simulation", type="primary")
        chart_ph  = st.empty()

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
            state_log, cur_state, period_start = [], None, None

            for i, row in sim_df.iterrows():
                today, lvl = row["date"], row["niveau_nappe"]
                safe_now  = lvl > threshold
                dam_state = "Running" if (safe_now and any_pump_active) else "Stopped"

                st.session_state.live_stopped_at    = today
                st.session_state.live_stopped_level = float(lvl)

                if dam_state != cur_state:
                    if cur_state is not None:
                        state_log.append({
                            "Status": cur_state,
                            "From": period_start.strftime("%Y-%m-%d"),
                            "To":   (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                            "Days": (today - period_start).days,
                        })
                        log_ph.dataframe(pd.DataFrame(state_log), use_container_width=True)
                    cur_state, period_start = dam_state, today

                sub        = sim_df[sim_df["date"] <= today]
                color_line = "#22c55e" if dam_state == "Running" else "#ef4444"

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=sim_df["date"], y=sim_df["niveau_nappe"],
                    mode="lines", name="Full year",
                    line=dict(color="#c0c8d8", width=1.5), opacity=0.5))
                fig.add_trace(go.Scatter(x=sub["date"], y=sub["niveau_nappe"],
                    mode="lines", name="Simulation",
                    line=dict(color=color_line, width=2.5)))
                fig.add_trace(go.Scatter(
                    x=[today], y=[lvl], mode="markers+text",
                    marker=dict(size=10, color="#f59e0b", symbol="circle"),
                    text=[f"{lvl:.2f}m"], textposition="top center",
                    textfont=dict(color="#d97706", size=10), name="Now"))
                add_threshold_line(fig, threshold)
                fig.add_annotation(
                    x=today, y=1.05, xref="x", yref="paper",
                    text=f"📅 {today.strftime('%Y-%m-%d')} | {dam_state}",
                    showarrow=False,
                    font=dict(size=11, color="#d97706", family="IBM Plex Mono"),
                    bgcolor="rgba(255,255,255,0.85)", borderpad=4, xanchor="center"
                )
                apply_theme(fig)
                fig.update_layout(height=420, showlegend=True,
                                  xaxis=dict(range=[sim_df["date"].min(), sim_df["date"].max()]))
                chart_ph.plotly_chart(fig, use_container_width=True)
                time.sleep(1.0 / sim_speed)

            total_run  = sum(x["Days"] for x in state_log if x["Status"] == "Running")
            total_stop = sum(x["Days"] for x in state_log if x["Status"] == "Stopped")
            st.success(f"✅ Simulation complete — **{total_run} days running** / **{total_stop} days stopped**")

# ════════════════════════════════
# VIEW 2 : FORECASTING
# ════════════════════════════════
elif st.session_state.view == "forecast":
    st.markdown("### 📈 Forecasting – Scenario Analysis")

    last_hist_date = df["date"].max()
    fc_future = fc[fc["date"] > last_hist_date].copy()
    came_from_live = (st.session_state.live_stopped_at is not None)

    if came_from_live:
        stopped_date_str  = pd.Timestamp(st.session_state.live_stopped_at).strftime("%Y-%m-%d")
        stopped_level_val = st.session_state.live_stopped_level
        st.markdown(f"""
        <div style="background:#fffbeb;border:1px solid #f59e0b;border-left:5px solid #f59e0b;
                    border-radius:8px;padding:10px 16px;margin-bottom:12px;
                    font-family:'IBM Plex Mono',monospace;font-size:0.82rem;color:#92400e;">
            ⏸️ <strong>Live stopped at {stopped_date_str}</strong> — level {stopped_level_val:.2f} m
            &nbsp;|&nbsp; Forecast recalculated from this point ↓
        </div>
        """, unsafe_allow_html=True)

    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        scenario_choice = st.multiselect("Active Scenarios", ["dry", "medium", "wet"],
                                         default=["dry", "medium", "wet"])
    with fc2:
        add_stop_point = st.checkbox("➕ Add / update stop point", value=came_from_live)
    with fc3:
        if add_stop_point:
            default_date  = pd.Timestamp(st.session_state.live_stopped_at).date() if came_from_live else last_hist_date.date()
            default_level = st.session_state.live_stopped_level if came_from_live else float(df["niveau_nappe"].iloc[-1])
            extra_date    = st.date_input("Stop date", value=default_date)
            extra_level   = st.number_input("Level (m)", value=float(default_level), step=0.1)

    sc_colors = {"dry": "#94a3b8", "medium": "#f59e0b", "wet": "#34d399"}

    # ── Graphique haut : historique ──
    fig_top = go.Figure()
    fig_top.add_trace(go.Scatter(x=df["date"], y=df["niveau_nappe"],
        mode="lines", name="Historical", line=dict(color="#388bfd", width=2)))
    for sc in scenario_choice:
        sc_data = fc_future[fc_future["scenario"] == sc]
        if not sc_data.empty:
            fig_top.add_trace(go.Scatter(x=sc_data["date"], y=sc_data["niveau_nappe"],
                mode="lines", name=f"Forecast: {sc.capitalize()}",
                line=dict(color=sc_colors[sc], width=2, dash="dot"), opacity=0.9))
    if add_stop_point:
        extra_ts = pd.Timestamp(extra_date)
        fig_top.add_trace(go.Scatter(
            x=[extra_ts], y=[extra_level], mode="markers+text",
            marker=dict(size=14, color="#f43f5e", symbol="star"),
            text=[f" Stop {extra_level:.2f}m"], textposition="top right",
            textfont=dict(color="#f43f5e", size=10), name="Stop point"))
        fig_top.add_shape(type="line",
            x0=str(extra_ts.date()), x1=str(extra_ts.date()), y0=0, y1=1,
            xref="x", yref="paper", line=dict(color="#f43f5e", width=1, dash="dot"))
        fig_top.add_annotation(
            x=str(extra_ts.date()), y=1.02, xref="x", yref="paper",
            text="Stop → recalculated", showarrow=False,
            font=dict(color="#f43f5e", size=9), xanchor="left")
    add_threshold_line(fig_top, threshold)
    apply_theme(fig_top)
    fig_top.update_layout(height=320, title="Historical + Forecast Scenarios")
    st.plotly_chart(fig_top, use_container_width=True)

    # ── Graphique bas : forecast depuis stop ──
    st.markdown("#### 🔍 Forecast Detail Window")
    fig_bot = go.Figure()

    if add_stop_point:
        extra_ts = pd.Timestamp(extra_date)
        extra_lv = float(extra_level)
        recompute_dates = pd.date_range(start=extra_ts, periods=365, freq="D")
        n_pts = len(recompute_dates)
        rng   = np.random.default_rng(seed=42)

        for sc, annual_drift in [("dry", +0.8), ("medium", 0.0), ("wet", -0.6)]:
            if sc not in scenario_choice:
                continue
            t  = np.linspace(0, 1, n_pts)
            vals = extra_lv + annual_drift*t + 0.8*np.sin(2*np.pi*t) + np.cumsum(rng.normal(0,0.08,n_pts))*0.015
            bw   = 0.05 + 0.7*t
            dl   = list(recompute_dates)
            fig_bot.add_trace(go.Scatter(
                x=dl + dl[::-1], y=list(vals+bw) + list((vals-bw)[::-1]),
                fill="toself", fillcolor=sc_colors[sc],
                opacity=0.15, line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig_bot.add_trace(go.Scatter(
                x=recompute_dates, y=vals,
                mode="lines", name=sc.capitalize(),
                line=dict(color=sc_colors[sc], width=2.5)))

        fig_bot.add_trace(go.Scatter(
            x=[extra_ts], y=[extra_lv], mode="markers+text",
            marker=dict(size=14, color="#f43f5e", symbol="star"),
            text=[f"  {extra_lv:.2f} m"], textposition="middle right",
            textfont=dict(color="#f43f5e", size=11, family="IBM Plex Mono"),
            name="Stop point"))
        fig_bot.add_shape(type="line",
            x0=str(extra_ts.date()), x1=str(extra_ts.date()), y0=0, y1=1,
            xref="x", yref="paper", line=dict(color="#f43f5e", width=1.5, dash="dot"))
        fig_bot.add_annotation(
            x=str(extra_ts.date()), y=1.04, xref="x", yref="paper",
            text="▶ Forecast from stop", showarrow=False,
            font=dict(color="#f43f5e", size=10, family="IBM Plex Mono"), xanchor="left")
        fig_bot.update_xaxes(range=[str(extra_ts.date()), str(recompute_dates[-1].date())])
        fig_bot.update_layout(height=350, title="Forecast from Stop Point (1 year horizon)")
    else:
        if not fc_future.empty:
            for sc in scenario_choice:
                sc_data = fc_future[fc_future["scenario"] == sc].copy().sort_values("date")
                if not sc_data.empty:
                    dl = list(sc_data["date"]); vl = list(sc_data["niveau_nappe"])
                    fig_bot.add_trace(go.Scatter(
                        x=dl+dl[::-1], y=[v+0.4 for v in vl]+[v-0.4 for v in vl[::-1]],
                        fill="toself", fillcolor=sc_colors[sc],
                        opacity=0.12, line=dict(width=0), showlegend=False))
                    fig_bot.add_trace(go.Scatter(
                        x=sc_data["date"], y=sc_data["niveau_nappe"],
                        mode="lines", name=sc.capitalize(),
                        line=dict(color=sc_colors[sc], width=2)))
        else:
            st.info("Run the live simulation and press Stop to generate a forecast from that point.")
        fig_bot.update_layout(height=350, title="Forecast Scenarios (from end of history)")

    add_threshold_line(fig_bot, threshold)
    apply_theme(fig_bot)
    st.plotly_chart(fig_bot, use_container_width=True)

    if not fc_future.empty:
        st.markdown("#### 📊 End-of-Period Forecast Summary")
        mc1, mc2, mc3 = st.columns(3)
        for col_m, sc in zip([mc1, mc2, mc3], ["dry", "medium", "wet"]):
            sc_end = fc_future[fc_future["scenario"] == sc]
            if not sc_end.empty:
                val = sc_end["niveau_nappe"].iloc[-1]
                col_m.metric(f"{sc.capitalize()} Scenario", f"{val:.2f} m",
                             delta=f"{val - current_level:+.2f} m vs now")

# ════════════════════════════════
# VIEW 3 : HISTORY
# ════════════════════════════════
elif st.session_state.view == "history":
    st.markdown("### 📋 Full Historical Record")
    h1, h2 = st.columns([3, 1])

    with h1:
        date_range = st.date_input("Date range",
            value=[df["date"].min().date(), df["date"].max().date()],
            min_value=df["date"].min().date(), max_value=df["date"].max().date())
        filtered = df[
            (df["date"] >= pd.Timestamp(date_range[0])) &
            (df["date"] <= pd.Timestamp(date_range[1]))
        ] if len(date_range) == 2 else df.copy()

        fig_hist = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                 row_heights=[0.7, 0.3],
                                 subplot_titles=["Water Level (m)", "Rainfall (mm)"])
        fig_hist.add_trace(go.Scatter(
            x=filtered["date"], y=filtered["niveau_nappe"],
            mode="lines", name="Water Level", line=dict(color="#388bfd", width=1.8)
        ), row=1, col=1)
        fig_hist.add_hline(y=threshold, line_dash="dash", line_color="#ef4444",
                           annotation_text="Threshold", annotation_position="top left",
                           row=1, col=1)
        if "pluie_mm" in filtered.columns:
            fig_hist.add_trace(go.Bar(
                x=filtered["date"], y=filtered["pluie_mm"],
                name="Rainfall", marker_color="#34d399", opacity=0.6
            ), row=2, col=1)
        fig_hist.update_layout(height=500,
            **{k: v for k, v in PLOT_LAYOUT.items() if k not in ("xaxis","yaxis")})
        fig_hist.update_xaxes(gridcolor="#e2e8f0", linecolor="#cbd5e1")
        fig_hist.update_yaxes(gridcolor="#e2e8f0", linecolor="#cbd5e1")
        st.plotly_chart(fig_hist, use_container_width=True)

    with h2:
        st.markdown("#### 📊 Stats")
        if not filtered.empty:
            st.metric("Min Level",  f"{filtered['niveau_nappe'].min():.2f} m")
            st.metric("Max Level",  f"{filtered['niveau_nappe'].max():.2f} m")
            st.metric("Mean Level", f"{filtered['niveau_nappe'].mean():.2f} m")
            days_below = (filtered["niveau_nappe"] < threshold).sum()
            st.metric("Days below threshold", f"{days_below} d")
            st.metric("% time critical", f"{days_below/len(filtered)*100:.1f}%")
        st.markdown("---")
        st.markdown("#### 📥 Export")
        st.download_button("⬇️ Download CSV", data=filtered.to_csv(index=False),
                           file_name="groundwater_history.csv", mime="text/csv",
                           use_container_width=True)

    if st.session_state.control_log:
        st.markdown("#### 📋 Control Action Log")
        log_df = pd.DataFrame(st.session_state.control_log)
        st.dataframe(log_df[::-1], use_container_width=True)
        st.download_button("⬇️ Export Action Log", data=log_df.to_csv(index=False),
                           file_name="action_log.csv", mime="text/csv")
    else:
        st.info("No control actions recorded yet.")
