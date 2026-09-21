# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 05a — Exploration des données (EDA)
# MAGIC
# MAGIC Étape 1/5 du projet ML : **Exploration → Nettoyage → Analyse → Features → Modèle**
# MAGIC
# MAGIC Objectif ici : comprendre la donnée brute avant d'y toucher. Pas de
# MAGIC transformation dans ce notebook, uniquement de l'observation.

# COMMAND ----------

gold_base = "/Volumes/pfa_data/gold_data/gold"

import pandas as pd
import numpy as np

df = spark.read.format("delta").load(f"{gold_base}/gold_ml_features_transaction").toPandas()
print(f"Dimensions : {df.shape[0]:,} lignes x {df.shape[1]} colonnes")
df.head()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Vue d'ensemble des colonnes et types

# COMMAND ----------

df.info()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Valeurs manquantes

# COMMAND ----------

missing = df.isnull().sum()
missing_pct = (missing / len(df) * 100).round(2)
missing_df = pd.DataFrame({"nb_manquants": missing, "pct_manquants": missing_pct})
missing_df[missing_df["nb_manquants"] > 0].sort_values("pct_manquants", ascending=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Déséquilibre de classes (le point central du projet)

# COMMAND ----------

taux_fraude = df["fraud_flag"].mean()
print(f"Transactions normales : {(df['fraud_flag']==0).sum():,} ({(1-taux_fraude)*100:.2f}%)")
print(f"Transactions frauduleuses : {(df['fraud_flag']==1).sum():,} ({taux_fraude*100:.2f}%)")
print(f"Ratio normal:fraude ≈ {(1-taux_fraude)/taux_fraude:.0f} : 1")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Statistiques descriptives des variables numériques

# COMMAND ----------

FEATURES_NUM = [
    "montant", "frais_transaction", "montant_moyen_client_30j",
    "ecart_type_client_30j", "nb_transactions_client_30j",
    "ecart_relatif_montant", "montant_cumule_client", "age",
    "revenu_mensuel", "score_credit", "ratio_montant_revenu",
    "taux_utilisation_30j",
]

df[FEATURES_NUM].describe().T

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Distribution des variables numériques : fraude vs normal
# MAGIC
# MAGIC Comparaison de la moyenne/médiane par classe — un premier indice de quelles
# MAGIC variables séparent (ou pas) les deux populations.

# COMMAND ----------

comparaison = df.groupby("fraud_flag")[FEATURES_NUM].agg(["mean", "median"]).T
comparaison.columns = ["Normal", "Fraude"]
comparaison

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Variables catégorielles : taux de fraude par modalité

# COMMAND ----------

FEATURES_CAT = [
    "type_transaction", "canal", "mode_paiement", "sens_operation",
    "segment_client", "tranche_revenu", "niveau_risque_client", "tranche_horaire",
]

for col in FEATURES_CAT:
    print(f"\n--- {col} ---")
    print(
        df.groupby(col)["fraud_flag"]
        .agg(nb="count", taux_fraude="mean")
        .sort_values("taux_fraude", ascending=False)
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Variables binaires de contexte : is_night, is_weekend, est_international, hors_agence

# COMMAND ----------

for col in ["is_night", "is_weekend", "est_international", "hors_agence"]:
    print(f"\n--- {col} ---")
    print(df.groupby(col)["fraud_flag"].agg(nb="count", taux_fraude="mean"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Corrélations entre variables numériques

# COMMAND ----------

corr = df[FEATURES_NUM + ["fraud_flag"]].corr()
corr["fraud_flag"].sort_values(ascending=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Doublons et cohérence

# COMMAND ----------

print(f"Doublons sur transaction_id : {df['transaction_id'].duplicated().sum()}")
print(f"Montants négatifs ou nuls    : {(df['montant'] <= 0).sum()}")
print(f"Âges hors plage [18-100]     : {((df['age'] < 18) | (df['age'] > 100)).sum()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Synthèse après lecture des résultats
# MAGIC
# MAGIC
# MAGIC - **Valeurs manquantes à traiter** :
# MAGIC   - `mode_paiement` : **59,98%** manquant → imputation ou suppression de cette variable ?
# MAGIC   - `age` : **18,26%** manquant → imputation par médiane ou KNN recommandée
# MAGIC
# MAGIC - **Déséquilibre de classes** :
# MAGIC   - Fraude : **1,21%** (2 419 cas) vs Normal : **98,79%** (197 581 cas)
# MAGIC   - Ratio de **82:1** → nécessitera un traitement spécifique (SMOTE, sous-échantillonnage, poids de classe)
# MAGIC
# MAGIC - **Variables qui semblent discriminantes** (à conserver) :
# MAGIC   - `montant` : corrélation **0,147** avec fraud_flag ; montant moyen fraude **5 728** vs normal **1 482**
# MAGIC   - `frais_transaction` : corrélation **0,107** ; fraude **13,67** vs normal **3,02**
# MAGIC   - `ratio_montant_revenu` : corrélation **0,091** ; fraude **1,32** vs normal **0,36**
# MAGIC   - `ecart_relatif_montant` et `taux_utilisation_30j` : corrélation **0,073** chacun
# MAGIC   - `is_night` : taux de fraude **1,58%** (nuit) vs **1,17%** (jour)
# MAGIC   - `tranche_horaire` : Nuit (**1,45%**) plus risqué que les autres moments
# MAGIC
# MAGIC - **Variables qui ne semblent PAS discriminantes** (corrélation proche de 0) :
# MAGIC   - `age`, `revenu_mensuel`, `score_credit`, `nb_transactions_client_30j`
# MAGIC   - `is_weekend` : pas de différence significative entre semaine et week-end
# MAGIC   - La plupart des variables catégorielles (`segment_client`, `tranche_revenu`, etc.) ont des taux de fraude similaires entre modalités (~1,1-1,3%)
# MAGIC
# MAGIC - **Anomalies détectées** :
# MAGIC   - ✅ **Aucun doublon** sur `transaction_id`
# MAGIC   - ✅ **Aucun montant négatif ou nul**
# MAGIC   - ✅ **Aucun âge aberrant** (hors [18-100])
# MAGIC   - ⚠️ Le fort taux de valeurs manquantes sur `mode_paiement` (60%) questionne la qualité de cette variable

# COMMAND ----------

