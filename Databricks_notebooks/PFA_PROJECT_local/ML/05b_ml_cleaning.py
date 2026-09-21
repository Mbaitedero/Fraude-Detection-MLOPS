# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 05b — Nettoyage des données
# MAGIC
# MAGIC Étape 2/5 : Exploration → **Nettoyage** → Analyse → Features → Modèle
# MAGIC
# MAGIC Décisions prises suite à l'exploration :
# MAGIC - `mode_paiement` : le manque semble structurel (lié au type de transaction),
# MAGIC   vérifié ci-dessous avant de trancher entre imputation par catégorie
# MAGIC   explicite ou suppression.
# MAGIC - `age` : imputation par médiane + indicateur binaire de valeur manquante.

# COMMAND ----------

gold_base = "/Volumes/pfa_data/gold_data/gold"

import pandas as pd
import numpy as np

df = spark.read.format("delta").load(f"{gold_base}/gold_ml_features_transaction").toPandas()
print(f"Dimensions avant nettoyage : {df.shape[0]:,} lignes x {df.shape[1]} colonnes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Vérifier si le manque de `mode_paiement` est structurel

# COMMAND ----------

print("Répartition de type_transaction selon que mode_paiement est renseigné ou non :\n")
print(
    df.assign(mode_paiement_renseigne=df["mode_paiement"].notna())
    .groupby(["type_transaction", "mode_paiement_renseigne"])
    .size()
    .unstack(fill_value=0)
)

# COMMAND ----------

# MAGIC %md
# MAGIC Si le tableau ci-dessus montre que `mode_paiement` n'est jamais renseigné pour
# MAGIC certains `type_transaction` (ex: Virement, Retrait) et toujours renseigné pour
# MAGIC d'autres (ex: Paiement), le manque est structurel → on impute par une
# MAGIC catégorie explicite plutôt que de supprimer la variable ou d'imputer au hasard.

# COMMAND ----------

df["mode_paiement"] = df["mode_paiement"].fillna("Non_applicable")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Traitement de `age`

# COMMAND ----------

df["age_manquant"] = df["age"].isna().astype(int)
mediane_age = df["age"].median()
df["age"] = df["age"].fillna(mediane_age)
print(f"Âge imputé par la médiane : {mediane_age}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Vérifier les autres colonnes potentiellement manquantes
# MAGIC
# MAGIC (`score_credit`, `niveau_risque_client` viennent d'une jointure avec
# MAGIC `clients_silver` — si des `client_id` ne correspondent pas, ces colonnes
# MAGIC peuvent contenir des NaN même si l'exploration initiale ne les a pas signalées
# MAGIC en tête de liste)

# COMMAND ----------

missing_apres = df.isnull().sum()
missing_apres = missing_apres[missing_apres > 0]
print("Colonnes encore manquantes après étapes 1-2 :")
print(missing_apres if len(missing_apres) > 0 else "Aucune ✅")

# COMMAND ----------

if "score_credit" in missing_apres.index:
    df["score_credit"] = df["score_credit"].fillna(df["score_credit"].median())
if "niveau_risque_client" in missing_apres.index:
    df["niveau_risque_client"] = df["niveau_risque_client"].fillna("Inconnu")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Vérification finale

# COMMAND ----------

missing_final = df.isnull().sum().sum()
print(f"Dimensions après nettoyage : {df.shape[0]:,} lignes x {df.shape[1]} colonnes")
print(f"Total valeurs manquantes restantes : {missing_final}")
assert missing_final == 0, "Il reste des valeurs manquantes non traitées !"
print("✅ Aucune valeur manquante restante")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Sauvegarde de la table nettoyée
# MAGIC
# MAGIC Persistée comme table Gold séparée — la table source
# MAGIC `gold_ml_features_transaction` n'est pas modifiée (traçabilité : on peut
# MAGIC toujours remonter à la donnée brute).

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP SCHEMA IF EXISTS pfa_data.ml_outputs CASCADE;

# COMMAND ----------


spark.createDataFrame(df).write.format("delta").mode("overwrite").saveAsTable(
    "pfa_data.ml_outputs.gold_ml_features_clean"
)
print("✅ gold_ml_features_clean sauvegardée")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Résumé des décisions de nettoyage
# MAGIC
# MAGIC | Variable | Problème | Traitement |
# MAGIC | :--- | :--- | :--- |
# MAGIC | `mode_paiement` | 59,98% manquant | Imputé par `"Non_applicable"` (manque structurel, cf. section 1) |
# MAGIC | `age` | 18,26% manquant | Médiane + indicateur `age_manquant` |
# MAGIC | `score_credit` / `niveau_risque_client` | Manques résiduels (jointure client) | Médiane / `"Inconnu"` |
# MAGIC
# MAGIC **Prochaine étape** : notebook `05c_ml_analyse` — analyse approfondie des
# MAGIC variables jugées discriminantes (dont `hors_agence` à vérifier).