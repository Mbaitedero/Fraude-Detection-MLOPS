# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 06 — Scoring batch (modèle `champion`)
# MAGIC
# MAGIC Dernière brique du périmètre MLOps : Tracking ✅ → Registry ✅ → **Batch
# MAGIC scoring** → Airflow.
# MAGIC
# MAGIC Ce notebook simule ce qui tournerait en production : charger le modèle
# MAGIC actuellement promu `champion` (pas une version codée en dur — si un futur
# MAGIC run promeut un meilleur modèle, ce notebook l'utilisera automatiquement sans
# MAGIC modification), appliquer le même feature engineering qu'à l'entraînement, et
# MAGIC scorer de nouvelles transactions.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuration et chargement du modèle `champion`

# COMMAND ----------

import mlflow
from mlflow.tracking import MlflowClient

mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()

CATALOG = "pfa_data"
SCHEMA = "ml_outputs"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.fraud_detection_model"

# Vérifier et configurer l'alias champion si nécessaire
try:
    champion_version = client.get_model_version_by_alias(MODEL_NAME, "champion")
    print(f"ℹ️ Alias champion pointe vers version {champion_version.version}")
except:
    # L'alias n'existe pas ou pointe vers une version supprimée — le définir sur la dernière version
    versions = client.search_model_versions(f"name='{MODEL_NAME}'")
    if versions:
        latest_version = max(versions, key=lambda v: int(v.version))
        client.set_registered_model_alias(MODEL_NAME, "champion", latest_version.version)
        print(f"✅ Alias champion défini sur version {latest_version.version}")
        champion_version = client.get_model_version_by_alias(MODEL_NAME, "champion")
    else:
        raise ValueError(f"Aucune version du modèle {MODEL_NAME} trouvée")

model_uri = f"models:/{MODEL_NAME}@champion"
model = mlflow.sklearn.load_model(model_uri)

print(f"✅ Modèle chargé : {MODEL_NAME}, version {champion_version.version} (alias champion)")
print(f"   Run source : {champion_version.run_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Chargement de l'encodeur (le même qu'à l'entraînement, pas un nouveau)

# COMMAND ----------

import joblib

ENCODER_PATH = "/Workspace/Users/allahjaphet9@gmail.com/PFA_PROJECT/ML/pfa_data.ml_outputs.ml_ordinal_encoder.joblib"
encoder = joblib.load(ENCODER_PATH)

FEATURES_CAT = list(encoder.feature_names_in_)
print(f"✅ Encodeur chargé — catégories connues : {len(encoder.categories_)} colonnes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Chargement des transactions à scorer
# MAGIC
# MAGIC En production, cette requête filtrerait sur les transactions du batch/jour
# MAGIC en cours (ex: `WHERE date_transaction = current_date()`). Pour cette
# MAGIC démonstration, on score l'ensemble de `gold_ml_features_clean` afin de
# MAGIC pouvoir comparer aux vrais labels et valider le scoring.

# COMMAND ----------

model_info = mlflow.models.get_model_info(model_uri)
FEATURES_FINALES = [inp.name for inp in model_info.signature.inputs.inputs]
print(f"✅ {len(FEATURES_FINALES)} features attendues par le modèle (depuis sa signature) :")
print(FEATURES_FINALES)

# COMMAND ----------

manquantes = set(FEATURES_CAT) - set(FEATURES_FINALES)
if manquantes:
    raise ValueError(f"Incohérence encodeur/modèle : {manquantes} absentes de la signature du modèle")
print("✅ Cohérence encodeur ↔ modèle vérifiée")

# COMMAND ----------

df_new = spark.table(f"{CATALOG}.{SCHEMA}.gold_ml_features_clean").toPandas()
print(f"Transactions à scorer : {len(df_new):,}")

# COMMAND ----------

colonnes_manquantes = set(FEATURES_FINALES) - set(df_new.columns)
if colonnes_manquantes:
    raise ValueError(f"Colonnes manquantes dans les données à scorer : {colonnes_manquantes}")

# COMMAND ----------



# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Feature engineering identique à l'entraînement
# MAGIC
# MAGIC ⚠️ On réutilise l'encodeur chargé (`transform`, jamais `fit_transform`) —
# MAGIC toute nouvelle modalité inconnue est encodée à -1 (`handle_unknown`), pas
# MAGIC d'erreur, mais à surveiller si ça devient fréquent (dérive de données).

# COMMAND ----------

# 1. Sélectionner les features catégorielles dans le BON ORDRE
X_new = df_new[FEATURES_FINALES].copy()
X_new[FEATURES_CAT] = X_new[FEATURES_CAT].fillna("Inconnu")

# 2. S'assurer que les colonnes sont dans l'ordre attendu par l'encodeur
X_new[FEATURES_CAT] = X_new[FEATURES_CAT][FEATURES_CAT]   # ← même ordre

# 3. Transformer
X_new[FEATURES_CAT] = encoder.transform(X_new[FEATURES_CAT])

# 4. Vérifier les modalités inconnues
nb_modalites_inconnues = (X_new[FEATURES_CAT] == -1).sum().sum()
if nb_modalites_inconnues > 0:
    print(f"⚠️ {nb_modalites_inconnues} valeurs avec une modalité inconnue (encodées -1)")
else:
    print("✅ Aucune modalité inconnue")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Scoring

# COMMAND ----------

import numpy as np
import pandas as pd

y_proba = model.predict_proba(X_new)[:, 1]

SEUIL_DECISION = 0.5  # à remplacer par best_threshold_f1 du run si tu veux le seuil optimal métier

resultats = pd.DataFrame({
    "transaction_id": df_new["transaction_id"].values,
    "client_id": df_new["client_id"].values,
    "montant": df_new["montant"].values,
    "fraud_proba": y_proba,
    "fraud_predicted": (y_proba >= SEUIL_DECISION).astype(int),
    "fraud_flag_reel": df_new["fraud_flag"].values,  # gardé pour cette démo uniquement (comparaison)
    "model_version": champion_version.version,
    "date_scoring": pd.Timestamp.now(),
})

print(f"Transactions scorées         : {len(resultats):,}")
print(f"Transactions signalées fraude : {resultats['fraud_predicted'].sum():,} ({resultats['fraud_predicted'].mean()*100:.2f}%)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Sauvegarde des scores

# COMMAND ----------

spark.createDataFrame(resultats).write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.{SCHEMA}.fraud_scores_batch"
)
print(f"✅ {CATALOG}.{SCHEMA}.fraud_scores_batch sauvegardée")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Contrôle de cohérence (uniquement possible ici car on connaît le vrai label)
# MAGIC
# MAGIC En production réelle, cette section n'existerait pas au moment du scoring
# MAGIC (le label n'est connu qu'après coup) — elle sert uniquement à vérifier que
# MAGIC le scoring batch reproduit bien les performances mesurées à l'entraînement.

# COMMAND ----------

from sklearn.metrics import classification_report

print(classification_report(
    resultats["fraud_flag_reel"], resultats["fraud_predicted"],
    target_names=["Normal", "Fraude"]
))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Résumé
# MAGIC
# MAGIC | Élément | Valeur |
# MAGIC | :--- | :--- |
# MAGIC | Modèle utilisé | `fraud_detection_model@champion` (version affichée en section 1) |
# MAGIC | Table de sortie | `pfa_data.ml_outputs.fraud_scores_batch` |
# MAGIC
# MAGIC
# MAGIC