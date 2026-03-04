import streamlit as st
import pandas as pd

st.set_page_config(page_title="Digital Twin Nappe", layout="wide")

st.title("Digital Twin — Niveau de nappe (V1)")
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

# ---- Sidebar controls ----
st.sidebar.header("Paramètres")

scenario = st.sidebar.selectbox("Scénario météo", ["dry", "medium", "wet"], index=1)
horizon = st.sidebar.selectbox("Horizon de prévision (jours)", [7, 30, 90, 365], index=1)

# seuil par défaut = 10e percentile historique
default_seuil = float(df["niveau_nappe"].dropna().quantile(0.1))
seuil = st.sidebar.number_input(
    "Seuil d'alerte (même unité que niveau)",
    value=default_seuil,
    step=0.1
)

show_meteo = st.sidebar.checkbox("Afficher pluie/ETP", value=False)

# ---- Prepare data ----
df_hist = df[["date", "niveau_nappe", "pluie_mm", "etp_mm"]].dropna(subset=["niveau_nappe"]).copy()
df_hist = df_hist.sort_values("date")

fc_sc = fc[fc["scenario"] == scenario].sort_values("date").head(horizon).copy()

# ---- Layout ----
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Historique — niveau de nappe")
    hist_plot = df_hist.set_index("date")[["niveau_nappe"]]
    st.line_chart(hist_plot, height=320)

    st.subheader(f"Prévision — scénario: {scenario} (horizon {horizon} jours)")
    pred_plot = fc_sc.set_index("date")[["niveau_nappe"]]
    st.line_chart(pred_plot, height=320)

    if show_meteo:
        st.subheader("Météo — pluie et ETP (historique)")
        met = df_hist.set_index("date")[["pluie_mm", "etp_mm"]]
        st.line_chart(met, height=240)

with col2:
    st.subheader("Alerte seuil")
    st.write(f"Seuil actuel : **{seuil:.2f}**")

    # Alertes historiques (dernier 1 an)
    st.markdown("### Historique (365 derniers jours)")
    last_year = df_hist[df_hist["date"] >= (df_hist["date"].max() - pd.Timedelta(days=365))].copy()
    last_year["alerte"] = last_year["niveau_nappe"] < seuil
    occ_hist = last_year[last_year["alerte"]][["date", "niveau_nappe"]].sort_values("date", ascending=False)

    if occ_hist.empty:
        st.success("Aucune occurrence sous le seuil sur les 365 derniers jours.")
    else:
        st.error(f"{len(occ_hist)} jour(s) sous le seuil sur les 365 derniers jours.")
        st.dataframe(occ_hist, use_container_width=True, height=220)

    st.markdown("### Prévision (horizon sélectionné)")
    fc_sc["alerte"] = fc_sc["niveau_nappe"] < seuil
    occ_pred = fc_sc[fc_sc["alerte"]][["date", "niveau_nappe"]].copy()

    if occ_pred.empty:
        st.success("Aucune alerte prévue sur l'horizon sélectionné.")
    else:
        st.warning(f"Alerte prévue : {len(occ_pred)} jour(s) sous le seuil.")
        st.dataframe(occ_pred, use_container_width=True, height=220)

    st.markdown("### Export")
    st.download_button(
        "Télécharger prévision CSV",
        data=fc_sc.to_csv(index=False).encode("utf-8"),
        file_name=f"forecast_{scenario}_{horizon}d.csv",
        mime="text/csv",
    )

st.divider()
st.subheader("Résumé")
st.write(
    f"- Dernière date historique: **{df_hist['date'].max().date()}**\n"
    f"- Première date prévision: **{fc_sc['date'].min().date()}**\n"
    f"- Dernière date prévision: **{fc_sc['date'].max().date()}**\n"
)