import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# Page configuration
st.set_page_config(page_title="Synthetic Digital Twin for Groundwater Extraction and Monitoring", layout="wide")

# Custom CSS for status indicators
st.markdown("""
<style>
/* Status cards */
.status-card {
    padding: 12px;
    border-radius: 10px;
    margin: 10px 0;
    font-weight: bold;
    color: white;
    display: flex;
    align-items: center;
    gap: 10px;
    border-left: 5px solid #000;
}
.status-safe {
    background: #0f7a35;
    border-left-color: #22c55e;
}
.status-alert {
    background: #8a1a1a;
    border-left-color: #ef4444;
}
.status-running {
    background: #164e63;
    border-left-color: #0ea5e9;
}
.status-stopped {
    background: #7c2d12;
    border-left-color: #ea580c;
}
.dot {
    width: 12px; height: 12px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
}
.dot-green { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
.dot-red { background: #ef4444; box-shadow: 0 0 6px #ef4444; }
.dot-blue { background: #0ea5e9; box-shadow: 0 0 6px #0ea5e9; }
</style>
""", unsafe_allow_html=True)

# Main title
st.title("🌊 Synthetic Digital Twin for Groundwater Extraction and Monitoring")

# Info columns
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("""
    **Simulated Components**
    - Piezometer: water level measurement
    - Control Center: manual/automatic decision
    - Dam: extraction enabled/disabled
    """)

with col2:
    st.caption("""
    **Features**
    - Automatic mode: stops if critical threshold
    - Manual mode: direct control
    - State history
    """)

with col3:
    st.caption("""
    **Data Sources**
    - Historical water level: Hub'Eau
    - Scenarios: linear regression
    """)

# --- Data loading (unchanged) ---
@st.cache_data
def load_hist():
    try:
        df = pd.read_csv("data/processed/dataset_daily.csv")
        df["date"] = pd.to_datetime(df["date"])
        return df
    except:
        return None

@st.cache_data
def load_forecast():
    try:
        fc = pd.read_csv("data/processed/forecast_scenarios.csv")
        fc["date"] = pd.to_datetime(fc["date"])
        return fc
    except:
        return None

# Load or simulate data
df = load_hist()
fc = load_forecast()

if df is None or fc is None:
    st.warning("Real data not found. Generating simulated data.")
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="D")
    n = len(dates)
    np = 115 + 10 * np.sin(np.arange(n) * 0.05) + np.random.normal(0, 0.5, n)
    df = pd.DataFrame({
        "date": dates,
        "niveau_nappe": np,
        "pluie_mm": np.random.exponential(5, n),
        "etp_mm": np.random.exponential(3, n)
    })
    scenarios = ["dry", "medium", "wet"]
    fc_list = []
    for sc in scenarios:
        fc_sc = pd.DataFrame({
            "date": dates[-365:],
            "scenario": sc,
            "niveau_nappe": np[-365:] + (1 if sc == "dry" else (-1 if sc == "wet" else 0))
        })
        fc_list.append(fc_sc)
    fc = pd.concat(fc_list)

# === Generate dam history ===
def generate_dam_history(df, threshold, start_date=None):
    if start_date is None:
        start_date = df["date"].max() - pd.Timedelta(days=30)
    history = df[df["date"] >= start_date].copy()
    history["dam_status"] = "Stopped"
    history.loc[history["niveau_nappe"] > (threshold - 0.5), "dam_status"] = "Running"
    return history

if "dam_history" not in st.session_state:
    st.session_state.dam_history = generate_dam_history(df, threshold=114.2)

# --- Session state ---
if "dam_status" not in st.session_state:
    st.session_state.dam_status = "Running"
if "control_mode" not in st.session_state:
    st.session_state.control_mode = "Automatic"
if "alert_history" not in st.session_state:
    st.session_state.alert_history = []
if "control_log" not in st.session_state:
    st.session_state.control_log = []

