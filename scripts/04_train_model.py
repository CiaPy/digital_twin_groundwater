import pandas as pd
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

DATA_PATH = "data/processed/dataset_daily.csv"
MODEL_PATH = "models/model.joblib"


def main():

    print("Lecture dataset")

    df = pd.read_csv(DATA_PATH)

    df["date"] = pd.to_datetime(df["date"])

    # features utilisées
    FEATURES = [
        "niveau_lag_1",
        "niveau_lag_2",
        "niveau_lag_3",
        "niveau_lag_7",
        "niveau_lag_14",
        "niveau_lag_30",
        "pluie_sum_7",
        "pluie_sum_14",
        "pluie_sum_30",
        "etp_sum_7",
        "etp_sum_14",
        "etp_sum_30",
        "month",
        "doy",
    ]

    TARGET = "niveau_nappe"

    # supprimer lignes avec NA
    df = df.dropna(subset=FEATURES + [TARGET])

    print("Nombre lignes dataset:", len(df))

    # split temporel
    split = int(len(df) * 0.8)

    train = df.iloc[:split]
    test = df.iloc[split:]

    X_train = train[FEATURES]
    y_train = train[TARGET]

    X_test = test[FEATURES]
    y_test = test[TARGET]

    print("Train:", len(train))
    print("Test:", len(test))

    # modèle
    model = LinearRegression()

    model.fit(X_train, y_train)

    # prédiction
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print("\nRésultats modèle")
    print("MAE:", mae)
    print("R2:", r2)

    # sauvegarde modèle
    Path("models").mkdir(exist_ok=True)

    joblib.dump(
        {
            "model": model,
            "features": FEATURES,
        },
        MODEL_PATH,
    )

    print("\nModèle sauvegardé:", MODEL_PATH)


if __name__ == "__main__":
    main()