# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# dependencies = [
#   "statsmodels",
# ]
# ///
# MAGIC %md
# MAGIC # 05d — Feature engineering et split train/test
# MAGIC
# MAGIC Étape 4/5 : Exploration → Nettoyage → Analyse → **Features** → Modèle
# MAGIC
# MAGIC 16 variables retenues (choix final, plus large que la sélection statistique
# MAGIC stricte de l'étape Analyse — décision documentée : on garde des variables de
# MAGIC contexte à effet univarié faible mais potentiellement utiles en interaction
# MAGIC pour un modèle d'arbres) :
# MAGIC
# MAGIC - **Valeur de la transaction (5)** : `montant`, `frais_transaction`, `ecart_relatif_montant`, `ratio_montant_revenu`, `taux_utilisation_30j`
# MAGIC - **Comportement client 30j (4)** : `montant_moyen_client_30j`, `ecart_type_client_30j`, `nb_transactions_client_30j`, `montant_cumule_client`
# MAGIC - **Contexte (7)** : `type_transaction`, `mode_paiement`, `sens_operation`, `tranche_horaire`, `is_night`, `is_weekend`, `est_international`

# COMMAND ----------

import pandas as pd
import numpy as np

df = spark.table("pfa_data.ml_outputs.gold_ml_features_clean").toPandas()
FEATURES_FINALES = [
    # --- Valeur de la transaction (5) ---
    "montant",
    "frais_transaction",
    "ecart_relatif_montant",
    "ratio_montant_revenu",
    "taux_utilisation_30j",
    # --- Comportement client 30j (4) ---
    "montant_moyen_client_30j",
    "ecart_type_client_30j",
    "nb_transactions_client_30j",
    "montant_cumule_client",
    # --- Contexte (7) ---
    "type_transaction",
    "mode_paiement",
    "sens_operation",
    "tranche_horaire",
    "is_night",
    "is_weekend",
    "est_international",
]

FEATURES_NUM = [
    "montant", "frais_transaction", "ecart_relatif_montant", "ratio_montant_revenu", "taux_utilisation_30j",
    "montant_moyen_client_30j", "ecart_type_client_30j", "nb_transactions_client_30j", "montant_cumule_client",
]
FEATURES_CAT = ["type_transaction", "mode_paiement", "sens_operation", "tranche_horaire"]
FEATURES_BIN = ["is_night", "is_weekend", "est_international"]
LABEL = "fraud_flag"

print(f"Dimensions : {df.shape[0]:,} lignes")
print(f"{len(FEATURES_FINALES)} features : {len(FEATURES_NUM)} numériques, {len(FEATURES_CAT)} catégorielles, {len(FEATURES_BIN)} binaires")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Multicolinéarité entre les variables numériques

# COMMAND ----------

corr_matrix = df[FEATURES_NUM].corr()
corr_matrix

# COMMAND ----------

paires_correlees = (
    corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    .stack()
    .reset_index()
)
paires_correlees.columns = ["variable_1", "variable_2", "correlation"]
paires_correlees = paires_correlees.reindex(
    paires_correlees["correlation"].abs().sort_values(ascending=False).index
)
print("Paires de features numériques triées par corrélation absolue décroissante :")
paires_correlees

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. VIF (Variance Inflation Factor)

# COMMAND ----------

# MAGIC %pip install statsmodels

# COMMAND ----------

display(df)

# COMMAND ----------

from statsmodels.stats.outliers_influence import variance_inflation_factor

X_vif = df[FEATURES_NUM].fillna(0)
vif_data = pd.DataFrame({
    "variable": FEATURES_NUM,
    "VIF": [variance_inflation_factor(X_vif.values, i) for i in range(len(FEATURES_NUM))],
})
print("VIF > 5 = multicolinéarité modérée à surveiller ; VIF > 10 = problématique")
vif_data.sort_values("VIF", ascending=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Split train/test stratifié — AVANT encodage
# MAGIC
# MAGIC ⚠️ Important : le split se fait avant l'encodage des variables catégorielles,
# MAGIC et l'encodeur est ensuite **entraîné uniquement sur le train** (`fit` sur
# MAGIC train, `transform` sur train et test). L'entraîner sur l'ensemble des données
# MAGIC avant le split ferait fuiter de l'information du test set (par exemple, une
# MAGIC modalité rare qui n'apparaît que dans le test influencerait quand même
# MAGIC l'encodage) — une fuite discrète mais réelle.

# COMMAND ----------

from sklearn.model_selection import train_test_split

X = df[FEATURES_FINALES].copy()
y = df[LABEL].copy()

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"Train : {len(X_train):,} lignes — taux fraude {y_train.mean()*100:.3f}%")
print(f"Test  : {len(X_test):,} lignes — taux fraude {y_test.mean()*100:.3f}%")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Encodage des variables catégorielles (fit sur train uniquement)

