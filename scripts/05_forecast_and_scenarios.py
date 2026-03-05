import numpy as np
import pandas as pd
import joblib
from pathlib import Path

DATASET_PATH = "data/processed/dataset_daily.csv"
MODEL_PATH = "models/model.joblib"
OUT_PATH = "data/processed/forecast_scenarios.csv"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcule les features exactement comme dans 03_build_dataset.py"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # lags niveau
    for lag in [1, 2, 3, 7, 14, 30]:
        df[f"niveau_lag_{lag}"] = df["niveau_nappe"].shift(lag)

    # cumuls pluie/etp
    for w in [7, 14, 30]:
        df[f"pluie_sum_{w}"] = df["pluie_mm"].rolling(w).sum()
        df[f"etp_sum_{w}"] = df["etp_mm"].rolling(w).sum()

    # saisonnalité
    df["doy"] = df["date"].dt.dayofyear
    df["month"] = df["date"].dt.month

    return df


def make_future_meteo_from_climatology(df_hist: pd.DataFrame, horizon_days: int, scenario: str) -> pd.DataFrame:
    """
    Crée une météo future à partir de la moyenne par jour-de-l'année (climatologie),
    puis applique un facteur scénario.
    """
    factors = {
        "dry": (0.7, 1.15),     # moins de pluie, plus d'ETP
        "medium": (1.0, 1.0),
        "wet": (1.3, 0.95),     # plus de pluie, ETP un peu plus faible
    }
    rain_f, etp_f = factors.get(scenario, factors["medium"])

    hist = df_hist.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["doy"] = hist["date"].dt.dayofyear

    clim = hist.groupby("doy")[["pluie_mm", "etp_mm"]].mean()

    last_date = hist["date"].max()
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon_days, freq="D")

    fut = pd.DataFrame({"date": future_dates})
    fut["doy"] = fut["date"].dt.dayofyear

    fut = fut.join(clim, on="doy")
    fut["pluie_mm"] = (fut["pluie_mm"].fillna(0.0) * rain_f).astype(float)
    fut["etp_mm"] = (fut["etp_mm"].interpolate(limit_direction="both").fillna(0.0) * etp_f).astype(float)

    return fut[["date", "pluie_mm", "etp_mm"]]


def forecast_iterative(df_hist: pd.DataFrame, model_pack: dict, horizon_days: int, scenario: str) -> pd.DataFrame:
    model = model_pack["model"]
    FEATURES = model_pack["features"]

    # météo future scénario
    fut_meteo = make_future_meteo_from_climatology(df_hist, horizon_days, scenario)

    # concat hist + futur (niveau futur à remplir)
    hist = df_hist.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values("date")

    fut = fut_meteo.copy()
    fut["niveau_nappe"] = np.nan

    full = pd.concat([hist, fut], ignore_index=True)
    full = build_features(full)

    start_idx = len(hist)

    for i in range(start_idx, len(full)):
        row = full.iloc[i]

        # si features manquantes -> on tente de recalculer et/ou skip
        if row[FEATURES].isna().any():
            # rebuild complet (au cas où)
            full = build_features(full)
            row = full.iloc[i]
            if row[FEATURES].isna().any():
                continue

        yhat = float(model.predict(row[FEATURES].to_frame().T)[0])
        full.at[i, "niveau_nappe"] = yhat

        # mise à jour features après injection de la prédiction
        full = build_features(full)

    out = full.iloc[start_idx:][["date", "niveau_nappe", "pluie_mm", "etp_mm"]].copy()
    out["scenario"] = scenario
    return out


def main():
    Path("data/processed").mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATASET_PATH)
    df["date"] = pd.to_datetime(df["date"])

    # on garde l'historique utile
    df_hist = df[["date", "niveau_nappe", "pluie_mm", "etp_mm"]].dropna(subset=["niveau_nappe"]).copy()
    df_hist = df_hist.sort_values("date")

    model_pack = joblib.load(MODEL_PATH)

    horizons = [7, 30, 90, 365]
    horizon_days = 30  # par défaut, on sort 30 jours (Streamlit pourra filtrer)
    if "forecast_horizons_days" in model_pack:
        horizon_days = int(model_pack["forecast_horizons_days"][1])

    # ici on fixe 365 max pour que tu aies un gros fichier unique
    horizon_days = 365

    all_fc = []
    for sc in ["dry", "medium", "wet"]:
        print(f"Prévision scénario: {sc} (horizon={horizon_days} jours)")
        fc = forecast_iterative(df_hist, model_pack, horizon_days=horizon_days, scenario=sc)
        all_fc.append(fc)

    out = pd.concat(all_fc, ignore_index=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"OK -> {OUT_PATH} ({len(out)} lignes)")
    print(out.head(3).to_string(index=False))
    print(out.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()