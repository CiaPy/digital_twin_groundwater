import pandas as pd
import requests
from urllib.parse import quote
from utils import load_config, ensure_dir

BASE = "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes"

def download_chroniques(code_bss: str, start_date: str, end_date: str) -> pd.DataFrame:
    # Endpoint "chroniques" (CSV)
    # Exemple documenté côté Hub’Eau (API Piézométrie). :contentReference[oaicite:1]{index=1}
    url = (
        f"{BASE}/chroniques.csv?"
        f"code_bss={quote(code_bss)}"
        f"&date_debut_mesure={start_date}"
        f"&date_fin_mesure={end_date}"
        f"&size=20000"
        f"&sort=asc"
    )
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    # Hub'Eau renvoie un CSV
    from io import StringIO
    df = pd.read_csv(StringIO(r.text), sep=";", quotechar='"')
    return df

def main():
    cfg = load_config()
    ensure_dir("data/raw")

    df = download_chroniques(cfg["code_bss"], cfg["start_date"], cfg["end_date"])

    # Harmonisation minimale
    # Colonnes typiques : date_mesure, niveau_nappe, profondeur_nappe, ... (selon station)
    if "date_mesure" not in df.columns:
        raise ValueError(f"Colonne 'date_mesure' introuvable. Colonnes: {list(df.columns)}")

    df["date_mesure"] = pd.to_datetime(df["date_mesure"], errors="coerce").dt.date
    df = df.dropna(subset=["date_mesure"])

    out = f"data/raw/piezo_{cfg['code_bss'].replace('/','_')}.csv"
    df.to_csv(out, index=False)
    print(f"OK -> {out} ({len(df)} lignes)")

if __name__ == "__main__":
    main()