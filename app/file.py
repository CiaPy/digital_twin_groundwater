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
tab1, tab2 = st.tabs(["📊 Supervision", "📈 Historique"])

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
