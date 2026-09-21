# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Description du Projet - Couche Bronze
# MAGIC
# MAGIC ## Vue d'ensemble
# MAGIC
# MAGIC Ce projet implémente une architecture **médaillon (Medallion Architecture)** pour la gestion et le traitement des données d'une institution financière. La couche Bronze constitue la première étape de cette architecture et sert de fondation pour toutes les transformations de données ultérieures.
# MAGIC
# MAGIC ## Objectif de la Couche Bronze
# MAGIC
# MAGIC La couche Bronze a pour mission de :
# MAGIC
# MAGIC - **Ingérer les données brutes** provenant de différentes sources (fichiers CSV, bases de données, APIs, etc.)
# MAGIC - **Préserver la fidélité des données sources** sans transformation métier majeure
# MAGIC - **Stocker les données au format Delta Lake** pour bénéficier de la fiabilité ACID et du versioning
# MAGIC - **Effectuer des conversions de types minimales** (notamment les dates/timestamps) pour faciliter les traitements ultérieurs
# MAGIC - **Assurer la traçabilité** avec des métadonnées de création et de mise à jour
# MAGIC
# MAGIC ## Périmètre des Données
# MAGIC
# MAGIC Le projet couvre les entités suivantes du système d'information bancaire :
# MAGIC
# MAGIC ### 1. **Agences** (`agences.csv`)
# MAGIC    - Référentiel des agences bancaires
# MAGIC    - Localisation, type, dates d'ouverture
# MAGIC
# MAGIC ### 2. **Clients** (`clients.csv`)
# MAGIC    - Informations clients (particuliers et professionnels)
# MAGIC    - Données démographiques, segmentation, risque
# MAGIC
# MAGIC ### 3. **Comptes** (`comptes.csv`)
# MAGIC    - Comptes bancaires (courants, épargne, dépôt à terme)
# MAGIC    - Soldes, statuts, dates d'ouverture/fermeture
# MAGIC
# MAGIC ### 4. **Transactions** (`transactions.csv`)
# MAGIC    - Mouvements bancaires détaillés
# MAGIC    - **Table volumineuse** : partitionnée par année et mois pour optimiser les performances
# MAGIC
# MAGIC ### 5. **Crédits** (`credits.csv`)
# MAGIC    - Portefeuille de prêts
# MAGIC    - Montants, échéanciers, incidents de paiement
# MAGIC
# MAGIC ### 6. **Classification des Créances** (`classification_creances.csv`)
# MAGIC    - Classification réglementaire des crédits (sain, sous surveillance, douteux, compromis)
# MAGIC    - Provisions, restructurations, contentieux
# MAGIC
# MAGIC ### 7. **Ratios de Liquidité** (`ratios_liquidite.csv`)
# MAGIC    - Indicateurs de liquidité réglementaires (LCR, NSFR, etc.)
# MAGIC    - Calculs périodiques pour le pilotage prudentiel
# MAGIC
# MAGIC ## Architecture Technique
# MAGIC
# MAGIC ### Stockage
# MAGIC - **Format** : Delta Lake
# MAGIC - **Schéma** : `pfa_bronze`
# MAGIC - **Localisation des fichiers sources** : `/Volumes/pfa_data/data_sources/pfa_raw_data`
# MAGIC
# MAGIC ### Partitionnement
# MAGIC - Les **transactions** sont partitionnées par `annee` et `mois` pour optimiser les requêtes temporelles
# MAGIC - Les autres tables (moins volumineuses) ne sont pas partitionnées
# MAGIC
# MAGIC ### Traitement des Données
# MAGIC 1. **Lecture des CSV** avec inférence de schéma (`inferSchema=True`)
# MAGIC 2. **Conversion des types de dates** (string → date/timestamp)
# MAGIC 3. **Écriture en format Delta** avec mode `overwrite`
# MAGIC 4. **Enregistrement en tant que tables Unity Catalog**
# MAGIC
# MAGIC ## Contrôles Qualité
# MAGIC
# MAGIC La couche Bronze intègre des contrôles de qualité essentiels :
# MAGIC
# MAGIC - **Comptage des lignes ingérées** par table
# MAGIC - **Vérification de l'unicité** des clés primaires
# MAGIC - **Contrôle d'intégrité référentielle** (ex: transactions orphelines sans client)
# MAGIC - **Affichage d'échantillons** pour validation visuelle
# MAGIC
# MAGIC ## Prochaines Étapes
# MAGIC
# MAGIC Après l'ingestion en couche Bronze, les données seront transformées dans :
# MAGIC
# MAGIC - **Couche Silver** : nettoyage, déduplication, enrichissement, jointures
# MAGIC - **Couche Gold** : agrégations métier, KPI, tables analytiques pour la BI
# MAGIC
# MAGIC ## Métadonnées
# MAGIC
# MAGIC - **Auteur** : PFA - Pipeline Data & BI
# MAGIC - **Date** : Septembre 2026
# MAGIC - **Version** : 1.0
# MAGIC - **Plateforme** : Databricks / Unity Catalog

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuration

# COMMAND ----------

# DBTITLE 1,Configuration des  chemins
# Paramètres (peuvent être passés en paramètres de job)
base_path = "/Volumes/pfa_data/data_sources/pfa_raw_data"
bronze_path = "/Volumes/pfa_data/bronze_data/bronze"


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Lecture des CSV avec inference de schéma

# COMMAND ----------

