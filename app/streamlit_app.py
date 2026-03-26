import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# Configuration de la page
st.set_page_config(page_title="Jumeau Numérique Eau - Barrage & Contrôle", layout="wide")

# CSS personnalisé pour les indicateurs
st.markdown("""
<style>
/* Indicateurs d'état */
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

# Titre principal
st.title("🌊 Jumeau Numérique de l'Eau : Barrage & Contrôle Automatisé")

# Colonnes pour les infos
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("""
    **Composants simulés**
    - Piézomètre : mesure du niveau d'eau
    - Centre de contrôle : décision manuelle/automatique
    - Barrage : extraction activée/désactivée
    """)

with col2:
    st.caption("""
    **Fonctionnalités**
    - Mode automatique : arrêt si seuil critique
    - Mode manuel : contrôle direct
    - Historique des états
    """)

with col3:
    st.caption("""
    **Données**
    - Historique nappe : Hub'Eau
    - Scénarios : régression linéaire
    """)

# --- Chargement des données (inchangé) ---
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

# Simuler les données si les fichiers sont absents
try:
    df = load_hist()
    fc = load_forecast()
except:
    st.warning("Données réelles non trouvées. Génération de données simulées.")
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="D")
    n = len(dates)
    np = 115 + 10 * np.sin(np.arange(n) * 0.05) + np.random.normal(0, 0.5, n)
    df = pd.DataFrame({"date": dates, "niveau_nappe": np, "pluie_mm": np.random.exponential(5, n), "etp_mm": np.random.exponential(3, n)})
    fc = pd.DataFrame({"date": dates[-365:], "scenario": "medium", "niveau_nappe": np[-365:]})
    fc = pd.concat([fc.assign(scenario=sc) for sc in ["dry", "medium", "wet"]])



# === Ajout : Génération de l'historique du barrage ===
def generate_barrage_history(df, seuil, start_date=None):
    if start_date is None:
        start_date = df["date"].max() - pd.Timedelta(days=30)
    history = df[df["date"] >= start_date].copy()
    history["barrage_etat"] = "Arrêt"
    # Simulation simple : si niveau > seuil - 0.5, on suppose marche
    history.loc[history["niveau_nappe"] > (seuil - 0.5), "barrage_etat"] = "Marche"
    return history


# Générer l'historique dès le démarrage
if "barrage_history" not in st.session_state:
    st.session_state.barrage_history = generate_barrage_history(df, seuil=114.2)




# --- États de session ---
if "barrage_etat" not in st.session_state:
    st.session_state.barrage_etat = "Marche"  # ou "Arrêt"
if "mode_controle" not in st.session_state:
    st.session_state.mode_controle = "Automatique"
if "alert_history" not in st.session_state:
    st.session_state.alert_history = []
if "control_log" not in st.session_state:
    st.session_state.control_log = []

# --- Sidebar : Contrôle central ---
st.sidebar.header("🏛️ Centre de Contrôle")
mode = st.sidebar.radio("Mode de fonctionnement", ["Automatique", "Manuel"], index=0 if st.session_state.mode_controle == "Automatique" else 1)
st.session_state.mode_controle = mode

seuil = st.sidebar.number_input("Seuil critique (m)", value=114.2, step=0.1)
st.sidebar.markdown("---")

# Boutons de commande (uniquement en mode manuel)
if mode == "Manuel":
    col_marche, col_arret = st.sidebar.columns(2)
    if col_marche.button("🟢 Marche"):
        st.session_state.barrage_etat = "Marche"
        st.session_state.control_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "Mise en marche manuelle",
            "level": float(df["niveau_nappe"].iloc[-1])
        })
    if col_arret.button("🔴 Arrêt"):
        st.session_state.barrage_etat = "Arrêt"
        st.session_state.control_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "Arrêt manuel",
            "level": float(df["niveau_nappe"].iloc[-1])
        })

# --- Données actuelles ---
current_level = float(df["niveau_nappe"].iloc[-1])
is_safe = current_level > seuil

# --- Logique automatique ---
if mode == "Automatique":
    if is_safe and st.session_state.barrage_etat != "Marche":
        st.session_state.barrage_etat = "Marche"
        st.session_state.control_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "Marche (niveau sûr)",
            "level": current_level
        })
    elif not is_safe and st.session_state.barrage_etat != "Arrêt":
        st.session_state.barrage_etat = "Arrêt"
        st.session_state.control_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "Arrêt (niveau critique)",
            "level": current_level
        })

# --- Affichage principal ---
tab1, tab2, tab3 = st.tabs(["📊 Supervision", "📈 Historique", "▶️ Live"])

with tab1:
    # Colonnes
    col_param, col_graph, col_control = st.columns([1, 2, 1])

    with col_param:
        st.markdown("## 📡 Données en Temps Réel")

        # Niveau d'eau
        st.markdown(f"""
        <div class="status-card {'status-safe' if is_safe else 'status-alert'}">
            <span class="dot {'dot-green' if is_safe else 'dot-red'}"></span>
            <strong>Niveau nappe :</strong> {current_level:.2f} m
        </div>
        """, unsafe_allow_html=True)

        # État du barrage
        etat_color = "status-running" if st.session_state.barrage_etat == "Marche" else "status-stopped"
        dot_color = "dot-blue" if st.session_state.barrage_etat == "Marche" else "dot-red"
        st.markdown(f"""
        <div class="status-card {etat_color}">
            <span class="dot {dot_color}"></span>
            <strong>Barrage :</strong> {st.session_state.barrage_etat}
        </div>
        """, unsafe_allow_html=True)

        # Mode de contrôle
        mode_color = "status-running" if mode == "Automatique" else "status-alert"
        dot_mode = "dot-green" if mode == "Automatique" else "dot-red"
        st.markdown(f"""
        <div class="status-card {mode_color}">
            <span class="dot {dot_mode}"></span>
            <strong>Mode :</strong> {mode}
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🏗️ Barrage")
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Grande_Discorde_dam.jpg/800px-Grande_Discorde_dam.jpg", width=200)

    with col_graph:
        st.subheader("Évolution du niveau de nappe")

        # Graphique Plotly
        fig = go.Figure()

        # Historique
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["niveau_nappe"],
            mode="lines",
            name="Niveau nappe",
            line=dict(color="blue", width=2)
        ))

        # Seuil
        fig.add_hline(y=seuil, line_dash="dash", line_color="red",
                      annotation_text="Seuil critique", annotation_position="top left")

        fig.update_layout(
            height=500,
            xaxis_title="Date",
            yaxis_title="Niveau (m)",
            margin=dict(l=20, r=20, t=40, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)

    with col_control:
        st.markdown("## 📋 Journal des Actions")
        if st.session_state.control_log:
            log_df = pd.DataFrame(st.session_state.control_log[-10:])
            st.dataframe(log_df[::-1], use_container_width=True, height=400)
        else:
            st.info("Aucune action enregistrée.")

with tab2:
    st.subheader("📋 Historique des États")

    if st.session_state.control_log:
        full_log = pd.DataFrame(st.session_state.control_log)
        st.dataframe(full_log, use_container_width=True)
    else:
        st.info("Aucun événement à afficher.")

    st.download_button(
        "📥 Exporter le journal",
        data=pd.DataFrame(st.session_state.control_log).to_csv(index=False),
        file_name="journal_barrage.csv",
        mime="text/csv"
    )

with tab3:
    st.subheader("🎥 Simulation en Temps Réel (1 an)")

    # Paramètres
    sim_seuil = st.number_input("Seuil critique (m)", value=114.2, step=0.1, key="sim_seuil_live")
    sim_speed = st.slider("Vitesse de simulation (jours/seconde)", 1, 30, 10, key="sim_speed_live")
    sim_start_date = pd.Timestamp("2025-01-01")  # Date fixe pour la démo

    if st.button("▶️ Lancer la simulation"):
        # Préparer les données
        start_date = sim_start_date
        end_date = start_date + pd.Timedelta(days=365)
        sim_dates = pd.date_range(start_date, end_date, freq="D")

        # Filtrer les données historiques
        current_df = df[df["date"] >= start_date].copy()
        current_df = current_df[current_df["date"] <= end_date]
        current_df = current_df.sort_values("date")

        # Initialisation
        placeholder = st.empty()
        log_placeholder = st.container()

        simulation_log = []
        current_state = None
        period_start = None

        # Boucle de simulation
        for i, current_date in enumerate(sim_dates):
            # Données jusqu'à la date courante
            sub_df = current_df[current_df["date"] <= current_date]
            if sub_df.empty:
                continue
            current_level = float(sub_df["niveau_nappe"].iloc[-1])
            is_safe = current_level > sim_seuil

            # Décision automatique
            etat_barrage = "Marche" if is_safe else "Arrêt"

            # Gestion des périodes
            if etat_barrage != current_state:
                if current_state is not None:
                    # Fin de la période précédente
                    simulation_log.append({
                        "État": current_state,
                        "Début": period_start.strftime("%Y-%m-%d"),
                        "Fin": (current_date - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                        "Durée (jours)": (current_date - period_start).days,
                        "Seuil (m)": sim_seuil,
                        "Niveau moyen (m)": round(sub_df["niveau_nappe"].tail(len(sub_df) - len(sub_df[sub_df["date"] < period_start])).mean(), 2)
                    })
                # Nouvelle période
                current_state = etat_barrage
                period_start = current_date

            # --- Affichage dynamique ---
            with placeholder.container():
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown("### Évolution du niveau d’eau")
                    fig = go.Figure()

                    # Historique complet (gris)
                    fig.add_trace(go.Scatter(
                        x=current_df["date"],
                        y=current_df["niveau_nappe"],
                        mode="lines",
                        name="Historique",
                        line=dict(color="lightgray", width=2),
                        opacity=0.5
                    ))

                    # Données simulées jusqu'à aujourd'hui (bleu)
                    fig.add_trace(go.Scatter(
                        x=sub_df["date"],
                        y=sub_df["niveau_nappe"],
                        mode="lines",
                        name="Simulation",
                        line=dict(color="blue", width=2)
                    ))

                    # Seuil
                    fig.add_hline(
                        y=sim_seuil,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"Seuil : {sim_seuil} m",
                        annotation_position="top left"
                    )

                    # --- Curseur : jour actuel (CORRIGÉ) ---
                    # Ajout de la ligne verticale
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
                    # Ajout de l'annotation manuellement
                    fig.add_annotation(
                        x=current_date,
                        y=1.02,
                        xref="x",
                        yref="paper",
                        text=f"Jour : {current_date.strftime('%Y-%m-%d')}",
                        showarrow=False,
                        font=dict(size=12, color="orange"),
                        bgcolor="rgba(0,0,0,0.6)",
                        borderpad=4,
                        xanchor="center"
                    )

                    fig.update_layout(
                        height=500,
                        xaxis_title="Date",
                        yaxis_title="Niveau (m)",
                        margin=dict(l=20, r=20, t=60, b=20),
                        xaxis=dict(type="date")  # ✅ Sécurité supplémentaire
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    st.markdown("### État du système")
                    color = "green" if etat_barrage == "Marche" else "red"
                    st.markdown(f"""
                    <div style="padding:15px; border-radius:10px; background-color: #1a1a1a; color: white; margin: 10px 0;">
                        <strong>📅 Date :</strong> {current_date.strftime("%Y-%m-%d")}<br>
                        <strong>💧 Niveau :</strong> {current_level:.2f} m<br>
                        <strong>🎯 Seuil :</strong> {sim_seuil} m<br>
                        <strong>🔴 Barrage :</strong> 
                        <span style="color: {color}; font-weight: bold;">{etat_barrage}</span>
                    </div>
                    """, unsafe_allow_html=True)

            # Pause pour simuler le temps réel
            time.sleep(1.0 / sim_speed)

        # --- Afficher l'historique des périodes ---
        with log_placeholder:
            st.markdown("### 📊 Historique des états du barrage")
            if simulation_log:
                log_df = pd.DataFrame(simulation_log)
                st.dataframe(log_df, use_container_width=True)

                # Statistiques
                total_marche = log_df[log_df["État"] == "Marche"]["Durée (jours)"].sum()
                total_arret = log_df[log_df["État"] == "Arrêt"]["Durée (jours)"].sum()
                st.markdown(f"**📊 Bilan sur 1 an :** {total_marche} jours en **marche**, {total_arret} jours à **l'arrêt**")
            else:
                st.info("Aucune transition d'état détectée pendant la simulation.")

