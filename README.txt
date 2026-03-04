# Digital Twin Groundwater — Piézomètre & Prévision du niveau de nappe

## Description

Ce projet implémente une première version d’un **digital twin simplifié de nappe phréatique**.
L’objectif est de **prévoir l’évolution du niveau d’un piézomètre** à partir :

* des observations historiques Hub’Eau (ADES)
* des données météorologiques SAFRAN (pluie et évapotranspiration potentielle)
* d’un modèle de **régression linéaire**

Une interface **Streamlit** permet ensuite de :

* visualiser l’historique du niveau de nappe
* explorer des **scénarios météorologiques**
* définir un **seuil critique**
* détecter les **alertes de franchissement de seuil**

Ce projet constitue une **preuve de concept (PoC)** d’un digital twin hydrologique.

---

# Architecture du projet

```
digital_twin_groundwater/
│
├── app/
│   └── streamlit_app.py          # Interface utilisateur
│
├── data/
│   ├── raw/                      # Données brutes
│   │   ├── piezo_*.csv
│   │   └── meteo_daily.csv
│   │
│   └── processed/
│       ├── dataset_daily.csv
│       └── forecast_scenarios.csv
│
├── models/
│   └── model.joblib              # Modèle entraîné
│
├── scripts/
│   ├── 01_download_piezo.py      # téléchargement données HubEau
│   ├── 02_get_meteo_template.py  # récupération météo SAFRAN
│   ├── 03_build_dataset.py       # construction du dataset
│   ├── 04_train_model.py         # entraînement du modèle
│   └── 05_forecast_and_scenarios.py
│
├── config.json                   # paramètres projet
├── requirements.txt
└── README.md
```

---

# Pipeline du projet

Le pipeline se déroule en **5 étapes**.

---

# 1. Téléchargement des données piézométriques

Script :

```
scripts/01_download_piezo.py
```

Source :

* API **Hub’Eau / ADES**

Contenu :

* niveau de nappe
* profondeur
* date de mesure

Sortie :

```
data/raw/piezo_CODEBSS.csv
```

---

# 2. Téléchargement des données météorologiques

Script :

```
scripts/02_get_meteo_template.py
```

Source :

* **SAFRAN-ISBA** (Météo-France)

Variables utilisées :

| Variable | Description                    |
| -------- | ------------------------------ |
| PRELIQ_Q | précipitations liquides        |
| PRENEI_Q | précipitations solides         |
| ETP_Q    | évapotranspiration potentielle |

Pluie totale :

```
pluie = PRELIQ_Q + PRENEI_Q
```

Sortie :

```
data/raw/meteo_daily.csv
```

Format :

```
date,pluie_mm,etp_mm
1990-01-01,0.6,0.4
1990-01-02,0.0,0.4
```

---

# 3. Construction du dataset

Script :

```
scripts/03_build_dataset.py
```

Cette étape :

* aligne les séries temporelles
* fusionne **piézo + météo**
* crée des **features hydrologiques**

Features créées :

### Mémoire de la nappe

```
niveau_lag_1
niveau_lag_2
niveau_lag_3
niveau_lag_7
niveau_lag_14
niveau_lag_30
```

### Recharge climatique

```
pluie_sum_7
pluie_sum_14
pluie_sum_30
```

### Evapotranspiration

```
etp_sum_7
etp_sum_14
etp_sum_30
```

### Saison

```
month
doy
```

Sortie :

```
data/processed/dataset_daily.csv
```

---

# 4. Entraînement du modèle

Script :

```
scripts/04_train_model.py
```

Modèle utilisé :

```
LinearRegression (scikit-learn)
```

Le dataset est séparé en :

```
80% train
20% test
```

Métriques calculées :

* MAE
* R²

Le modèle est sauvegardé :

```
models/model.joblib
```

---

# 5. Génération de prévisions

Script :

```
scripts/05_forecast_and_scenarios.py
```

Des scénarios météorologiques sont générés :

| Scénario | Description         |
| -------- | ------------------- |
| dry      | sécheresse          |
| medium   | conditions normales |
| wet      | recharge forte      |

Les prévisions sont calculées **de manière itérative jour par jour**.

Sortie :

```
data/processed/forecast_scenarios.csv
```

---

# Interface utilisateur — Streamlit

L'application permet de :

### Visualisation

* historique du niveau de nappe
* prévision du niveau

### Paramètres interactifs

* scénario météo
* horizon de prévision
* seuil critique

### Détection d’alerte

Le système détecte si :

```
niveau_nappe < seuil
```

et affiche :

* un message d’alerte
* les dates concernées

---

# Lancer l'application

```
streamlit run app/streamlit_app.py
```

L'application sera accessible sur :

```
http://localhost:8501
```

---

# Résumé scientifique

Le modèle apprend une relation de type :

```
niveau(t+1) = f(
    niveau passé,
    pluie,
    evapotranspiration,
    saison
)
```

Ce qui correspond au fonctionnement hydrologique simplifié :

```
Recharge = pluie
Perte = evapotranspiration
Stockage = nappe
```

---

# Perspectives d’amélioration

Plusieurs améliorations sont possibles :

* modèle **LSTM**
* scénarios climatiques probabilistes
* assimilation de données
* interface web avancée
* connexion temps réel Hub’Eau
* système d’alerte automatisé

---

# Licence

Projet de recherche / démonstration scientifique.