# COMMAND ----------

from sklearn.preprocessing import OrdinalEncoder

X_train[FEATURES_CAT] = X_train[FEATURES_CAT].fillna("Inconnu")
X_test[FEATURES_CAT] = X_test[FEATURES_CAT].fillna("Inconnu")

encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
X_train[FEATURES_CAT] = encoder.fit_transform(X_train[FEATURES_CAT])
X_test[FEATURES_CAT] = encoder.transform(X_test[FEATURES_CAT])

print("Modalités apprises par catégorie :")
for col, cats in zip(FEATURES_CAT, encoder.categories_):
    print(f"  {col}: {list(cats)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Sauvegarde des ensembles train/test et de l'encodeur
# MAGIC
# MAGIC L'encodeur est sauvegardé à part — le notebook de scoring batch (06) devra
# MAGIC réutiliser **exactement le même encodeur** (pas en réentraîner un nouveau)
# MAGIC pour rester cohérent avec le modèle.

# COMMAND ----------

import joblib

train_df = X_train.copy()
train_df[LABEL] = y_train
test_df = X_test.copy()
test_df[LABEL] = y_test

spark.createDataFrame(train_df).write.format("delta").mode("overwrite").saveAsTable(
    f"pfa_data.ml_outputs.ml_train_set"
)
spark.createDataFrame(test_df).write.format("delta").mode("overwrite").saveAsTable(
    f"pfa_data.ml_outputs.ml_test_set"
)

encoder_path = "pfa_data.ml_outputs.ml_ordinal_encoder.joblib"
joblib.dump(encoder, encoder_path)

print("✅ ml_train_set, ml_test_set et l'encodeur sauvegardés")
print(f"   Encodeur : {encoder_path}")

# COMMAND ----------

display(train_df)
display(test_df)

# COMMAND ----------


## 6. Import des ensembles train et test

#Chargement des tables `ml_train_set` et `ml_test_set` sauvegardées précédemment.

train  =  spark.table("pfa_data.ml_outputs.ml_train_set").toPandas()
test   =  spark.table("pfa_data.ml_outputs.ml_test_set").toPandas()



# COMMAND ----------

# Distribution croisée du label dans train et test

print("Distribution du label (fraud_flag) dans train :")
train_label_counts = train[LABEL].value_counts().sort_index()
train_label_pct = train[LABEL].value_counts(normalize=True).sort_index() * 100
train_dist = pd.DataFrame({
    'Effectif': train_label_counts,
    'Pourcentage': train_label_pct
})
print(train_dist)
print(f"\nTotal train : {len(train):,} lignes\n")

print("Distribution du label (fraud_flag) dans test :")
test_label_counts = test[LABEL].value_counts().sort_index()
test_label_pct = test[LABEL].value_counts(normalize=True).sort_index() * 100
test_dist = pd.DataFrame({
    'Effectif': test_label_counts,
    'Pourcentage': test_label_pct
})
print(test_dist)
print(f"\nTotal test : {len(test):,} lignes\n")

# Tableau croisé dynamique train vs test
print("Tableau croisé dynamique - Distribution comparée :")
crosstab = pd.DataFrame({
    'Train_Effectif': train_label_counts,
    'Train_%': train_label_pct,
    'Test_Effectif': test_label_counts,
    'Test_%': test_label_pct
})
print(crosstab)

# COMMAND ----------

import joblib

encoder_path = "/Workspace/Users/allahjaphet9@gmail.com/PFA_PROJECT/ML/pfa_data.ml_outputs.ml_ordinal_encoder.joblib"
encoder = joblib.load(encoder_path)

print("✅ Encodeur chargé avec succès")
print(f"Type : {type(encoder)}")
print(f"Catégories apprises :")
for col, cats in zip(FEATURES_CAT, encoder.categories_):
    print(f"  {col}: {list(cats)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Résumé
# MAGIC
# MAGIC | Élément | Valeur |
# MAGIC | :--- | :--- |
# MAGIC | Features finales | 16 variables (9 numériques, 4 catégorielles encodées, 3 binaires) |
# MAGIC | Split | `train_test_split` stratifié sur `fraud_flag`, 80/20, **avant** encodage |
# MAGIC | Encodage | `OrdinalEncoder`, fit sur train uniquement, sauvegardé pour réutilisation |
# MAGIC | Tables sauvegardées | `ml_train_set`, `ml_test_set` |
# MAGIC
# MAGIC **Prochaine étape** : notebook `05e_ml_modele` — entraînement sur
# MAGIC `ml_train_set`, évaluation sur `ml_test_set`, tracking MLflow et registre.
# MAGIC