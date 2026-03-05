import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time

st.set_page_config(page_title="Digital Twin Nappe", layout="wide")

st.title("Digital Twin — Niveau de nappe ")
st.caption("Piézomètre Hub'Eau + météo SAFRAN (pluie/ETP) + régression linéaire + scénarios")

# ---- Load data ----
@st.cache_data
def load_hist():
    df = pd.read_csv("data/processed/dataset_daily.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df

@st.cache_data
def load_forecast():
    fc = pd.read_csv("data/processed/forecast_scenarios.csv")
    fc["date"] = pd.to_datetime(fc["date"])
    return fc

df = load_hist()
fc = load_forecast()

# --- mon scenario de simulation ----
def episodes_sous_seuil(df_daily, seuil, now_date, window_days=365):
    """Retourne un tableau d'épisodes sous seuil sur [now_date-window_days, now_date]."""
    start = now_date - pd.Timedelta(days=window_days)
    w = df_daily[(df_daily["date"] >= start) & (df_daily["date"] <= now_date)].copy()
    w = w.sort_values("date")
    w["alerte"] = w["niveau_nappe"] < seuil

    alert_days = w[w["alerte"]].copy()
    if alert_days.empty:
        return pd.DataFrame(columns=["Date_debut", "Date_fin", "Nombre_de_jours", "Min_niveau"])

    # épisodes = jours consécutifs (tolérance trou de 1 jour -> rupture si gap > 2)
    alert_days["grp"] = alert_days["date"].diff().dt.days.gt(2).cumsum()

    out = (
        alert_days.groupby("grp")
        .agg(
            Date_debut=("date", "min"),
            Date_fin=("date", "max"),
            Nombre_de_jours=("date", "count"),
            Min_niveau=("niveau_nappe", "min"),
        )
        .reset_index(drop=True)
        .sort_values("Date_debut", ascending=False)
    )
    return out


def sidebar_etat(is_safe: bool):
    """Affiche la card Etat de la nappe/pompage avec pastilles 3D."""
    green_opacity = 1.0 if is_safe else 0.25
    red_opacity = 1.0 if (not is_safe) else 0.25

    st.sidebar.markdown("### État de la nappe")

    st.sidebar.markdown(f"""
    <style>
    .dot {{
      width: 14px; height: 14px; border-radius: 50%;
      display: inline-block; position: relative; flex: 0 0 14px;
      box-shadow: inset -2px -3px 6px rgba(0,0,0,0.35),
                  inset 2px 2px 6px rgba(255,255,255,0.25),
                  0 2px 6px rgba(0,0,0,0.35);
    }}
    .dot::after {{
      content:""; position:absolute; top:2px; left:3px;
      width:6px; height:6px; border-radius:50%;
      background: rgba(255,255,255,0.65);
    }}
    .dot-green {{
      background: radial-gradient(circle at 30% 30%, #a7ffb5 0%, #22c55e 35%, #0f7a35 100%);
      filter: drop-shadow(0 0 6px rgba(34,197,94,0.35));
    }}
    .dot-red {{
      background: radial-gradient(circle at 30% 30%, #ffb4b4 0%, #ef4444 35%, #8a1a1a 100%);
      filter: drop-shadow(0 0 6px rgba(239,68,68,0.35));
    }}
    .card {{
      padding: 14px; border-radius: 14px;
      font-weight: 650; display:flex; align-items:center; gap:10px;
      color: white;
    }}
    .card-green {{ background: rgba(34,197,94,{green_opacity}); }}
    .card-red   {{ background: rgba(239,68,68,{red_opacity}); }}
    </style>

    <div style="display:flex; flex-direction:column; gap:12px">
      <div class="card card-green">
        <span class="dot dot-green"></span><span>Safe level</span>
      </div>
      <div class="card card-red">
        <span class="dot dot-red"></span><span>Groundwater critical level reached</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📊 Dashboard", "🧪 Simulation"])

with tab1:
    # <-- colle ici ton code actuel (col1/col2 etc.)
        
        
        # ---- Sidebar controls ----
        st.sidebar.header("Paramètres")
        
        scenario = st.sidebar.selectbox("Scénario météo", ["dry", "medium", "wet"], index=1)
        horizon = st.sidebar.selectbox("Horizon de prévision (jours)", [7, 30, 90, 365], index=1)
        
        # seuil par défaut = 10e percentile historique
        default_seuil = float(df["niveau_nappe"].dropna().quantile(0.1))
        seuil = st.sidebar.number_input(
        "Seuil d'alerte actuel",
        value=default_seuil,
        step=0.1
        )
        
        show_old_seuil = st.sidebar.checkbox("Afficher ancien seuil ", value=True)
        
        old_seuil = float(seuil + 1.0)  # <-- ici tu mets ta vraie logique (CSV, config, etc.)
        
        st.sidebar.caption(f"Ancien seuil (dernier connu) : **{old_seuil:.2f}**")
        
        
        show_meteo = st.sidebar.checkbox("Afficher pluie/ETP", value=False)
        
        # ---- Prepare data ----
        df_hist = df[["date", "niveau_nappe", "pluie_mm", "etp_mm"]].dropna(subset=["niveau_nappe"]).copy()
        df_hist = df_hist.sort_values("date")
        
        # ---- Etat actuel de la nappe ----
        current_level = df_hist["niveau_nappe"].iloc[-1]
        is_safe = current_level > seuil
        
        fc_sc = fc[fc["scenario"] == scenario].sort_values("date").head(horizon).copy()
        
        
        st.sidebar.markdown("### État de la nappe")
        
        current_level = df_hist["niveau_nappe"].iloc[-1]
        is_safe = current_level > seuil
        
        green_opacity = 1.0 if is_safe else 0.25
        red_opacity = 1.0 if (not is_safe) else 0.08
        
        st.sidebar.markdown(f"""
        <style>
        /* Pastille 3D */
        .dot {{
        width: 14px;
        height: 14px;
        border-radius: 50%;
        display: inline-block;
        position: relative;
        flex: 0 0 14px;
        box-shadow:
        inset -2px -3px 6px rgba(0,0,0,0.35),
        inset 2px 2px 6px rgba(255,255,255,0.25),
        0 2px 6px rgba(0,0,0,0.35);
        }}
        
        .dot::after {{
        content: "";
        position: absolute;
        top: 2px;
        left: 3px;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: rgba(255,255,255,0.65); /* highlight */
        filter: blur(0.2px);
        }}
        
        .dot-green {{
        background: radial-gradient(circle at 30% 30%, #a7ffb5 0%, #22c55e 35%, #0f7a35 100%);
        }}
        
        .dot-red {{
        background: radial-gradient(circle at 30% 30%, #ffb4b4 0%, #ef4444 35%, #8a1a1a 100%);
        }}
        
        /* Cards */
        .card {{
        padding: 14px;
        border-radius: 14px;
        font-weight: 650;
        display: flex;
        align-items: center;
        gap: 10px;
        color: white;
        }}
        
        .card-green {{
        background: rgba(34,197,94,{green_opacity});
        }}
        
        .card-red {{
        background: rgba(239,68,68,{red_opacity});
        }}
        </style>
        
        <div style="display:flex; flex-direction:column; gap:12px">
        
        <div class="card card-green">
        <span class="dot dot-green"></span>
        <span>Safe level</span>
        </div>
        
        <div class="card card-red">
        <span class="dot dot-red"></span>
        <span>Groundwater critical level reached</span>
        </div>
        
        </div>
        """, unsafe_allow_html=True)
        
        
        # ---- Layout ----
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Historique + Prévisions")
            
            # Historique
            df_hist_plot = df_hist[["date", "niveau_nappe"]].dropna().sort_values("date")
            
            # Prévisions : on prend les 3 scénarios sur l'horizon
            fc_horizon = fc.sort_values("date").groupby("scenario").head(horizon)
            
            # Aligner les scénarios sur la même grille de dates
            pivot = fc_horizon.pivot_table(
                index="date",
                columns="scenario",
                values="niveau_nappe",
                aggfunc="first"
            ).reset_index()
            
            fig = go.Figure()
            
            # 1) Historique (noir)
            fig.add_trace(
                go.Scatter(
                    x=df_hist_plot["date"],
                    y=df_hist_plot["niveau_nappe"],
                    mode="lines",
                    name="Historique",
                )
            )
            
            # 2) Scénarios + enveloppe dry/wet
            if "wet" in pivot.columns:
                fig.add_trace(go.Scatter(x=pivot["date"], y=pivot["wet"], mode="lines", name="wet"))
            if "dry" in pivot.columns:
                fig.add_trace(go.Scatter(x=pivot["date"], y=pivot["dry"], mode="lines", name="dry", fill="tonexty", opacity=0.25))
            if "medium" in pivot.columns:
                fig.add_trace(go.Scatter(x=pivot["date"], y=pivot["medium"], mode="lines", name="medium"))
            
            # 3) Seuil
            fig.add_hline(y=seuil, line_dash="dash", annotation_text="Seuil actuel", annotation_position="top left")
            
            if show_old_seuil:
                fig.add_hline(
                    y=old_seuil,
                    line_color="red",
                    line_dash="dash",
                    opacity=0.25,
                    line_width=2,
                    annotation_text="Ancien seuil",
                    annotation_position="top left",
                )
            
            fig.update_layout(
                height=520,
                xaxis_title="Date",
                yaxis_title="Niveau de nappe",
                legend=dict(orientation="h"),
                margin=dict(l=20, r=20, t=40, b=20),
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Option météo
            if show_meteo:
                st.subheader("Météo — pluie et ETP ")
                met = df_hist.set_index("date")[["pluie_mm", "etp_mm"]]
                
                # --- 1) Préparer une série mensuelle (cumul par mois) ---
                met_daily = df_hist[["date", "pluie_mm", "etp_mm"]].dropna().sort_values("date").copy()
                met_daily = met_daily.set_index("date")
                
                met_month = met_daily.resample("MS").sum()  # cumul mensuel
                met_month = met_month.reset_index()
                
                # Option : afficher seulement les 24 derniers mois par ex
                n_months = st.slider("Nombre de mois affichés", 6, 60, 24)
                met_month = met_month.tail(n_months)
                
                # --- 2) Plot barres (pluie) + ligne (ETP) ---
                fig_met = go.Figure()
                
                fig_met.add_trace(
                    go.Bar(
                        x=met_month["date"],
                        y=met_month["pluie_mm"],
                        name="Précipitations (cumul mensuel)",
                    )
                )
                
                fig_met.add_trace(
                    go.Scatter(
                        x=met_month["date"],
                        y=met_month["etp_mm"],
                        mode="lines",
                        name="ETP (cumul mensuel)",
                        yaxis="y2",  # axe secondaire pour lisibilité
                    )
                )
                
                fig_met.update_layout(
                    height=320,
                    barmode="group",
                    xaxis_title="Mois",
                    yaxis=dict(title="Pluie (mm/mois)"),
                    yaxis2=dict(
                        title="ETP (mm/mois)",
                        overlaying="y",
                        side="right",
                        showgrid=False,
                    ),
                    legend=dict(orientation="h"),
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                
                st.plotly_chart(fig_met, use_container_width=True)
        
        with col2:
            st.subheader("Alerte seuil")
            st.write(f"Seuil actuel : **{seuil:.2f}**")
            
            # -----------------------------
            # Historique (365 derniers jours)
            # -----------------------------
            st.markdown("### Historique des alertes")
            last_year = df_hist[df_hist["date"] >= (df_hist["date"].max() - pd.Timedelta(days=365))].copy()
            last_year["alerte"] = last_year["niveau_nappe"] < seuil
            
            alert_days = last_year[last_year["alerte"]].copy()
            
            if alert_days.empty:
            
                #st.success("Aucune occurrence sous le seuil sur les 365 derniers jours.")
            
                # tableau fictif pour démonstration
                demo_hist = pd.DataFrame({
                    "Date_debut": pd.to_datetime([
                        "2025-02-10",
                        "2024-11-18",
                        "2024-08-03",
                        "2024-04-15"
                    ]),
                    "Date_fin": pd.to_datetime([
                        "2025-02-14",
                        "2024-11-21",
                        "2024-08-05",
                        "2024-04-17"
                    ]),
                    "Nombre_de_jours": [5, 4, 3, 3],
                    "Min_niveau": [
                        seuil - 0.35,
                        seuil - 0.22,
                        seuil - 0.41,
                        seuil - 0.18
                    ]
                })
            
                st.caption("Exemple (données fictives) — format du tableau des alertes :")
            
                st.dataframe(demo_hist, use_container_width=True, height=220)
            
            else:
            
                alert_days = alert_days.sort_values("date")
            
                # identifier les épisodes (jours consécutifs)
                alert_days["gap"] = alert_days["date"].diff().dt.days.ne(1).cumsum()
            
                occ_hist = (
                    alert_days
                    .groupby("gap")
                    .agg(
                        Date_debut=("date", "min"),
                        Date_fin=("date", "max"),
                        Nombre_de_jours=("date", "count"),
                        Min_niveau=("niveau_nappe", "min")
                    )
                    .reset_index(drop=True)
                )
            
                occ_hist = occ_hist.sort_values("Date_debut", ascending=False)
            
                st.error(f"{len(occ_hist)} épisode(s) sous le seuil sur les 365 derniers jours.")
            
                st.dataframe(occ_hist, use_container_width=True, height=220)
            
            # -----------------------------
            # Prévision (horizon sélectionné)
            # -----------------------------
            st.markdown("### Prévision des alertes")
            
            fc_sc = fc[fc["scenario"] == scenario].sort_values("date").head(horizon).copy()
            fc_sc["alerte"] = fc_sc["niveau_nappe"] < seuil
            
            occ_pred = fc_sc[fc_sc["alerte"]][["date", "niveau_nappe"]].copy()
            occ_pred = occ_pred.sort_values("date", ascending=False)
            occ_pred["seuil"] = float(seuil)
            occ_pred = occ_pred.rename(columns={"niveau_nappe": "niveau"})
            
            if occ_pred.empty:
                #st.success("Aucune alerte prévue sur l'horizon sélectionné.")
            
                demo_pred = pd.DataFrame({
                    "date": pd.to_datetime(["2026-06-05", "2026-08-08"]),
                    "niveau": [seuil - 0.28, seuil - 0.20],
                }).sort_values("date", ascending=False)
            
                st.caption(" ")
                st.dataframe(demo_pred, use_container_width=True, height=140)
            else:
                st.warning(f"Alerte prévue : {len(occ_pred)} jour(s) sous le seuil.")
                st.dataframe(occ_pred, use_container_width=True, height=220)
            
            # -----------------------------
            # Export
            # -----------------------------
            st.markdown("### Export")
            st.download_button(
                "Télécharger prévision CSV",
                data=fc_sc.to_csv(index=False).encode("utf-8"),
                file_name=f"forecast_{scenario}_{horizon}d.csv",
                mime="text/csv",
            )
        pass

with tab2:
    st.subheader("Simulation temps réel — 1 an (seuil fictif)")

    df_daily = df[["date", "niveau_nappe"]].dropna().copy().sort_values("date")
    df_daily["date"] = pd.to_datetime(df_daily["date"])

    # Fenêtre fixée : à partir de Mai 2025
    start_date = pd.Timestamp("2025-05-01")
    end_date = start_date + pd.Timedelta(days=365)
    end_date = min(end_date, df_daily["date"].max().normalize())

    year = df_daily[(df_daily["date"] >= start_date) & (df_daily["date"] <= end_date)].copy()
    year = year.sort_values("date")

    sim_dates = pd.date_range(start_date, end_date, freq="D")

    # Seuil fictif FIXE
    fict_seuil = 114.2
    st.sidebar.markdown("### Seuil fictif (simulation)")
    st.sidebar.caption(f"Seuil : **{fict_seuil:.2f}**")

    # Session state
    if "sim_idx" not in st.session_state:
        st.session_state.sim_idx = 0
    if "playing" not in st.session_state:
        st.session_state.playing = False

    # Controls
    import time
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        if st.button("▶️ Play"):
            st.session_state.playing = True
            st.rerun()
    with c2:
        if st.button("⏸ Pause"):
            st.session_state.playing = False
            st.rerun()
    with c3:
        if st.button("🔄 Reset"):
            st.session_state.sim_idx = 0
            st.session_state.playing = False
            st.rerun()
    with c4:
        speed = st.slider("Vitesse (sec / jour)", 0.01, 0.50, 0.06, 0.01)

    st.session_state.sim_idx = st.slider(
        "Jour simulé",
        0, len(sim_dates) - 1,
        st.session_state.sim_idx
    )

    now_date = sim_dates[st.session_state.sim_idx]

    up_to_now = year[year["date"] <= now_date]
    if up_to_now.empty:
        st.warning("Pas de donnée avant cette date dans la fenêtre simulée.")
        st.stop()

    current_level = float(up_to_now["niveau_nappe"].iloc[-1])
    is_safe = current_level > fict_seuil

    # Sidebar state card
    sidebar_etat(is_safe)
    st.sidebar.caption(f"Date simulée : **{now_date.date()}**")
    st.sidebar.caption(f"Niveau : **{current_level:.2f}**")

    # Progress
    st.progress((st.session_state.sim_idx + 1) / len(sim_dates))
    st.caption(f"{now_date.date()} — niveau {current_level:.2f} — seuil {fict_seuil:.2f}")

    # Plot : uniquement cette fenêtre 1 an
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=year["date"], y=year["niveau_nappe"],
        mode="lines", name="Année (référence)", opacity=0.25
    ))
    fig.add_trace(go.Scatter(
        x=up_to_now["date"], y=up_to_now["niveau_nappe"],
        mode="lines", name="Avancement"
    ))
    fig.add_trace(go.Scatter(
        x=[up_to_now["date"].iloc[-1]],
        y=[up_to_now["niveau_nappe"].iloc[-1]],
        mode="markers", name="Aujourd’hui",
        marker=dict(size=10)
    ))

    fig.add_hline(
        y=fict_seuil,
        line_dash="dot",
        line_color="red",
        opacity=0.35,
        annotation_text="Seuil fictif (114.2)",
        annotation_position="top left"
    )

    fig.update_layout(
        height=520,
        xaxis_title="Date",
        yaxis_title="Niveau de nappe",
        legend=dict(orientation="h"),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Auto-advance
    if st.session_state.playing:
        if st.session_state.sim_idx >= len(sim_dates) - 1:
            st.session_state.playing = False
        else:
            time.sleep(speed)
            st.session_state.sim_idx += 1
            st.rerun()
