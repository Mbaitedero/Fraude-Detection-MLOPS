# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Couche Silver – Nettoyage, Enrichissement et Transformations
# MAGIC
# MAGIC Ce notebook transforme les données brutes (Bronze) en données nettoyées et enrichies (Silver).
# MAGIC Les transformations incluent :
# MAGIC - Conversion des types et gestion des NULL
# MAGIC - Enrichissement des transactions avec des données client/compte
# MAGIC - Calcul de features pour la détection de fraude (moyennes mobiles, écarts-types)
# MAGIC - Agrégations préliminaires (comptes, clients)
# MAGIC
# MAGIC **Auteur** : PFA - Pipeline Data & BI  
# MAGIC **Date** : Septembre 2026

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuration

# COMMAND ----------

bronze_path = "/Volumes/pfa_data/bronze_data/bronze"
silver_path = "/Volumes/pfa_data/silver_data/silver"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Lecture des tables Bronze

# COMMAND ----------

# Lecture des tables Bronze depuis le chemin défini
agences_bronze = spark.read.format("delta").load(f"{bronze_path}/bronze_agences")
clients_bronze = spark.read.format("delta").load(f"{bronze_path}/bronze_clients")
comptes_bronze = spark.read.format("delta").load(f"{bronze_path}/bronze_comptes")
transactions_bronze = spark.read.format("delta").load(f"{bronze_path}/bronze_transactions")
credits_bronze = spark.read.format("delta").load(f"{bronze_path}/bronze_credits")
classification_bronze = spark.read.format("delta").load(f"{bronze_path}/bronze_classification_creances")
ratios_bronze = spark.read.format("delta").load(f"{bronze_path}/bronze_ratios_liquidite")