# DBTITLE 1,Importation des  données
# Lecture de chaque fichier CSV avec en-têtes et inference de type
agences_df = spark.read.option("header", True).option("inferSchema", True).csv(f"{base_path}/agences.csv")
clients_df = spark.read.option("header", True).option("inferSchema", True).csv(f"{base_path}/clients.csv")
comptes_df = spark.read.option("header", True).option("inferSchema", True).csv(f"{base_path}/comptes.csv")
transactions_df = spark.read.option("header", True).option("inferSchema", True).csv(f"{base_path}/transactions.csv")
credits_df = spark.read.option("header", True).option("inferSchema", True).csv(f"{base_path}/credits.csv")
classification_df = spark.read.option("header", True).option("inferSchema", True).csv(f"{base_path}/classification_creances.csv")
ratios_df = spark.read.option("header", True).option("inferSchema", True).csv(f"{base_path}/ratios_liquidite.csv")

# COMMAND ----------

# Affichage des 10 premières lignes de chaque table
print("=== TOP 10 AGENCES ===")
display(agences_df.limit(10))

print("\n=== TOP 10 CLIENTS ===")
display(clients_df.limit(10))

print("\n=== TOP 10 COMPTES ===")
display(comptes_df.limit(10))

print("\n=== TOP 10 TRANSACTIONS ===")
display(transactions_df.limit(10))

print("\n=== TOP 10 CRÉDITS ===")
display(credits_df.limit(10))

print("\n=== TOP 10 CLASSIFICATION CRÉANCES ===")
display(classification_df.limit(10))

print("\n=== TOP 10 RATIOS LIQUIDITÉ ===")
display(ratios_df.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Enregistrement des tables Delta

# COMMAND ----------

# MAGIC %md
# MAGIC On sauvegarde chaque DataFrame en table Delta dans le schéma `pfa_bronze`.
# MAGIC On partitionne les tables volumineuses (ex: transactions) par année et mois pour améliorer les performances des requêtes.

# COMMAND ----------

# Écriture des tables Delta dans le path bronze

# Transactions : on ajoute des colonnes année et mois pour le partitionnement
from pyspark.sql.functions import year, month, col

transactions_df_bronze = transactions_df \
    .withColumn("annee", year("date_transaction")) \
    .withColumn("mois", month("date_transaction"))

# ✅ AJOUT : forcer la réécriture du schéma
transactions_df_bronze.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .partitionBy("annee", "mois") \
    .save(f"{bronze_path}/bronze_transactions")

# Les autres tables (plus petites) ne sont pas partitionnées
agences_df.write.format("delta").mode("overwrite").save(f"{bronze_path}/bronze_agences")
clients_df.write.format("delta").mode("overwrite").save(f"{bronze_path}/bronze_clients")
comptes_df.write.format("delta").mode("overwrite").save(f"{bronze_path}/bronze_comptes")
credits_df.write.format("delta").mode("overwrite").save(f"{bronze_path}/bronze_credits")
classification_df.write.format("delta").mode("overwrite").save(f"{bronze_path}/bronze_classification_creances")
ratios_df.write.format("delta").mode("overwrite").save(f"{bronze_path}/bronze_ratios_liquidite")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Vérifications et statistiques

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Afficher les fichiers sauvegardés dans bronze_path
# MAGIC LIST '/Volumes/pfa_data/bronze_data/bronze';

# COMMAND ----------

# MAGIC %md
# MAGIC ### Comptage des lignes

# COMMAND ----------

# Nombre de lignes ingérées depuis bronze_path
print("Nombre de lignes ingérées depuis bronze_path:")
print(f"agences                   : {spark.read.format('delta').load(f'{bronze_path}/bronze_agences').count()}")
print(f"clients                   : {spark.read.format('delta').load(f'{bronze_path}/bronze_clients').count()}")
print(f"comptes                   : {spark.read.format('delta').load(f'{bronze_path}/bronze_comptes').count()}")
print(f"transactions              : {spark.read.format('delta').load(f'{bronze_path}/bronze_transactions').count()}")
print(f"credits                   : {spark.read.format('delta').load(f'{bronze_path}/bronze_credits').count()}")
print(f"classification_creances   : {spark.read.format('delta').load(f'{bronze_path}/bronze_classification_creances').count()}")
print(f"ratios_liquidite          : {spark.read.format('delta').load(f'{bronze_path}/bronze_ratios_liquidite').count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Échantillon de données (transactions)

# COMMAND ----------

display(spark.read.format('delta').load(f'{bronze_path}/bronze_transactions').limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Contrôles de qualité (intégrité)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Vérifier que les clés primaires sont uniques
# MAGIC SELECT COUNT(DISTINCT transaction_id) AS distinct_count, COUNT(*) AS total_count
# MAGIC FROM delta.`/Volumes/pfa_data/bronze_data/bronze/bronze_transactions`;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Vérifier que les références à client_id existent
# MAGIC SELECT COUNT(*) AS orphan_transactions
# MAGIC FROM delta.`/Volumes/pfa_data/bronze_data/bronze/bronze_transactions` t
# MAGIC LEFT JOIN delta.`/Volumes/pfa_data/bronze_data/bronze/bronze_clients` c ON t.client_id = c.client_id
# MAGIC WHERE c.client_id IS NULL;

# COMMAND ----------

# MAGIC %md
# MAGIC La couche Bronze est prête. Les données brutes sont désormais disponibles en Delta Lake, prêtes pour les transformations vers les couches Silver et Gold.