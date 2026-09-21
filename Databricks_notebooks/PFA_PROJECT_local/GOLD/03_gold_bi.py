# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Couche Gold – Schéma en étoile pour Power BI
# MAGIC
# MAGIC - `fact_transactions` : grain = 1 ligne par transaction
# MAGIC - `fact_credits`      : grain = 1 ligne par crédit (avec sa classification réglementaire)
# MAGIC - `fact_liquidite`    : grain = 1 ligne par ratio calculé (période × niveau de consolidation)
# MAGIC - `dim_client`        : 1 ligne par client
# MAGIC - `dim_agence`        : 1 ligne par agence — **partagée** par les 3 faits
# MAGIC - `dim_temps`         : 1 ligne par jour, jointe sur `date_key` (entier `yyyyMMdd`) — **partagée** par les 3 faits
# MAGIC
# MAGIC ⚠️ `fact_liquidite` : pour les lignes `niveau_consolidation` = BANQUE/GROUPE,
# MAGIC `agence_id` est NULL (ratio consolidé, non rattaché à une agence) — la
# MAGIC relation vers `dim_agence` est donc partielle pour ce fait, contrairement aux
# MAGIC deux autres. C'est normal, pas une anomalie de données.
# MAGIC
# MAGIC Toutes les agrégations (taux de fraude par mois, volume par canal, etc.)
# MAGIC se font côté Power BI via des mesures DAX, plutôt que d'être figées ici.
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