# --- Sidebar: Control Center ---
st.sidebar.header("🏛️ Control Center")
mode = st.sidebar.radio("Operation Mode", ["Automatic", "Manual"], index=0 if st.session_state.control_mode == "Automatic" else 1)
st.session_state.control_mode = mode

threshold = st.sidebar.number_input("Critical threshold (m)", value=114.2, step=0.1)
st.sidebar.markdown("---")

# Manual controls
if mode == "Manual":
    col_start, col_stop = st.sidebar.columns(2)
    if col_start.button("🟢 Start"):
        st.session_state.dam_status = "Running"
        st.session_state.control_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "Manual start",
            "level": float(df["niveau_nappe"].iloc[-1])
        })
    if col_stop.button("🔴 Stop"):
        st.session_state.dam_status = "Stopped"
        st.session_state.control_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "Manual stop",
            "level": float(df["niveau_nappe"].iloc[-1])
        })

# --- Current data ---
current_level = float(df["niveau_nappe"].iloc[-1])
is_safe = current_level > threshold

# --- Automatic logic ---
if mode == "Automatic":
    if is_safe and st.session_state.dam_status != "Running":
        st.session_state.dam_status = "Running"
        st.session_state.control_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "Start (safe level)",
            "level": current_level
        })
    elif not is_safe and st.session_state.dam_status != "Stopped":
        st.session_state.dam_status = "Stopped"
        st.session_state.control_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "Stop (critical level)",
            "level": current_level
        })

# --- Main display ---
tab1, tab2, tab3 = st.tabs(["📊 Supervision", "📈 History", "▶️ Live"])

