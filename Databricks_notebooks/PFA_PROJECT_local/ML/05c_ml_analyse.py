# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 05c — Analyse statistique des variables
# MAGIC
# MAGIC Étape 3/5 : Exploration → Nettoyage → **Analyse** → Features → Modèle
# MAGIC
# MAGIC Objectif : trancher objectivement quelles variables sont vraiment
# MAGIC discriminantes, plutôt qu'à l'œil comme à l'étape d'exploration.
# MAGIC
# MAGIC ⚠️ **Point méthodologique important** : avec ~200 000 lignes, un test
# MAGIC statistique classique (t-test, chi²) trouvera presque toujours un résultat
# MAGIC "significatif" (p < 0,05), même pour un écart minuscule sans intérêt
# MAGIC pratique — la taille d'échantillon donne une puissance statistique énorme.
# MAGIC **La significativité seule ne suffit donc pas à décider** : on regarde
# MAGIC systématiquement la **taille d'effet** (effect size) à côté du p-value, et
# MAGIC c'est elle qui guide la décision finale de garder ou écarter une variable.

# COMMAND ----------

import pandas as pd
import numpy as np
from scipy import stats

df = spark.table("pfa_data.ml_outputs.gold_ml_features_clean").toPandas()
print(f"Dimensions : {df.shape[0]:,} lignes x {df.shape[1]} colonnes")

fraude = df[df["fraud_flag"] == 1]
normal = df[df["fraud_flag"] == 0]

# COMMAND ----------

# Distribution de la variable cible fraud_flag

print("Distribution de fraud_flag :")
print(df["fraud_flag"].value_counts())
print("\nProportions :")
print(df["fraud_flag"].value_counts(normalize=True))

# Déséquilibre des classes
taux_fraude = (df["fraud_flag"] == 1).mean()
print(f"\nTaux de fraude : {taux_fraude:.2%}")
print(f"Ratio normal/fraude : {1/taux_fraude:.1f}:1")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Variables numériques — test de Mann-Whitney U + taille d'effet
# MAGIC
# MAGIC Mann-Whitney plutôt qu'un t-test classique : robuste aux distributions non
# MAGIC normales (les montants de transaction sont très asymétriques, cf. la
# MAGIC génération log-normale dans `generate_data.py`).
# MAGIC
# MAGIC Taille d'effet : corrélation rang-bisériale, dans [-1, 1]. Repères usuels :
# MAGIC ~0,10 = effet faible, ~0,30 = effet modéré, ~0,50 = effet fort.

# COMMAND ----------

FEATURES_NUM = [
    "montant", "frais_transaction", "montant_moyen_client_30j",
    "ecart_type_client_30j", "nb_transactions_client_30j",
    "ecart_relatif_montant", "montant_cumule_client", "age",
    "revenu_mensuel", "score_credit", "ratio_montant_revenu",
    "taux_utilisation_30j",
]

resultats_num = []
for col in FEATURES_NUM:
    u_stat, p_value = stats.mannwhitneyu(
        fraude[col].dropna(), normal[col].dropna(), alternative="two-sided"
    )
    n1, n2 = len(fraude[col].dropna()), len(normal[col].dropna())
    effet_rang_biserial = 1 - (2 * u_stat) / (n1 * n2)
    resultats_num.append({
        "variable": col,
        "type": "numérique",
        "p_value": p_value,
        "taille_effet": abs(effet_rang_biserial),
    })

df_resultats_num = pd.DataFrame(resultats_num)
df_resultats_num

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Variables catégorielles et binaires — test du Chi² + V de Cramér
# MAGIC
# MAGIC V de Cramér dans [0, 1] : ~0,10 = effet faible, ~0,30 = modéré, ~0,50 = fort
# MAGIC (mêmes repères que Cohen, adaptés au chi²).

# COMMAND ----------

FEATURES_CAT_BIN = [
    "type_transaction", "canal", "mode_paiement", "sens_operation",
    "segment_client", "tranche_revenu", "niveau_risque_client", "tranche_horaire",
    "is_night", "is_weekend", "est_international", "hors_agence", "age_manquant",
]

resultats_cat = []
for col in FEATURES_CAT_BIN:
    table_contingence = pd.crosstab(df[col], df["fraud_flag"])
    chi2, p_value, dof, expected = stats.chi2_contingency(table_contingence)
    n = table_contingence.sum().sum()
    min_dim = min(table_contingence.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 else 0.0
    resultats_cat.append({
        "variable": col,
        "type": "catégorielle/binaire",
        "p_value": p_value,
        "taille_effet": cramers_v,
    })

df_resultats_cat = pd.DataFrame(resultats_cat)
df_resultats_cat

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Synthèse globale, triée par taille d'effet

# COMMAND ----------

# MAGIC %pip install statsmodels
# MAGIC
# MAGIC df_resultats = pd.concat([df_resultats_num, df_resultats_cat], ignore_index=True)
# MAGIC
# MAGIC # Correction de Benjamini-Hochberg (FDR) pour les tests multiples
# MAGIC from statsmodels.stats.multitest import multipletests
# MAGIC
# MAGIC _, p_adj, _, _ = multipletests(df_resultats["p_value"], method="fdr_bh")
# MAGIC df_resultats["p_value_ajuste"] = p_adj
# MAGIC
# MAGIC def classer_effet(e):
# MAGIC     if e >= 0.30:
# MAGIC         return "Fort"
# MAGIC     elif e >= 0.10:
# MAGIC         return "Modéré"
# MAGIC     elif e >= 0.03:
# MAGIC         return "Faible"
# MAGIC     else:
# MAGIC         return "Négligeable"
# MAGIC
# MAGIC df_resultats["force_effet"] = df_resultats["taille_effet"].apply(classer_effet)
# MAGIC
# MAGIC df_resultats["decision"] = np.where(
# MAGIC     df_resultats["force_effet"].isin(["Fort", "Modéré", "Faible"]),
# MAGIC     "Garder",
# MAGIC     "Écarter (effet négligeable malgré p-value)",
# MAGIC )
# MAGIC df_resultats.sort_values("taille_effet", ascending=False)

# COMMAND ----------


variables_retenues = df_resultats[df_resultats["decision"] == "Garder"]["variable"].tolist()
variables_ecartees = df_resultats[df_resultats["decision"] != "Garder"]["variable"].tolist()
 
print(f"Variables retenues ({len(variables_retenues)}) :")
print(variables_retenues)
print(f"\nVariables écartées ({len(variables_ecartees)}) :")
print(variables_ecartees)
 

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Résumé
# MAGIC
# MAGIC Cette étape a remplacé l'intuition ("on pensait que X serait discriminant")
# MAGIC par une décision objective basée sur la taille d'effet, pas uniquement le
# MAGIC p-value — indispensable avec un échantillon de cette taille où presque tout
# MAGIC ressort "statistiquement significatif" sans être réellement utile.
# MAGIC
# MAGIC **Prochaine étape** : notebook `05d_ml_features` — construction du jeu de
# MAGIC features final à partir des variables retenues ci-dessus, encodage, et
# MAGIC `train_test_split` stratifié sur `fraud_flag`.