print("✅ Toutes les tables Bronze ont été chargées avec succès.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Nettoyage et transformations

# COMMAND ----------

from pyspark.sql.functions import (
    col, to_date, year, month, dayofmonth, dayofweek, when, lit, 
    round, coalesce, isnan, isnull, count, sum, avg, stddev, 
    datediff, current_date, explode, split, regexp_replace,
    dense_rank, row_number, lag, lead, abs, expr, min, max, 
    date_format, unix_timestamp, from_unixtime
)
from pyspark.sql.types import DoubleType, IntegerType, StringType, DateType
from pyspark.sql.window import Window

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 Agences (nettoyage minimal)

# COMMAND ----------

#Affichons  les  10  prémières  lignes
display(agences_bronze.limit(10))
# Affichage des informations de la table
agences_bronze.printSchema()

# COMMAND ----------

## gestion des  valeurs  nulles et  des  doublons  
agences_bronze = agences_bronze.dropDuplicates(["agence_id"]).withColumn(
    "agence_id", 
    when(col("agence_id").isNotNull(), col("agence_id")).otherwise(lit(None))
).withColumn(
    "nom_agence", 
    when(col("nom_agence").isNotNull(), col("nom_agence")).otherwise(lit(None))
).withColumn(
    "adresse", 
    when(col("adresse").isNotNull(), col("adresse")).otherwise(lit(None))
).withColumn(
    "ville", 
    when(col("ville").isNotNull(), col("ville")).otherwise(lit(None))
).withColumn(
    "code_postal", 
    when(col("code_postal").isNotNull(), col("code_postal")).otherwise(lit(None))
).withColumn(
    "region", 
    when(col("region").isNotNull(), col("region")).otherwise(lit(None))
).withColumn(
    "pays", 
    when(col("pays").isNotNull(), col("pays")).otherwise(lit(None))
).withColumn(
    "telephone", 
    when(col("telephone").isNotNull(), col("telephone")).otherwise(lit(None))
)
agences_bronze = agences_bronze.dropna(subset=["agence_id"])
agences_bronze = agences_bronze.withColumn(
    "email", 
    when(col("email").isNotNull(), regexp_replace(col("email"), "@gmail.com", "@banque.com")).otherwise(lit(None))
)
agences_bronze = agences_bronze.withColumn(
    "directeur", 
    when(col("directeur").isNotNull(), col("directeur")).otherwise(lit(None))
)
agences_bronze = agences_bronze.withColumn(
    "date_ouverture", 
    when(col("date_ouverture").isNotNull(), col("date_ouverture")).otherwise(lit(None))
)
agences_bronze = agences_bronze.withColumn(
    "type_agence", 
    when(col("type_agence").isNotNull(), col("type_agence")).otherwise(lit(None))
)
agences_bronze = agences_bronze.withColumn(
    "latitude", 
    when(col("latitude").isNotNull(), col("latitude")).otherwise(lit(None))
)
agences_bronze = agences_bronze.withColumn(
    "longitude", 
    when(col("longitude").isNotNull(), col("longitude")).otherwise(lit(None))
)


# COMMAND ----------

# Les agences sont déjà propres. On ajoute juste un champ de vérification.
agences_silver = agences_bronze.select(
    col("agence_id"),
    col("nom_agence"),
    col("adresse"),
    col("ville"),
    col("code_postal"),
    col("region"),
    col("pays"),
    col("telephone"),
    col("email"),
    col("directeur"),
    col("date_ouverture"),
    col("type_agence"),
    col("latitude"),
    col("longitude")
)

# COMMAND ----------

display(agences_bronze.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 Clients (nettoyage et enrichissement)

# COMMAND ----------

#Affichons les 10 premières lignes
display(clients_bronze.limit(10))

# Affichage des informations de la table
clients_bronze.printSchema()

# Statistiques descriptives sur les colonnes numériques
display(clients_bronze.describe())

# Comptage des lignes
print(f"Nombre total de clients : {clients_bronze.count()}")

# Vérification des valeurs nulles
from pyspark.sql.functions import col, count, when, isnan, isnull

null_counts = clients_bronze.select([
    count(when(col(c).isNull(), c)).alias(c) for c in clients_bronze.columns
])
print("\nNombre de valeurs nulles par colonne :")
display(null_counts)

# Distribution par statut client
print("\nDistribution par statut client :")
display(clients_bronze.groupBy("statut_client").count().orderBy("count", ascending=False))

# Distribution par segment client
print("\nDistribution par segment client :")
display(clients_bronze.groupBy("segment_client").count().orderBy("count", ascending=False))

# Distribution par ville
print("\nTop 10 villes avec le plus de clients :")
display(clients_bronze.groupBy("ville").count().orderBy("count", ascending=False).limit(10))

# COMMAND ----------

# importation de  floor
from pyspark.sql.functions import floor
# Nettoyage des clients : conversion des dates, calcul de l'âge, gestion des NULL
clients_silver = clients_bronze.withColumn(
    "age", 
    when(col("date_naissance").isNotNull(), 
         floor(datediff(current_date(), col("date_naissance")) / 365.25)
    ).otherwise(lit(None))
).withColumn(
    "anciennete_annees",
    floor(datediff(current_date(), col("date_premier_contact")) / 365.25)
).withColumn(
    "tranche_revenu",
    when(col("revenu_mensuel") < 5000, "0-5k")
    .when(col("revenu_mensuel") < 15000, "5k-15k")
    .when(col("revenu_mensuel") < 30000, "15k-30k")
    .when(col("revenu_mensuel") < 50000, "30k-50k")
    .otherwise("50k+")
).withColumn(
    "statut_client_binaire",
    when(col("statut_client") == "Actif", 1).otherwise(0)
)

# COMMAND ----------

from pyspark.sql.functions import when, concat_ws, col, lit, coalesce

clients_silver = clients_silver.withColumn(
    "nom_complet",
    when(col("type_client") == "Particulier",
         concat_ws(" ", coalesce(col("civilite"), lit("")), 
                      coalesce(col("prenom"), lit("")), 
                      coalesce(col("nom"), lit(""))))
    .when(col("type_client") == "Entreprise",
         coalesce(col("raison_sociale"), col("nom")))
    .otherwise(col("nom"))
)

# COMMAND ----------

display(clients_silver.limit(30))

# COMMAND ----------

# Suppression des colonnes nom et prenom, puis suppression des valeurs nulles par colonne
clients_silver = clients_silver.drop("nom", "prenom")

print("✅ Colonnes 'nom' et 'prenom' supprimées ")
display(clients_silver.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 Comptes (nettoyage et enrichissement)

# COMMAND ----------

#Affichons les 10 premières lignes
display(comptes_bronze.limit(10))

# Affichage des informations de la table
comptes_bronze.printSchema()

# Statistiques descriptives sur les colonnes numériques
display(comptes_bronze.describe())

# Comptage des lignes
print(f"Nombre total de comptes : {comptes_bronze.count()}")

# Vérification des valeurs nulles
from pyspark.sql.functions import col, count, when, isnan, isnull

null_counts = comptes_bronze.select([
    count(when(col(c).isNull(), c)).alias(c) for c in comptes_bronze.columns
])
print("\nNombre de valeurs nulles par colonne :")
display(null_counts)

# Distribution par type de compte
print("\nDistribution par type de compte :")
display(comptes_bronze.groupBy("type_compte").count().orderBy("count", ascending=False))

# Distribution par statut de compte
print("\nDistribution par statut de compte :")
display(comptes_bronze.groupBy("statut_compte").count().orderBy("count", ascending=False))

# Statistiques sur les soldes par type de compte
print("\nStatistiques des soldes par type de compte :")
display(comptes_bronze.groupBy("type_compte").agg(
    count("compte_id").alias("nombre_comptes"),
    avg("solde").alias("solde_moyen"),
    min("solde").alias("solde_min"),
    max("solde").alias("solde_max")
).orderBy("solde_moyen", ascending=False))

# COMMAND ----------

# Nettoyage des comptes : calcul de l'ancienneté du compte, gestion des NULL
comptes_silver = comptes_bronze.withColumn(
    "anciennete_compte_mois",
    when(col("date_ouverture").isNotNull(),
         round(datediff(current_date(), col("date_ouverture")) / 30.44, 1)
    ).otherwise(lit(None))
).withColumn(
    "est_actif", 
    when(col("statut_compte") == "Actif", 1).otherwise(0)
).withColumn(
    "solde_normalise",
    when(col("type_compte") == "Compte épargne", col("solde") / 1000)
    .otherwise(col("solde") / 10000)  # normalisation relative
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 Transactions (enrichissement avancé)

# COMMAND ----------

display(transactions_bronze.limit(10 ))


# COMMAND ----------

# On commence par enrichir les transactions avec les données client et compte
from pyspark.sql.functions import lit, col, datediff, round, dayofweek, date_format, split, cast, when, lit, count, avg, min, max, sum, countDistinct, mean, stddev, skewness, kurtosis, corr, covar_pop, covar_samp, skewness, kurtosis, corr, covar_pop, covar_samp, skewness, kurtosis, corr, covar_pop

transactions_base = transactions_bronze.join(
    clients_silver.select("client_id", "age", "ville", "segment_client", "tranche_revenu", "revenu_mensuel"),
    on="client_id",
    how="left"
).join(
    comptes_silver.select("compte_id", "type_compte", "date_ouverture").alias("comptes_src"),
    on=col("compte_source_id") == col("comptes_src.compte_id"),
    how="left"
)

# Ajout de colonnes temporelles
transactions_enriched = transactions_base.withColumn(
    "jour_semaine", dayofweek("date_transaction")
).withColumn(
    "mois_annee", date_format("date_transaction", "yyyy-MM")
).withColumn(
    "heure", 
    split(col("heure_transaction"), ":")[0].cast("int")
).withColumn(
    "tranche_horaire",
    when(col("heure") < 6, "Nuit")
    .when(col("heure") < 12, "Matin")
    .when(col("heure") < 18, "Après-midi")
    .otherwise("Soir")
)

# Détection des transactions 'inhabituelles' par rapport à la moyenne du client
# Calcul de la moyenne mobile (fenêtre de 30 jours) par client
window_spec = Window.partitionBy("client_id").orderBy("date_transaction").rowsBetween(-30, -1)

transactions_features = transactions_enriched.withColumn(
    "montant_moyen_client_30j",
    avg("montant").over(window_spec)
).withColumn(
    "ecart_type_client_30j",
    stddev("montant").over(window_spec)
).withColumn(
    "nb_transactions_client_30j",
    count("transaction_id").over(window_spec)
)

# Remplacer les NaN par des valeurs par défaut (pour les nouveaux clients)
transactions_features = transactions_features.fillna({
    "montant_moyen_client_30j": 0.0,
    "ecart_type_client_30j": 0.0,
    "nb_transactions_client_30j": 0
})

# Calcul de l'écart par rapport à la moyenne (pour détection d'anomalies)
transactions_features = transactions_features.withColumn(
    "ecart_relatif_montant",
    when(col("montant_moyen_client_30j") != 0,
         (col("montant") - col("montant_moyen_client_30j")) / col("montant_moyen_client_30j")
    ).otherwise(lit(0.0))
)

# Calcul du montant total par client (cumulé)
window_cumul = Window.partitionBy("client_id").orderBy("date_transaction").rowsBetween(Window.unboundedPreceding, Window.currentRow)
transactions_features = transactions_features.withColumn(
    "montant_cumule_client",
    sum("montant").over(window_cumul)
)

# Flag : transaction internationale
# 'is_international' est déjà présent, mais on le recrée au cas où
transactions_features = transactions_features.withColumn(
    "est_international",
    when(col("pays_marchand").isNotNull() & (col("pays_marchand") != "MA"), 1)
    .when(col("pays_destination").isNotNull() & (col("pays_destination") != "MA"), 1)
    .otherwise(0)
)

# Flag : transaction hors agence (ville différente)
transactions_features = transactions_features.withColumn(
    "hors_agence",
    when(col("ville_transaction") != col("ville"), 1).otherwise(0)
)

# Ajouter une colonne 'compte_touche' (jamais NULL) et 'sens_operation'
transactions_features = transactions_features.withColumn(
    "compte_touche",
    coalesce(col("compte_source_id"), col("compte_destination_id"))
).withColumn(
    "sens_operation",
    when(col("compte_source_id").isNotNull() & col("compte_destination_id").isNull(), "Débit")
    .when(col("compte_source_id").isNull() & col("compte_destination_id").isNotNull(), "Crédit")
    .when(col("compte_source_id").isNotNull() & col("compte_destination_id").isNotNull(), "Virement interne")
    .otherwise("Autre")
)

# Sélection des colonnes finales pour Silver
transactions_silver = transactions_features.select(
    "transaction_id",
    "compte_id",
    "client_id",
    "agence_id",
    "date_transaction",
    "compte_touche",
    "sens_operation",
    "date_valeur",
    "heure_transaction",
    "heure",
    "tranche_horaire",
    "montant",
    "devise",
    "type_transaction",
    "categorie",
    "sous_categorie",
    "canal",
    "mode_paiement",
    "statut_transaction",
    "reference_transaction",
    "libelle",
    "merchant_id",
    "code_mcc",
    "nom_marchand",
    "pays_marchand",
    "ville_transaction",
    "pays_origine",
    "pays_destination",
    "numero_carte_masque",
    "terminal_id",
    "frais_transaction",
    "solde_avant",
    "solde_apres",
    "latitude",
    "longitude",
    "ip_address",
    "device_id",
    "is_international",
    "est_international",  # nouveau
    "is_weekend",
    "is_night",
    "fraud_flag",
    "fraud_type",
    "fraud_rule_triggered",
    "jour_semaine",
    "mois_annee",
    "age",
    "segment_client",
    "tranche_revenu",
    "revenu_mensuel",
    "type_compte",
    "montant_moyen_client_30j",
    "ecart_type_client_30j",
    "nb_transactions_client_30j",
    "ecart_relatif_montant",
    "montant_cumule_client",
    "hors_agence"
)

# COMMAND ----------

display(transactions_silver.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 Crédits et Classification (enrichissement)

# COMMAND ----------

# Enrichir les crédits avec des indicateurs de risque
from pyspark.sql.functions import when

credits_silver = credits_bronze.withColumn(
    "ratio_restant_initial",
    when(col("montant_initial") != 0, col("montant_restant_du") / col("montant_initial"))
    .otherwise(0.0)
).withColumn(
    "provision_ratio",
    when(col("montant_restant_du") != 0, col("provision_constituee") / col("montant_restant_du"))
    .otherwise(0.0)
)

classification_silver = classification_bronze.withColumn(
    "taux_perte_attendue",
    when(col("exposition_en_cas_defaut_ead") != 0, 
         col("perte_attendue_el") / col("exposition_en_cas_defaut_ead"))
    .otherwise(0.0)
).withColumn(
    "ratio_provision_exposition",
    when(col("exposition_en_cas_defaut_ead") != 0,
         col("provision_constituee") / col("exposition_en_cas_defaut_ead"))
    .otherwise(0.0)
)

# COMMAND ----------

display(classification_silver.limit(10))
display(credits_silver.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.6 Ratios de liquidité (enrichissement)

# COMMAND ----------

# Ajouter des variations mensuelles
window_ratio = Window.orderBy("date_calcul")

ratios_silver = ratios_bronze.withColumn(
    "lcr_variation_mensuelle",
    col("lcr_ratio") - lag("lcr_ratio").over(window_ratio)
).withColumn(
    "nsfr_variation_mensuelle",
    col("nsfr_ratio") - lag("nsfr_ratio").over(window_ratio)
).withColumn(
    "tendance_lcr",
    when(col("lcr_variation_mensuelle") > 0, "Amélioration")
    .when(col("lcr_variation_mensuelle") < 0, "Détérioration")
    .otherwise("Stable")
)

# COMMAND ----------

display(ratios_silver.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Écriture des tables Silver

# COMMAND ----------

# DBTITLE 1,Sauvegarde des tables Silver
# Écriture des tables Silver dans le silver_path
print("💾 Sauvegarde des tables Silver...\n")

# 1. Agences
agences_silver.write.format("delta").mode("overwrite").save(f"{silver_path}/silver_agences")
print("✅ silver_agences sauvegardée")

# 2. Clients
clients_silver.write.format("delta").mode("overwrite").save(f"{silver_path}/silver_clients")
print("✅ silver_clients sauvegardée")

# 3. Comptes
comptes_silver.write.format("delta").mode("overwrite").save(f"{silver_path}/silver_comptes")
print("✅ silver_comptes sauvegardée")

# 4. Transactions
transactions_silver.write.format("delta").mode("overwrite").save(f"{silver_path}/silver_transactions")
print("✅ silver_transactions sauvegardée")

# 5. Crédits
credits_silver.write.format("delta").mode("overwrite").save(f"{silver_path}/silver_credits")
print("✅ silver_credits sauvegardée")

# 6. Classification des créances
classification_silver.write.format("delta").mode("overwrite").save(f"{silver_path}/silver_classification_creances")
print("✅ silver_classification_creances sauvegardée")

# 7. Ratios de liquidité
ratios_silver.write.format("delta").mode("overwrite").save(f"{silver_path}/silver_ratios_liquidite")
print("✅ silver_ratios_liquidite sauvegardée")

print("\n🎉 Toutes les tables Silver ont été sauvegardées avec succès dans:", silver_path)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Vérifications et statistiques

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Vérifications et statistiques des tables Silver
# MAGIC
# MAGIC -- 1. Vérifier l'existence et le nombre de lignes de toutes les tables Silver
# MAGIC SELECT 
# MAGIC   'agences' AS table_name,
# MAGIC   COUNT(*) AS nombre_lignes
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_agences`
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'clients' AS table_name,
# MAGIC   COUNT(*) AS nombre_lignes
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_clients`
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'comptes' AS table_name,
# MAGIC   COUNT(*) AS nombre_lignes
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_comptes`
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'transactions' AS table_name,
# MAGIC   COUNT(*) AS nombre_lignes
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_transactions`
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'credits' AS table_name,
# MAGIC   COUNT(*) AS nombre_lignes
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_credits`
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'classification_creances' AS table_name,
# MAGIC   COUNT(*) AS nombre_lignes
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_classification_creances`
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'ratios_liquidite' AS table_name,
# MAGIC   COUNT(*) AS nombre_lignes
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_ratios_liquidite`
# MAGIC
# MAGIC ORDER BY table_name;
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Comptage des lignes (Silver)

# COMMAND ----------

# Comptage du nombre de lignes dans chaque table Silver
print("📊 Nombre de lignes dans les tables Silver:\n")

print(f"Agences: {agences_silver.count():,}")
print(f"Clients: {clients_silver.count():,}")
print(f"Comptes: {comptes_silver.count():,}")
print(f"Transactions: {transactions_silver.count():,}")
print(f"Crédits: {credits_silver.count():,}")
print(f"Classification des créances: {classification_silver.count():,}")
print(f"Ratios de liquidité: {ratios_silver.count():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Échantillon des transactions enrichies

# COMMAND ----------

display(transactions_silver.select(
    "transaction_id", "client_id", "date_transaction", "montant", 
    "type_transaction", "fraud_flag", "montant_moyen_client_30j",
    "ecart_relatif_montant", "is_night", "hors_agence"
).limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Distribution des fraudes par tranche horaire

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC   tranche_horaire,
# MAGIC   COUNT(*) AS total_transactions,
# MAGIC   SUM(fraud_flag) AS total_fraudes,
# MAGIC   ROUND(SUM(fraud_flag) * 100.0 / COUNT(*), 2) AS taux_fraude_pct
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_transactions`
# MAGIC GROUP BY tranche_horaire
# MAGIC ORDER BY taux_fraude_pct DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ### Vérification de l'intégrité des données Silver

# COMMAND ----------

display(transactions_silver)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Vérifier qu'il n'y a pas de NULL dans les colonnes clés des transactions
# MAGIC SELECT 
# MAGIC   COUNT(*) AS total,
# MAGIC   SUM(CASE WHEN client_id IS NULL THEN 1 ELSE 0 END) AS null_client_id,
# MAGIC   SUM(CASE WHEN compte_id IS NULL THEN 1 ELSE 0 END) AS null_compte_id,
# MAGIC   SUM(CASE WHEN date_transaction IS NULL THEN 1 ELSE 0 END) AS null_date
# MAGIC FROM delta.`/Volumes/pfa_data/silver_data/silver/silver_transactions`

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Résumé des enrichissements

# COMMAND ----------

# MAGIC %md
# MAGIC **Nouvelles colonnes ajoutées dans Silver :**
# MAGIC
# MAGIC - **Clients** : `age`, `anciennete_annees`, `tranche_revenu`, `statut_client_binaire`
# MAGIC - **Comptes** : `anciennete_compte_mois`, `est_actif`, `solde_normalise`
# MAGIC - **Transactions** :
# MAGIC   - `jour_semaine`, `mois_annee`, `tranche_horaire`
# MAGIC   - `montant_moyen_client_30j`, `ecart_type_client_30j`, `nb_transactions_client_30j`
# MAGIC   - `ecart_relatif_montant` (indicateur d'anomalie)
# MAGIC   - `montant_cumule_client`
# MAGIC   - `est_international`, `hors_agence`, `compte_touche`, `sens_transactions`
# MAGIC - **Crédits** : `ratio_restant_initial`, `taux_retard_mois`, `provision_ratio`
# MAGIC - **Classification** : `taux_perte_attendue`, `ratio_provision_exposition`
# MAGIC - **Ratios** : `lcr_variation_mensuelle`, `nsfr_variation_mensuelle`, `tendance_lcr`

# COMMAND ----------

# MAGIC %md
# MAGIC La couche Silver est prête. Les données sont maintenant nettoyées, enrichies et prêtes pour les agrégations de la couche **Gold** (reporting réglementaire, KPIs, et dataset pour le Machine Learning).