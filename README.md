# Digital Twin Groundwater  
## Piézomètre & Prévision du niveau de nappe

## Description

Ce projet implémente un **digital twin simplifié de nappe phréatique** permettant de suivre et prévoir l’évolution du niveau d’un piézomètre à partir de données hydrométéorologiques.

Le système combine :

- les observations **piézométriques Hub’Eau (ADES)**
- les données météorologiques **SAFRAN (Météo-France)**
- un modèle de **régression linéaire**
- une interface interactive **Streamlit**

L’application permet d’explorer le comportement de la nappe et de tester différents **scénarios météorologiques**, tout en détectant automatiquement les **épisodes critiques de baisse du niveau de nappe**.

Ce projet constitue une **preuve de concept (PoC)** d’un **digital twin hydrologique appliqué aux eaux souterraines**.

---

# Fonctionnalités principales

L’application Streamlit propose deux interfaces principales.

---

# 1 — Dashboard

Le dashboard permet d’analyser la situation actuelle.

## Visualisation

- historique du niveau de nappe
- prévisions selon plusieurs scénarios météorologiques
- cumul mensuel pluie / évapotranspiration

## Paramètres interactifs

- scénario météorologique (dry / medium / wet)
- horizon de prévision
- seuil critique de niveau

## État de la nappe

Un indicateur synthétique affiche :
🟢 Safe level
🔴 Groundwater critical level reached


selon la condition :
niveau_nappe > seuil


## Détection d’alertes

Le système identifie automatiquement les **épisodes de franchissement de seuil** et génère un tableau :

Date début | Date fin | Nombre de jours | Niveau minimum


---

# 2 — Simulation temps réel

Une seconde interface permet de simuler l’évolution du niveau de nappe sur **une année hydrologique**.

La simulation :

- avance **jour par jour**
- affiche l’évolution du niveau par rapport à un **seuil fictif**
- colore la courbe :


vert : niveau au-dessus du seuil
rouge : niveau sous le seuil


Lorsque la nappe passe sous le seuil :

- l’indicateur d’état devient **critique**
- un **épisode d’alerte est enregistré automatiquement**

Le tableau **Historique des alertes** se construit progressivement au cours de la simulation.

---

# Architecture du projet


digital_twin_groundwater/
│
├── app/
│ └── streamlit_app.py # interface utilisateur
│
├── data/
│ ├── raw/
│ │ ├── piezo_*.csv
│ │ └── meteo_daily.csv
│ │
│ └── processed/
│ ├── dataset_daily.csv
│ └── forecast_scenarios.csv
│
├── models/
│ └── model.joblib
│
├── scripts/
│ ├── 01_download_piezo.py
│ ├── 02_get_meteo_template.py
│ ├── 03_build_dataset.py
│ ├── 04_train_model.py
│ └── 05_forecast_and_scenarios.py
│
├── config.json
├── requirements.txt
└── README.md


---

# Pipeline du projet

Le pipeline de traitement comprend **5 étapes principales**.

---

# 1 — Téléchargement des données piézométriques

Script :


scripts/01_download_piezo.py


Source :

**API Hub’Eau / ADES**

Variables récupérées :

- niveau de nappe
- profondeur
- date de mesure

Sortie :


data/raw/piezo_CODEBSS.csv


---

# 2 — Téléchargement des données météorologiques

Script :


scripts/02_get_meteo_template.py


Source :

**SAFRAN-ISBA — Météo-France**

Variables utilisées :

| Variable | Description |
|--------|-------------|
| PRELIQ_Q | précipitations liquides |
| PRENEI_Q | précipitations solides |
| ETP_Q | évapotranspiration potentielle |

Pluie totale :


pluie = PRELIQ_Q + PRENEI_Q


Sortie :


data/raw/meteo_daily.csv


Format :


date,pluie_mm,etp_mm
1990-01-01,0.6,0.4
1990-01-02,0.0,0.4


---

# 3 — Construction du dataset

Script :


scripts/03_build_dataset.py


Cette étape :

- aligne les séries temporelles
- fusionne **piézo + météo**
- génère des **features hydrologiques**

## Mémoire de la nappe


niveau_lag_1
niveau_lag_2
niveau_lag_3
niveau_lag_7
niveau_lag_14
niveau_lag_30


## Recharge climatique


pluie_sum_7
pluie_sum_14
pluie_sum_30


## Evapotranspiration


etp_sum_7
etp_sum_14
etp_sum_30


## Saison


month
doy


Sortie :


data/processed/dataset_daily.csv


---

# 4 — Entraînement du modèle

Script :


scripts/04_train_model.py


Modèle :


LinearRegression (scikit-learn)


Découpage des données :


80 % train
20 % test


Métriques :

- MAE
- R²

Le modèle est sauvegardé :


models/model.joblib


---

# 5 — Génération de prévisions

Script :


scripts/05_forecast_and_scenarios.py


Scénarios générés :

| Scénario | Description |
|--------|-------------|
| dry | sécheresse |
| medium | conditions normales |
| wet | recharge importante |

Les prévisions sont calculées **itérativement jour par jour**.

Sortie :


data/processed/forecast_scenarios.csv


---

# Lancer l'application


streamlit run app/streamlit_app.py


L'application sera accessible sur :


http://localhost:8501


---

# Formulation hydrologique simplifiée

Le modèle apprend une relation du type :


niveau(t+1) = f(
niveau(t),
pluie,
evapotranspiration,
saison
)


Conceptuellement :


Recharge = pluie
Perte = evapotranspiration
Stockage = nappe


---

# Perspectives d'amélioration

- modèles **LSTM / deep learning**
- scénarios météorologiques **probabilistes**
- assimilation de données
- connexion **temps réel Hub’Eau**
- système d’alerte automatisé
- extension à plusieurs piézomètres
- interface web avancée

---

# Licence

Projet de recherche / démonstration scientifique.
