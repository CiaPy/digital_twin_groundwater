import pandas as pd
import requests
from io import StringIO
from pathlib import Path
from datetime import datetime, date

from utils import load_config, ensure_dir

HUBEAU_STATIONS = "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/stations"
GEOSAS_POSITION = "https://api.geosas.fr/edr/collections/safran-isba/position"


def get_station_coords_from_hubeau(code_bss: str) -> tuple[float, float, str]:
    r = requests.get(HUBEAU_STATIONS, params={"code_bss": code_bss, "size": 1}, timeout=(15, 120))
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data", [])
    if not data:
        raise RuntimeError(f"Aucune station trouvée pour code_bss={code_bss}")
    st = data[0]

    # Try WGS84 keys first
    for lat_key, lon_key in [("latitude", "longitude"), ("lat", "lon")]:
        if lat_key in st and lon_key in st and st[lat_key] is not None and st[lon_key] is not None:
            x = float(st[lon_key])  # lon
            y = float(st[lat_key])  # lat
            return x, y, "EPSG:4326"

    # Try Lambert-93-like keys
    for x_key, y_key in [("x", "y"), ("x_l93", "y_l93"), ("x_coord", "y_coord")]:
        if x_key in st and y_key in st and st[x_key] is not None and st[y_key] is not None:
            x = float(st[x_key])
            y = float(st[y_key])

            # Heuristic: if values look like lon/lat, treat as EPSG:4326
            if -180 <= x <= 180 and -90 <= y <= 90:
                return x, y, "EPSG:4326"

            return x, y, "EPSG:2154"

    raise RuntimeError(f"Coordonnées introuvables. Clés station: {list(st.keys())}")


def make_year_chunks(start_date: str, end_date: str, step_years: int = 5):
    s = datetime.strptime(start_date, "%Y-%m-%d").date()
    e = datetime.strptime(end_date, "%Y-%m-%d").date()
    chunks = []
    y = s.year
    while True:
        cstart = date(y, 1, 1)
        if cstart < s:
            cstart = s
        yend = min(y + step_years - 1, e.year)
        cend = date(yend, 12, 31)
        if cend > e:
            cend = e
        chunks.append((cstart.isoformat(), cend.isoformat()))
        if cend >= e:
            break
        y = yend + 1
    return chunks


def fetch_safran_position_csv(x: float, y: float, crs: str, d1: str, d2: str) -> pd.DataFrame:
    params = {
        "parameter-name": "ETP_Q,PRELIQ_Q,PRENEI_Q",
        "coords": f"POINT({x} {y})",
        "crs": crs,
        "datetime": f"{d1}/{d2}",
        "f": "CSV",
    }
    r = requests.get(GEOSAS_POSITION, params=params, timeout=(20, 240))
    r.raise_for_status()

    txt = r.text.strip()
    if len(txt) == 0:
        return pd.DataFrame()

    # Read CSV (some implementations return ; separated)
    df = None
    try:
        df = pd.read_csv(StringIO(txt), comment="#")
    except Exception:
        df = pd.read_csv(StringIO(txt), comment="#", sep=";")

    if df.empty:
        return df

    # Find time column robustly
    time_col = None
    lower_cols = {c.lower(): c for c in df.columns}
    for key in ["datetime", "time", "date", "t"]:
        if key in lower_cols:
            time_col = lower_cols[key]
            break

    if time_col is None:
        # As a fallback, assume first column is time
        time_col = df.columns[0]

    df[time_col] = pd.to_datetime(df[time_col], errors="coerce", utc=True)
    df = df.dropna(subset=[time_col]).rename(columns={time_col: "date"})
    df["date"] = df["date"].dt.tz_convert(None).dt.floor("D")

    # Find variable columns by prefix
    def find_prefix(prefix: str):
        for c in df.columns:
            if str(c).startswith(prefix):
                return c
        # Sometimes columns are like "ETP_Q (mm)" or "ETP_Q_mm"
        for c in df.columns:
            if str(c).replace(" ", "").startswith(prefix):
                return c
        return None

    c_etp = find_prefix("ETP_Q")
    c_liq = find_prefix("PRELIQ_Q")
    c_nei = find_prefix("PRENEI_Q")

    if c_etp is None or c_liq is None or c_nei is None:
        # Print debug sample (first 5 lines of response)
        sample = "\n".join(txt.splitlines()[:10])
        raise ValueError(
            "Colonnes SAFRAN attendues non trouvées.\n"
            f"Colonnes reçues: {list(df.columns)}\n"
            f"Début réponse CSV:\n{sample}"
        )

    out = pd.DataFrame({
        "date": df["date"],
        "etp_mm": pd.to_numeric(df[c_etp], errors="coerce"),
        "pluie_mm": pd.to_numeric(df[c_liq], errors="coerce") + pd.to_numeric(df[c_nei], errors="coerce"),
    })
    return out


def main():
    cfg = load_config()
    ensure_dir("data/raw")

    code_bss = cfg["code_bss"]
    start_date = cfg["start_date"]
    end_date = cfg["end_date"]
    out_path = Path(cfg.get("meteo_csv_path", "data/raw/meteo_daily.csv"))

    print(f"[1/4] Coordonnées depuis Hub'Eau pour {code_bss} ...")
    x, y, crs = get_station_coords_from_hubeau(code_bss)
    print(f" -> coords={x} {y} ; crs={crs}")

    chunks = make_year_chunks(start_date, end_date, step_years=5)
    print(f"[2/4] Téléchargement SAFRAN par blocs (n={len(chunks)}) ...")

    parts = []
    for i, (d1, d2) in enumerate(chunks, 1):
        print(f"  - bloc {i}/{len(chunks)} : {d1} -> {d2}")
        df = fetch_safran_position_csv(x, y, crs, d1, d2)
        print(f"    -> {len(df)} jours")
        parts.append(df)

    meteo = pd.concat(parts, ignore_index=True)
    if meteo.empty:
        raise RuntimeError("SAFRAN a renvoyé 0 ligne (vérifier coords/crs/dates).")

    meteo = meteo.dropna(subset=["date"]).sort_values("date")
    meteo = meteo.groupby("date", as_index=False)[["pluie_mm", "etp_mm"]].mean()

    meteo["pluie_mm"] = meteo["pluie_mm"].fillna(0.0)
    meteo["etp_mm"] = meteo["etp_mm"].interpolate(limit_direction="both").fillna(0.0)

    meteo.to_csv(out_path, index=False)
    print(f"[3/4] OK -> {out_path} ({len(meteo)} jours)")

    print("[4/4] Aperçu:")
    print(meteo.head(3).to_string(index=False))
    print(meteo.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()