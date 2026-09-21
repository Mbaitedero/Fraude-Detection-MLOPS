# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Couche Gold – Features Machine Learning
# MAGIC
# MAGIC Ce notebook est désormais recentré uniquement sur le Machine Learning :
# MAGIC il construit `gold_ml_features_transaction`, la table au grain transaction
# MAGIC utilisée pour entraîner le modèle de détection de fraude.
# MAGIC
# MAGIC Les tables BI (`fact_transactions`, `dim_client`, `dim_agence`, `dim_temps`)
# MAGIC sont désormais gérées dans le notebook `03_gold_bi`, séparément.
# MAGIC
# MAGIC **Chemins** :
# MAGIC - Silver : `/Volumes/pfa_data/silver_data/silver`
# MAGIC - Gold   : `/Volumes/pfa_data/gold_data/gold`

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuration

# COMMAND ----------

silver_base = "/Volumes/pfa_data/silver_data/silver"
gold_base   = "/Volumes/pfa_data/gold_data/gold"

from pyspark.sql.functions import col, when

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Lecture des tables Silver

# COMMAND ----------

transactions_silver = spark.read.format("delta").load(f"{silver_base}/silver_transactions")
clients_silver      = spark.read.format("delta").load(f"{silver_base}/silver_clients")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Table Gold – Features pour Machine Learning (grain transaction)
# MAGIC
# MAGIC ⚠️ **Anti data-leakage** : `fraud_flag` est conservé comme **label** (colonne
# MAGIC cible), mais `fraud_type` et `fraud_rule_triggered` sont volontairement
# MAGIC exclus de cette table — ce sont des informations de vérité terrain générées
# MAGIC après coup, qu'un modèle ne devrait jamais voir en entrée.

# COMMAND ----------

clients_extra = clients_silver.select(
    "client_id",
    col("score_credit"),
    col("niveau_risque_client"),
)

ml_features = transactions_silver.join(
    clients_extra, on="client_id", how="left"
).select(
    # Identifiants
    col("transaction_id"),
    col("client_id"),
    col("compte_touche"),
    col("agence_id"),
    # Date/heure
    col("date_transaction"),
    col("heure"),
    col("tranche_horaire"),
    col("jour_semaine"),
    col("is_weekend"),
    col("is_night"),
    # Montants et frais
    col("montant"),
    col("frais_transaction"),
    # Caractéristiques de la transaction
    col("type_transaction"),
    col("canal"),
    col("mode_paiement"),
    col("est_international"),
    col("hors_agence"),
    col("sens_operation"),
    # Device et IP
    col("device_id"),
    col("ip_address"),
    # Features rolling (déjà présentes dans transactions_silver)
    col("montant_moyen_client_30j"),
    col("ecart_type_client_30j"),
    col("nb_transactions_client_30j"),
    col("ecart_relatif_montant"),
    col("montant_cumule_client"),
    # Informations client
    col("age"),
    col("segment_client"),
    col("tranche_revenu"),
    col("revenu_mensuel"),
    col("score_credit"),
    col("niveau_risque_client"),
    # Label (à ne jamais traiter comme feature d'entrée)
    col("fraud_flag"),
)

ml_features = ml_features.withColumn(
    "ratio_montant_revenu",
    when(col("revenu_mensuel") != 0, col("montant") / col("revenu_mensuel")).otherwise(0.0),
).withColumn(
    "taux_utilisation_30j",
    when(col("montant_moyen_client_30j") != 0, col("montant") / col("montant_moyen_client_30j")).otherwise(1.0),
)

ml_features.write.format("delta").mode("overwrite").save(f"{gold_base}/gold_ml_features_transaction")
print(f"✅ gold_ml_features_transaction créée — {ml_features.count():,} lignes")

# COMMAND ----------

display(ml_features.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Enregistrement dans le catalogue (optionnel, pour requêtage SQL/EDA)

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS pfa_data.pfa_gold;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE pfa_data.pfa_gold.gold_ml_features_transaction
# MAGIC AS SELECT * FROM delta.`/Volumes/pfa_data/gold_data/gold/gold_ml_features_transaction`;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Vérifications

# COMMAND ----------

taux_fraude = ml_features.selectExpr("avg(fraud_flag) as taux").collect()[0]["taux"]
print(f"Lignes                : {ml_features.count():,}")
print(f"Colonnes              : {len(ml_features.columns)}")
print(f"Taux de fraude (label): {taux_fraude * 100:.2f}%")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Résumé
# MAGIC
# MAGIC | Table | Grain | Utilisation |
# MAGIC | :--- | :--- | :--- |
# MAGIC | `gold_ml_features_transaction` | transaction | Entraînement du modèle de détection de fraude |
# MAGIC
# MAGIC

# COMMAND ----------