with tab1:
    # Colonnes
    col_param, col_graph, col_control = st.columns([1, 2, 1])

    with col_param:
        st.markdown("## 📡 Real-Time Data")

        # Niveau d'eau
        st.markdown(f"""
        <div class="status-card {'status-safe' if is_safe else 'status-alert'}">
            <span class="dot {'dot-green' if is_safe else 'dot-red'}"></span>
            <strong>Water Level:</strong> {current_level:.2f} m
        </div>
        """, unsafe_allow_html=True)

        # Mode de contrôle
        mode_color = "status-running" if mode == "Automatic" else "status-alert"
        dot_mode = "dot-green" if mode == "Automatic" else "dot-red"
        st.markdown(f"""
        <div class="status-card {mode_color}">
            <span class="dot {dot_mode}"></span>
            <strong>Mode:</strong> {mode}
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📊 Current Mode")
        if mode == "Automatic":
            st.info("🔁 Automatic mode: Decisions based on water level")
        else:
            st.warning(">manual mode: Manual control active")

        # Résumé des scénarios (prévision finale)
        try:
            forecast_end = fc.groupby("scenario").last()
            dry_level = forecast_end.loc["dry", "niveau_nappe"]
            wet_level = forecast_end.loc["wet", "niveau_nappe"]

            st.markdown("### 📈 1-Year Forecast Summary")
            st.metric("Dry Scenario", f"{dry_level:.2f} m")
            st.metric("Wet Scenario", f"{wet_level:.2f} m")
            st.caption("Based on forecast_scenarios.csv")
        except:
            st.info("Forecast data not available")

        with col_graph:
            st.subheader("📊 Water Level: Historical & Forecast (What-If Scenarios)")
    
            # --- Préparer les données combinées ---
            # Historique
            hist = df[["date", "niveau_nappe"]].copy()
            hist["type"] = "Historical"
    
            # Prévisions (scénarios)
            forecast_horizon = fc[fc["date"] > df["date"].max()].copy()
            forecast_horizon = forecast_horizon[forecast_horizon["date"] <= pd.Timestamp("2025-01-01") + pd.Timedelta(days=365)]
            forecast_wide = forecast_horizon.pivot(index="date", columns="scenario", values="niveau_nappe").reset_index()
    
            # Fusionner historique + prévisions
            combined = pd.merge(hist, forecast_wide[["date"]], on="date", how="outer", indicator=True)
            combined["date"] = pd.to_datetime(combined["date"])
            combined = combined.sort_values("date")
    
            # --- Créer le graphique ---
            fig = go.Figure()
    
            # 1. Historique (bleu)
            fig.add_trace(go.Scatter(
                x=hist["date"],
                y=hist["niveau_nappe"],
                mode="lines",
                name="Historical",
                line=dict(color="blue", width=2),
                opacity=0.8
            ))
    
            # 2. Scénarios de prévision
            colors = {"dry": "red", "medium": "orange", "wet": "green"}
            for scenario in ["dry", "medium", "wet"]:
                if scenario in forecast_wide.columns:
                    fc_data = forecast_wide[["date", scenario]].dropna()
                    fig.add_trace(go.Scatter(
                        x=fc_data["date"],
                        y=fc_data[scenario],
                        mode="lines",
                        name=f"Forecast: {scenario.capitalize()}",
                        line=dict(color=colors[scenario], width=2, dash="dot" if scenario != "medium" else "solid"),
                        opacity=0.9
                    ))
    
            # 3. Ligne de tendance globale (régression linéaire sur l'historique + scénario medium)
            # On combine l'historique + medium pour la tendance
            trend_data = pd.concat([
                hist[["date", "niveau_nappe"]],
                forecast_wide[["date", "medium"]].rename(columns={"medium": "niveau_nappe"})
            ]).dropna().sort_values("date")
    
            # Régression linéaire (simple)
            from scipy import stats
            trend_x = trend_data["date"].map(pd.Timestamp.toordinal)
            slope, intercept, r_value, p_value, std_err = stats.linregress(trend_x, trend_data["niveau_nappe"])
            trend_y = [slope * x + intercept for x in trend_x]
    
            fig.add_trace(go.Scatter(
                x=trend_data["date"],
                y=trend_y,
                mode="lines",
                name="Trend (Linear Regression)",
                line=dict(color="purple", width=2, dash="dash"),
                opacity=0.7
            ))
    
            # 4. Seuil critique
            fig.add_hline(
                y=threshold,
                line_dash="dash",
                line_color="red",
                annotation_text="Critical Threshold",
                annotation_position="top left"
            )
    
            # --- Mise en page ---
            fig.update_layout(
                height=500,
                xaxis_title="Date",
                yaxis_title="Water Level (m)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=40, b=20)
            )
    
            st.plotly_chart(fig, use_container_width=True)


    with col_control:
        st.markdown("## 📋 Action Log")
        if st.session_state.control_log:
            log_df = pd.DataFrame(st.session_state.control_log[-10:])
            st.dataframe(log_df[::-1], use_container_width=True, height=400)
        else:
            st.info("No actions recorded.")


with tab2:
    st.subheader("📋 State History")

    if st.session_state.control_log:
        full_log = pd.DataFrame(st.session_state.control_log)
        st.dataframe(full_log, use_container_width=True)
    else:
        st.info("No events to display.")

    st.download_button(
        "📥 Export log",
        data=pd.DataFrame(st.session_state.control_log).to_csv(index=False),
        file_name="dam_control_log.csv",
        mime="text/csv"
    )

with tab3:
    st.subheader("🎥 Real-Time Simulation (1 year)")

    sim_threshold = st.number_input("Critical threshold (m)", value=114.2, step=0.1, key="sim_threshold_live")
    sim_speed = st.slider("Simulation speed (days/second)", 1, 30, 10, key="sim_speed_live")
    sim_start_date = pd.Timestamp("2025-01-01")

    if st.button("▶️ Start Simulation"):
        start_date = sim_start_date
        end_date = start_date + pd.Timedelta(days=365)
        sim_dates = pd.date_range(start_date, end_date, freq="D")
        current_df = df[df["date"] >= start_date].copy()
        current_df = current_df[current_df["date"] <= end_date]
        current_df = current_df.sort_values("date")

        # --- Initialisation ---
        placeholder = st.empty()  # Pour le graphique et l'état
        log_placeholder = st.empty()  # Pour le tableau qui se met à jour en temps réel

        simulation_log = []
        current_state = None
        period_start = None

        # --- Boucle de simulation ---
        for i, current_date in enumerate(sim_dates):
            sub_df = current_df[current_df["date"] <= current_date]
            if sub_df.empty:
                continue
            current_level = float(sub_df["niveau_nappe"].iloc[-1])
            is_safe = current_level > sim_threshold
            dam_state = "Running" if is_safe else "Stopped"

            # --- Gestion des transitions d'état ---
            if dam_state != current_state:
                if current_state is not None:
                    # Fin de la période précédente
                    new_entry = {
                        "Status": current_state,
                        "Start": period_start.strftime("%Y-%m-%d"),
                        "End": (current_date - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                        "Duration (days)": (current_date - period_start).days,
                        "Threshold (m)": sim_threshold,
                        "Average Level (m)": round(sub_df["niveau_nappe"].tail(len(sub_df) - len(sub_df[sub_df["date"] < period_start])).mean(), 2)
                    }
                    simulation_log.append(new_entry)

                    # --- Mise à jour IMMÉDIATE du tableau ---
                    log_df = pd.DataFrame(simulation_log)
                    with log_placeholder.container():
                        st.markdown("### 📊 State Transition History")
                        st.dataframe(log_df, use_container_width=True)

                # Nouvelle période
                current_state = dam_state
                period_start = current_date

            # --- Affichage dynamique ---
            with placeholder.container():
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown("### Water Level Evolution")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=current_df["date"],
                        y=current_df["niveau_nappe"],
                        mode="lines",
                        name="Historical",
                        line=dict(color="lightgray", width=2),
                        opacity=0.5
                    ))
                    fig.add_trace(go.Scatter(
                        x=sub_df["date"],
                        y=sub_df["niveau_nappe"],
                        mode="lines",
                        name="Simulation",
                        line=dict(color="blue", width=2)
                    ))
                    fig.add_hline(
                        y=sim_threshold,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"Threshold: {sim_threshold} m",
                        annotation_position="top left"
                    )
                    fig.add_shape(
                        type="line",
                        x0=current_date,
                        x1=current_date,
                        y0=0,
                        y1=1,
                        xref="x",
                        yref="paper",
                        line=dict(color="orange", width=3)
                    )
                    fig.add_annotation(
                        x=current_date,
                        y=1.02,
                        xref="x",
                        yref="paper",
                        text=f"Day: {current_date.strftime('%Y-%m-%d')}",
                        showarrow=False,
                        font=dict(size=12, color="orange"),
                        bgcolor="rgba(0,0,0,0.6)",
                        borderpad=4,
                        xanchor="center"
                    )
                    fig.update_layout(
                        height=500,
                        xaxis_title="Date",
                        yaxis_title="Level (m)",
                        margin=dict(l=20, r=20, t=60, b=20),
                        xaxis=dict(type="date")
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    st.markdown("### System Status")
                    color = "green" if dam_state == "Running" else "red"
                    st.markdown(f"""
                    <div style="padding:15px; border-radius:10px; background-color: #1a1a1a; color: white; margin: 10px 0;">
                        <strong>📅 Date:</strong> {current_date.strftime('%Y-%m-%d')}<br>
                        <strong>💧 Level:</strong> {current_level:.2f} m<br>
                        <strong>🎯 Threshold:</strong> {sim_threshold} m<br>
                        <strong>🔴 Dam:</strong> 
                        <span style="color: {color}; font-weight: bold;">{dam_state}</span>
                    </div>
                    """, unsafe_allow_html=True)

            # --- Pause pour simuler le temps réel ---
            time.sleep(1.0 / sim_speed)

        # --- Message final ---
        if simulation_log:
            total_run = sum([x["Duration (days)"] for x in simulation_log if x["Status"] == "Running"])
            total_stop = sum([x["Duration (days)"] for x in simulation_log if x["Status"] == "Stopped"])
            st.markdown(f"**📊 Final Summary:** {total_run} days **running**, {total_stop} days **stopped**")
        else:
            st.info("No state transitions occurred during the simulation.")

