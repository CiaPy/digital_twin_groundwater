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
    padding: 8px 18px;
    border-radius: 6px;
    display: inline-block;
}
.pump-on  { background: #0f7a35; color: #86efac; border: 1px solid #22c55e; }
.pump-off { background: #7c1d1d; color: #fca5a5; border: 1px solid #ef4444; }
.dots-nav { display: flex; gap: 14px; align-items: center; }
.dot-nav {
    width: 16px; height: 16px;
    border-radius: 50%;
    background: #d0d9e8;
    border: 2px solid #4a80f5;
    cursor: pointer;
    transition: background 0.2s;
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
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── SIDEBAR ──
with st.sidebar:
    st.markdown("### ⚙️ Control Panel")
    st.markdown("---")
    threshold = st.number_input("🎯 Critical Threshold (m)", value=114.2, step=0.1, format="%.1f")
    sim_speed = st.slider("⚡ Simulation Speed (days/s)", 0.1, 10, 1)
    st.markdown("---")
    st.markdown("### 🗺️ Site Overview")
    from pathlib import Path
    img_path = Path(__file__).parent / "site_overview(1).png"
    if img_path.exists():
        st.image(str(img_path), use_container_width=True)

    st.markdown("---")
    st.markdown("### 📄 Automatic Report")
    if st.button("📥 Generate PDF Report", use_container_width=True):
        with st.spinner("Building report — rendering charts..."):
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from pdf_report import generate_pdf_report
            pdf_bytes = generate_pdf_report(
                df=df,
                fc=fc,
                threshold=threshold,
                pump1=st.session_state.pump1,
                pump2=st.session_state.pump2,
                mode="Automatic",
                control_log=st.session_state.control_log,
                live_stopped_at=st.session_state.live_stopped_at,
                live_stopped_level=st.session_state.live_stopped_level,
            )
        st.download_button(
            label="⬇️ Download PDF Report",
            data=pdf_bytes,
            file_name=f"groundwater_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# ── CURRENT STATE ──
current_level   = float(df["niveau_nappe"].iloc[-1])
current_date    = df["date"].iloc[-1]
is_safe         = current_level > threshold
any_pump_active = st.session_state.pump1 or st.session_state.pump2
mode = "Automatic"
pump_on         = (is_safe and any_pump_active)

if not any_pump_active:
    pump_html_cls, pump_html_txt = "pump-off", "ALL PUMPS OFF"
elif st.session_state.pump1 and st.session_state.pump2:
    pump_html_cls = "pump-on" if pump_on else "pump-off"
    pump_html_txt = "PUMP 1 + 2 ON" if pump_on else "PUMP 1 + 2 – STOPPED"
elif st.session_state.pump1:
    pump_html_cls = "pump-on" if pump_on else "pump-off"
    pump_html_txt = "PUMP 1 ON" if pump_on else "PUMP 1 – STOPPED"
else:
    pump_html_cls = "pump-on" if pump_on else "pump-off"
    pump_html_txt = "PUMP 2 ON" if pump_on else "PUMP 2 – STOPPED"

display_date  = pd.Timestamp(st.session_state.live_stopped_at) if st.session_state.live_stopped_at else current_date
display_level = st.session_state.live_stopped_level if st.session_state.live_stopped_level else current_level

if display_level > threshold:
    level_color_badge  = "#0f7a35"
    level_border_badge = "#22c55e"
    level_text_badge   = "#86efac"
else:
    level_color_badge  = "#7c1d1d"
    level_border_badge = "#ef4444"
    level_text_badge   = "#fca5a5"

# ── TITLE ──
st.markdown("# 💧 Synthetic Digital Twin for Groundwater Extraction and Monitoring")
st.markdown("---")

# ── NAV BUTTONS ──
nav1, nav2, nav3 = st.columns(3)
with nav1:
    if st.button("📡 Live", use_container_width=True,
                 type="primary" if st.session_state.view == "live" else "secondary"):
        st.session_state.view = "live"
        st.rerun()
with nav2:
    if st.button("📈 Forecasting", use_container_width=True,
                 type="primary" if st.session_state.view == "forecast" else "secondary"):
        st.session_state.view = "forecast"
        st.rerun()
with nav3:
    if st.button("📋 History", use_container_width=True,
                 type="primary" if st.session_state.view == "history" else "secondary"):
        st.session_state.view = "history"
        st.rerun()

st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

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
    fig.update_layout(**PLOT_LAYOUT)
    return fig

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
    sim_start = pd.Timestamp("2025-06-01")
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
            <div style="color:#475569;">Mode: Automatic</div>
        </div>
        """, unsafe_allow_html=True)
        
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
        chart_ph  = st.empty()
        
        # Conteneurs pour les boutons (définis une seule fois)
        sb1, sb2, sb3 = st.columns([1, 1, 1])
        
        # Placeholder pour le log (sous les boutons)
        log_ph    = st.empty()
        
        # Variables pour tracker l'état des boutons
        start_btn = False
        stop_btn = False

        # Graph figé au point de stop
        if st.session_state.live_stopped_at:
            stopped_ts  = pd.Timestamp(st.session_state.live_stopped_at)
            stopped_lvl = st.session_state.live_stopped_level
            sub_stopped = sim_df[sim_df["date"] <= stopped_ts]
            color_stopped = "#22c55e" if (stopped_lvl > threshold and any_pump_active) else "#ef4444"

            fig_frozen = go.Figure()
            fig_frozen.add_trace(go.Scatter(
                x=sim_df["date"], y=sim_df["niveau_nappe"],
                mode="lines", name="Full year",
                line=dict(color="#c0c8d8", width=1.5), opacity=0.5))
            fig_frozen.add_trace(go.Scatter(
                x=sub_stopped["date"], y=sub_stopped["niveau_nappe"],
                mode="lines", name="Simulation",
                line=dict(color=color_stopped, width=2.5)))
            fig_frozen.add_trace(go.Scatter(
                x=[stopped_ts], y=[stopped_lvl], mode="markers+text",
                marker=dict(size=12, color="#f59e0b", symbol="circle"),
                text=[f"{stopped_lvl:.2f}m"], textposition="top center",
                textfont=dict(color="#d97706", size=10), name="Stop point"))
            add_threshold_line(fig_frozen, threshold)
            fig_frozen.add_annotation(
                x=stopped_ts, y=1.05, xref="x", yref="paper",
                text=f"⏸ STOPPED — {stopped_ts.strftime('%Y-%m-%d')} | Level {stopped_lvl:.2f} m",
                showarrow=False,
                font=dict(size=11, color="#d97706", family="IBM Plex Mono"),
                bgcolor="rgba(255,255,255,0.85)", borderpad=4, xanchor="center"
            )
            apply_theme(fig_frozen)
            fig_frozen.update_layout(
                height=420, uirevision="frozen",
                title=" ",
                xaxis=dict(range=[sim_df["date"].min(), sim_df["date"].max()])
            )
            chart_ph.plotly_chart(fig_frozen, use_container_width=True,
                                  config={"displayModeBar": False})
            
            with sb2:
                if st.button("■ Reset & Start", use_container_width=True, type="primary"):
                    st.session_state.sim_running = True
                    st.session_state.live_stopped_at = None
                    st.session_state.live_stopped_level = None
                    st.session_state.control_log.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "action": "Live START",
                        "pumps": f"P1={'ON' if st.session_state.pump1 else 'OFF'} P2={'ON' if st.session_state.pump2 else 'OFF'}",
                        "level": float(df["niveau_nappe"].iloc[-1])
                    })
                    st.rerun()

        else:
            # Graph statique par défaut - créé UNE SEULE FOIS et réutilisé
            if "fig_base" not in st.session_state:
                st.session_state.fig_base = go.Figure()
                st.session_state.fig_base.add_trace(go.Scatter(
                    x=sim_df["date"], y=sim_df["niveau_nappe"],
                    mode="lines", name="Historical",
                    line=dict(color="#388bfd", width=2), opacity=0.6
                ))
                add_threshold_line(st.session_state.fig_base, threshold)
                apply_theme(st.session_state.fig_base)
                st.session_state.fig_base.update_layout(
                    height=420, 
                    uirevision="water_level_2025",  # Clé fixe pour ne jamais reset
                    title="Water Level 2025",
                    xaxis=dict(range=[sim_df["date"].min(), sim_df["date"].max()])
                )
            
            fig_static = st.session_state.fig_base
            chart_ph.plotly_chart(fig_static, use_container_width=True,
                                  config={"displayModeBar": False, "responsive": False})

            # ── BOUTONS DE CONTRÔLE (FIXES SOUS LE GRAPHIQUE) ──
            with sb1:
                pass  # Colonne vide pour l'espacement
            with sb2:
                start_btn = st.button("▶️ Start", use_container_width=True, type="primary")
            with sb3:
                stop_btn = st.button("■ Stop", use_container_width=True)

            if start_btn and not sim_df.empty:
                # Copier le graphique de base et ajouter les traces d'animation
                fig_live = st.session_state.fig_base.to_dict()  # Copier la config de base
                fig_live = go.Figure(fig_live)
                
                # Ajouter les deux traces qui vont être animées
                # Trace 1 : Simulation (sera mise à jour)
                fig_live.add_trace(go.Scatter(
                    x=[], y=[],
                    mode="lines", name="Simulation",
                    line=dict(color="#22c55e", width=2.5)
                ))
                
                # Trace 2 : Stop point (sera mise à jour)
                fig_live.add_trace(go.Scatter(
                    x=[], y=[],
                    mode="markers+text",
                    marker=dict(size=10, color="#f59e0b", symbol="circle"),
                    textposition="top center",
                    textfont=dict(color="#d97706", size=10),
                    name="Now"
                ))
                
                fig_live.update_layout(
                    uirevision="water_level_animation",  # Clé pour animation fluide
                    xaxis=dict(range=[sim_df["date"].min(), sim_df["date"].max()])
                )
                
                # Afficher le graphique UNE SEULE FOIS
                chart_ph.plotly_chart(
                    fig_live,
                    use_container_width=True,
                    config={"displayModeBar": False, "responsive": False}
                )

                # Initialiser l'état de l'animation
                if "live_animation" not in st.session_state:
                    st.session_state.live_animation = {
                        "running": True,
                        "state_log": [],
                        "cur_state": None,
                        "period_start": None,
                    }
                
                state_log = st.session_state.live_animation["state_log"]
                cur_state = st.session_state.live_animation["cur_state"]
                period_start = st.session_state.live_animation["period_start"]
                
                # Boucle d'animation : UNIQUEMENT mettre à jour les deux traces
                for idx, (i, row) in enumerate(sim_df.iterrows()):
                    if not st.session_state.live_animation["running"]:
                        break
                    
                    if stop_btn:
                        st.session_state.live_animation["running"] = False
                        st.session_state.control_log.append({
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "action": "Live STOP → Forecast ready",
                            "pumps": f"P1={'ON' if st.session_state.pump1 else 'OFF'} P2={'ON' if st.session_state.pump2 else 'OFF'}",
                            "level": st.session_state.live_stopped_level
                        })
                        st.info(f"⏸️ Simulation stopped at {st.session_state.live_stopped_at.strftime('%Y-%m-%d')} | Level {st.session_state.live_stopped_level:.2f} m")
                        break
                    
                    today, lvl = row["date"], row["niveau_nappe"]
                    safe_now = lvl > threshold
                    dam_state = "Running" if (safe_now and any_pump_active) else "Stopped"
                    color_line = "#22c55e" if dam_state == "Running" else "#ef4444"

                    st.session_state.live_stopped_at = today
                    st.session_state.live_stopped_level = float(lvl)

                    # Tracker les changements d'état
                    if dam_state != cur_state:
                        if cur_state is not None:
                            state_log.append({
                                "Status": cur_state,
                                "From": period_start.strftime("%Y-%m-%d"),
                                "To": (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                                "Days": (today - period_start).days,
                            })
                        cur_state, period_start = dam_state, today
                        st.session_state.live_animation["cur_state"] = cur_state
                        st.session_state.live_animation["period_start"] = period_start

                    # UNIQUEMENT mettre à jour les deux traces d'animation
                    sub = sim_df[sim_df["date"] <= today]
                    
                    # Trace 1 : Simulation
                    fig_live.data[-2].x = sub["date"]
                    fig_live.data[-2].y = sub["niveau_nappe"]
                    fig_live.data[-2].line.color = color_line
                    
                    # Trace 2 : Stop point
                    fig_live.data[-1].x = [today]
                    fig_live.data[-1].y = [lvl]
                    fig_live.data[-1].text = [f"{lvl:.2f}m"]

                    # Mettre à jour annotation date uniquement
                    new_annotations = []
                    for ann in fig_live.layout.annotations:
                        if "Threshold" in str(ann.text) or "📅" not in str(ann.text):
                            new_annotations.append(ann)
                    
                    new_annotations.append(go.layout.Annotation(
                        x=today, y=1.05, xref="x", yref="paper",
                        text=f"📅 {today.strftime('%Y-%m-%d')} | {dam_state}",
                        showarrow=False,
                        font=dict(size=11, color="#d97706", family="IBM Plex Mono"),
                        bgcolor="rgba(255,255,255,0.85)", borderpad=4, xanchor="center"
                    ))
                    fig_live.layout.annotations = new_annotations

                    # Redessiner UNIQUEMENT tous les N itérations
                    if idx % max(1, len(sim_df) // 60) == 0 or idx == len(sim_df) - 1:
                        chart_ph.plotly_chart(
                            fig_live,
                            use_container_width=True,
                            config={"displayModeBar": False, "responsive": False}
                        )
                        
                        if state_log:
                            log_ph.dataframe(pd.DataFrame(state_log), use_container_width=True)
                    
                    time.sleep(0.03 / sim_speed)  # Tempo très court

                # Affichage final
                chart_ph.plotly_chart(
                    fig_live,
                    use_container_width=True,
                    config={"displayModeBar": False, "responsive": False}
                )
                
                total_run = sum(x["Days"] for x in state_log if x["Status"] == "Running")
                total_stop = sum(x["Days"] for x in state_log if x["Status"] == "Stopped")
                st.success(f"✅ Simulation complete — **{total_run} days running** / **{total_stop} days stopped**")

# ════════════════════════════════
# VIEW 2 : FORECASTING
# ════════════════════════════════
elif st.session_state.view == "forecast":
    st.markdown("### 📈 Forecasting – Scenario Analysis")

    last_hist_date = df["date"].max()
    fc_future      = fc[fc["date"] > last_hist_date].copy()
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

    fc1, fc2 = st.columns([2, 1])
    with fc1:
        scenario_choice = st.multiselect("Active Scenarios", ["dry", "medium", "wet"],
                                         default=["dry", "medium", "wet"])

    sc_colors = {"dry": "#94a3b8", "medium": "#f59e0b", "wet": "#34d399"}

    st.markdown("#### 🔍 Forecast Detail Window")
    fig_bot = go.Figure()

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
    
    fig_bot.update_layout(height=400, title="Forecast Scenarios (from end of history)")

    add_threshold_line(fig_bot, threshold)
    apply_theme(fig_bot)
    st.plotly_chart(fig_bot, use_container_width=True)



# ════════════════════════════════
# VIEW 3 : HISTORY
# ════════════════════════════════
elif st.session_state.view == "history":
    st.markdown("### 📋 Full Historical Record")
    h1, h2 = st.columns([3, 1])

    hist_max = (
        pd.Timestamp(st.session_state.live_stopped_at).date()
        if st.session_state.live_stopped_at
        else df["date"].max().date()
    )

    with h1:
        date_range = st.date_input(
            "Date range",
            value=[df["date"].min().date(), hist_max],
            min_value=df["date"].min().date(),
            max_value=df["date"].max().date()
        )
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

        if st.session_state.live_stopped_at:
            stop_ts  = pd.Timestamp(st.session_state.live_stopped_at)
            stop_lvl = st.session_state.live_stopped_level
            fig_hist.add_trace(go.Scatter(
                x=[stop_ts], y=[stop_lvl], mode="markers+text",
                marker=dict(size=12, color="#f43f5e", symbol="star"),
                text=[f"  Stop {stop_lvl:.2f}m"], textposition="top right",
                textfont=dict(color="#f43f5e", size=10), name="Stop point"
            ), row=1, col=1)

        if "pluie_mm" in filtered.columns:
            fig_hist.add_trace(go.Bar(
                x=filtered["date"], y=filtered["pluie_mm"],
                name="Rainfall", marker_color="#34d399", opacity=0.6
            ), row=2, col=1)

        fig_hist.update_layout(
            height=500,
            **{k: v for k, v in PLOT_LAYOUT.items() if k not in ("xaxis", "yaxis")}
        )
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