from pyspark.sql.functions import (
    col, year, month, dayofmonth, dayofweek, date_format, when, ceil, explode
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Lecture des tables Silver

# COMMAND ----------

clients_silver        = spark.read.format("delta").load(f"{silver_base}/silver_clients")
agences_silver        = spark.read.format("delta").load(f"{silver_base}/silver_agences")
transactions_silver   = spark.read.format("delta").load(f"{silver_base}/silver_transactions")
credits_silver        = spark.read.format("delta").load(f"{silver_base}/silver_credits")
classification_silver = spark.read.format("delta").load(f"{silver_base}/silver_classification_creances")
ratios_silver         = spark.read.format("delta").load(f"{silver_base}/silver_ratios_liquidite")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Dimension Client (`dim_client`)
# MAGIC
# MAGIC Grain : 1 ligne par `client_id`. Attributs descriptifs uniquement (pas de mesures).

# COMMAND ----------

dim_client = clients_silver.select(
    "client_id",
    "type_client",
    "civilite",
    "nom_complet",
    "age",
    "ville",
    "region",
    "segment_client",
    "tranche_revenu",
    "revenu_mensuel",
    "score_credit",
    "niveau_risque_client",
    "statut_client",
    "anciennete_annees",
    "agence_id",
).dropDuplicates(["client_id"])

dim_client.write.format("delta").mode("overwrite").save(f"{gold_base}/dim_client")
print(f"✅ dim_client créée — {dim_client.count():,} clients")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Dimension Agence (`dim_agence`)
# MAGIC
# MAGIC Grain : 1 ligne par `agence_id`.

# COMMAND ----------

dim_agence = agences_silver.select(
    "agence_id",
    "nom_agence",
    "ville",
    "region",
    "type_agence",
    "date_ouverture",
).dropDuplicates(["agence_id"])

dim_agence.write.format("delta").mode("overwrite").save(f"{gold_base}/dim_agence")
print(f"✅ dim_agence créée — {dim_agence.count():,} agences")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Dimension Temps (`dim_temps`)
# MAGIC
# MAGIC Grain : 1 ligne par jour. Clé de jointure `date_key` (entier `yyyyMMdd`),
# MAGIC plus fiable qu'un texte `mois_annee` pour la relation avec le fait.

# COMMAND ----------

start_date = "2020-01-01"
end_date   = "2026-12-31"

dates_df = spark.range(1).selectExpr(
    f"sequence(to_date('{start_date}'), to_date('{end_date}'), interval 1 day) as date"
)
dates_df = dates_df.select(explode("date").alias("date"))

dim_temps = (
    dates_df
    .withColumn("date_key", date_format("date", "yyyyMMdd").cast("int"))
    .withColumn("annee", year("date"))
    .withColumn("trimestre", ceil(month("date") / 3))
    .withColumn("mois", month("date"))
    .withColumn("jour", dayofmonth("date"))
    .withColumn("jour_semaine", dayofweek("date"))
    .withColumn("nom_mois", date_format("date", "MMMM"))
    .withColumn("mois_annee", date_format("date", "yyyy-MM"))
    .withColumn("est_weekend", when(col("jour_semaine").isin([1, 7]), 1).otherwise(0))
)

dim_temps.write.format("delta").mode("overwrite").save(f"{gold_base}/dim_temps")
print(f"✅ dim_temps créée — {dim_temps.count():,} jours")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Fait Transactions (`fact_transactions`)
# MAGIC
# MAGIC Grain : 1 ligne par transaction. Contient les clés étrangères vers les 3
# MAGIC dimensions + les mesures/attributs de contexte (montant, canal, indicateurs
# MAGIC de fraude...). `fraud_flag` est conservé ici pour le monitoring BI — ce n'est
# MAGIC que dans la table ML (`gold_ml_features_transaction`, notebook 04) qu'il ne
# MAGIC doit surtout pas être utilisé comme variable explicative.

# COMMAND ----------

fact_transactions = transactions_silver.select(
    "transaction_id",
    "client_id",
    "agence_id",
    date_format("date_transaction", "yyyyMMdd").cast("int").alias("date_key"),
    "date_transaction",   
    "montant",
    "frais_transaction",
    "canal",
    "type_transaction",
    "mode_paiement",
    "sens_operation",
    "est_international",
    "is_weekend",
    "is_night",
    "hors_agence",
    "fraud_flag",
    "fraud_type",
    "fraud_rule_triggered",
)

fact_transactions.write.format("delta").mode("overwrite").save(f"{gold_base}/fact_transactions")
print(f"✅ fact_transactions créée — {fact_transactions.count():,} transactions")

# COMMAND ----------

display(fact_transactions.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Fait Crédits (`fact_credits`)
# MAGIC
# MAGIC Grain : 1 ligne par crédit. Jointure entre `silver_credits` (données du prêt)
# MAGIC et `silver_classification_creances` (classification réglementaire, PD/LGD/EAD,
# MAGIC provisions) — les deux tables partagent `credit_id`, une classification par
# MAGIC crédit à la date de calcul la plus récente.

# COMMAND ----------

fact_credits = credits_silver.select(
    "credit_id",
    "client_id",
    "agence_id",
    date_format("date_octroi", "yyyyMMdd").cast("int").alias("date_key"),
    "type_credit",
    "montant_initial",
    "montant_restant_du",
    "taux_interet_nominal",
    "duree_totale_mois",
    "duree_restante_mois",
    "montant_mensualite",
    "jours_retard",
    "statut_credit",
    "classification_bale",
    "provision_constituee",
).join(
    classification_silver.select(
        "credit_id",
        "categorie_reglementaire",
        "categorie_bale_ii",
        "categorie_ifrs9",
        "probabilite_defaut_pd",
        "perte_en_cas_defaut_lgd",
        "exposition_en_cas_defaut_ead",
        "perte_attendue_el",
        "provision_requise",
        "taux_provisionnement",
    ),
    on="credit_id",
    how="left",
)

fact_credits.write.format("delta").mode("overwrite").save(f"{gold_base}/fact_credits")
print(f"✅ fact_credits créée — {fact_credits.count():,} crédits")

# COMMAND ----------

display(fact_credits.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Fait Liquidité (`fact_liquidite`)
# MAGIC
# MAGIC Grain : 1 ligne par ratio calculé (une période × un niveau de consolidation,
# MAGIC éventuellement une agence). `agence_id` est NULL pour les niveaux
# MAGIC BANQUE/GROUPE — voir la remarque en tête de notebook.

# COMMAND ----------

fact_liquidite = ratios_silver.select(
    "ratio_id",
    "agence_id",
    date_format("date_calcul", "yyyyMMdd").cast("int").alias("date_key"),
    "niveau_consolidation",
    "type_ratio",
    "lcr_ratio",
    "lcr_conforme",
    "nsfr_ratio",
    "nsfr_conforme",
    "depot_total",
    "credit_total",
    "ratio_credit_depot",
    "statut_global",
    "alerte_niveau",
)

fact_liquidite.write.format("delta").mode("overwrite").save(f"{gold_base}/fact_liquidite")
print(f"✅ fact_liquidite créée — {fact_liquidite.count():,} lignes")

# COMMAND ----------

display(fact_liquidite.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Enregistrement dans le catalogue (Unity Catalog)
# MAGIC
# MAGIC Nécessaire pour que Power BI (via le SQL Warehouse) voie ces tables dans le
# MAGIC Navigator — un `.save(path)` seul ne suffit pas, il faut un objet catalogué.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS pfa_data.pfa_gold;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE pfa_data.pfa_gold.dim_client
# MAGIC AS SELECT * FROM delta.`/Volumes/pfa_data/gold_data/gold/dim_client`;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE pfa_data.pfa_gold.dim_agence
# MAGIC AS SELECT * FROM delta.`/Volumes/pfa_data/gold_data/gold/dim_agence`;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE pfa_data.pfa_gold.dim_temps
# MAGIC AS SELECT * FROM delta.`/Volumes/pfa_data/gold_data/gold/dim_temps`;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE pfa_data.pfa_gold.fact_transactions
# MAGIC AS SELECT * FROM delta.`/Volumes/pfa_data/gold_data/gold/fact_transactions`;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE pfa_data.pfa_gold.fact_credits
# MAGIC AS SELECT * FROM delta.`/Volumes/pfa_data/gold_data/gold/fact_credits`;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE pfa_data.pfa_gold.fact_liquidite
# MAGIC AS SELECT * FROM delta.`/Volumes/pfa_data/gold_data/gold/fact_liquidite`;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Vérifications d'intégrité référentielle

# COMMAND ----------

nb_transactions = fact_transactions.count()
nb_client_orphelins = fact_transactions.join(
    dim_client, on="client_id", how="left_anti"
).count()
nb_agence_orphelines = fact_transactions.join(
    dim_agence, on="agence_id", how="left_anti"
).count()
nb_date_orphelines = fact_transactions.join(
    dim_temps, on="date_key", how="left_anti"
).count()

print("Contrôles d'intégrité référentielle :")
print(f"  Transactions totales           : {nb_transactions:,}")
print(f"  Transactions sans client (orph): {nb_client_orphelins:,}")
print(f"  Transactions sans agence (orph): {nb_agence_orphelines:,}")
print(f"  Transactions hors dim_temps    : {nb_date_orphelines:,}")

if nb_client_orphelins == 0 and nb_agence_orphelines == 0 and nb_date_orphelines == 0:
    print("✅ Intégrité référentielle OK (fact_transactions) — toutes les clés sont couvertes")
else:
    print("⚠️ Des transactions ne trouvent pas leur dimension correspondante — à investiguer avant Power BI")

# COMMAND ----------

nb_credits = fact_credits.count()
nb_credits_client_orphelins = fact_credits.join(dim_client, on="client_id", how="left_anti").count()
nb_credits_agence_orphelines = fact_credits.join(dim_agence, on="agence_id", how="left_anti").count()

print("Contrôles fact_credits :")
print(f"  Crédits totaux                 : {nb_credits:,}")
print(f"  Crédits sans client (orphelin) : {nb_credits_client_orphelins:,}")
print(f"  Crédits sans agence (orphelin) : {nb_credits_agence_orphelines:,}")

# COMMAND ----------

nb_ratios = fact_liquidite.count()
nb_ratios_agence_null = fact_liquidite.filter(col("agence_id").isNull()).count()
nb_ratios_agence_orphelines = fact_liquidite.filter(col("agence_id").isNotNull()).join(
    dim_agence, on="agence_id", how="left_anti"
).count()

print("Contrôles fact_liquidite :")
print(f"  Ratios totaux                          : {nb_ratios:,}")
print(f"  Ratios sans agence (BANQUE/GROUPE, OK)  : {nb_ratios_agence_null:,}")
print(f"  Ratios avec agence_id orphelin (anomalie): {nb_ratios_agence_orphelines:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Résumé
# MAGIC
# MAGIC | Table | Grain | Rôle |
# MAGIC | :--- | :--- | :--- |
# MAGIC | `fact_transactions` | transaction | Fraude et activité transactionnelle |
# MAGIC | `fact_credits` | crédit | Portefeuille de prêts + classification réglementaire (PD/LGD/EAD, provisions) |
# MAGIC | `fact_liquidite` | ratio calculé | Suivi LCR/NSFR par période et niveau de consolidation |
# MAGIC | `dim_client` | client | Dimension — attributs client (segment, revenu, risque...) |
# MAGIC | `dim_agence` | agence | Dimension — attributs agence, **partagée par les 3 faits** |
# MAGIC | `dim_temps` | jour | Dimension — drill-down temporel, jointure sur `date_key`, **partagée par les 3 faits** |
# MAGIC
# MAGIC **Dans Power BI**, relations à créer (cardinalité "Un à plusieurs", filtre
# MAGIC croisé "Unique") :
# MAGIC - `dim_client[client_id]` → `fact_transactions[client_id]`
# MAGIC - `dim_client[client_id]` → `fact_credits[client_id]`
# MAGIC - `dim_agence[agence_id]` → `fact_transactions[agence_id]`
# MAGIC - `dim_agence[agence_id]` → `fact_credits[agence_id]`
# MAGIC - `dim_agence[agence_id]` → `fact_liquidite[agence_id]` (relation partielle, NULL pour BANQUE/GROUPE — pas un problème)
# MAGIC - `dim_temps[date_key]` → `fact_transactions[date_key]`
# MAGIC - `dim_temps[date_key]` → `fact_credits[date_key]`
# MAGIC - `dim_temps[date_key]` → `fact_liquidite[date_key]`
# MAGIC
# MAGIC **Prochaine étape** : construire les mesures DAX (taux de fraude, encours par
# MAGIC catégorie de créance, LCR moyen...) directement dans Power BI.