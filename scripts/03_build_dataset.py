import pandas as pd
import numpy as np
from utils import load_config, ensure_dir

def main():

    cfg = load_config()

    ensure_dir("data/processed")

    piezo_path = f"data/raw/piezo_{cfg['code_bss'].replace('/','_')}.csv"

    print("Lecture piezometre:", piezo_path)

    piezo = pd.read_csv(piezo_path)

    # conversion date
    piezo["date_mesure"] = pd.to_datetime(piezo["date_mesure"])

    # colonne niveau
    if "niveau_nappe_eau" not in piezo.columns:
        raise ValueError("colonne niveau_nappe_eau introuvable")

    piezo = piezo.rename(columns={"niveau_nappe_eau": "niveau_nappe"})

    piezo = piezo[["date_mesure", "niveau_nappe"]]

    piezo = piezo.sort_values("date_mesure")

    # passage au pas journalier
    piezo["date"] = piezo["date_mesure"].dt.floor("D")

    piezo_daily = piezo.groupby("date", as_index=False)["niveau_nappe"].mean()

    # lecture meteo
    print("Lecture meteo:", cfg["meteo_csv_path"])

    meteo = pd.read_csv(cfg["meteo_csv_path"])

    meteo["date"] = pd.to_datetime(meteo["date"])

    # index complet
    start = min(piezo_daily["date"].min(), meteo["date"].min())

    end = max(piezo_daily["date"].max(), meteo["date"].max())

    idx = pd.date_range(start=start, end=end, freq="D")

    df = pd.DataFrame({"date": idx})

    df = df.merge(piezo_daily, on="date", how="left")

    df = df.merge(meteo, on="date", how="left")

    # pluie NA -> 0
    df["pluie_mm"] = df["pluie_mm"].fillna(0)

    # etp interpolation
    df["etp_mm"] = df["etp_mm"].interpolate(limit_direction="both")

    # features hydrologiques

    for lag in [1,2,3,7,14,30]:

        df[f"niveau_lag_{lag}"] = df["niveau_nappe"].shift(lag)

    for w in [7,14,30]:

        df[f"pluie_sum_{w}"] = df["pluie_mm"].rolling(w).sum()

        df[f"etp_sum_{w}"] = df["etp_mm"].rolling(w).sum()

    # saisonnalité

    df["doy"] = df["date"].dt.dayofyear

    df["month"] = df["date"].dt.month

    # retirer lignes sans niveau

    df = df.dropna(subset=["niveau_nappe"])

    out = "data/processed/dataset_daily.csv"

    df.to_csv(out, index=False)

    print("Dataset créé:", out)

    print("Nombre lignes:", len(df))


if __name__ == "__main__":

    main()