# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # 05e — Entraînement du modèle (jeu de features final)
# MAGIC
# MAGIC Étape 5/5 : Exploration → Nettoyage → Analyse → Features → **Modèle**
# MAGIC
# MAGIC Entraîne sur `ml_train_set`, évalue sur `ml_test_set` (déjà splittés et
# MAGIC encodés à l'étape précédente — aucune transformation supplémentaire ici,
# MAGIC pour éviter toute fuite entre les deux ensembles).

# COMMAND ----------

import mlflow
mlflow.end_run()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuration

# COMMAND ----------


import mlflow
mlflow.set_registry_uri("databricks-uc")

CATALOG = "pfa_data"
SCHEMA = "ml_outputs"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.fraud_detection_model"
EXPERIMENT_NAME = "/Shared/pfa_fraud_detection"
mlflow.set_experiment(EXPERIMENT_NAME)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Chargement des ensembles déjà préparés

# COMMAND ----------

import pandas as pd
import numpy as np

train_df = spark.table(f"pfa_data.ml_outputs.ml_train_set").toPandas()
test_df = spark.table(f"pfa_data.ml_outputs.ml_test_set").toPandas()

LABEL = "fraud_flag"
FEATURES_FINALES = [c for c in train_df.columns if c != LABEL]

X_train, y_train = train_df[FEATURES_FINALES], train_df[LABEL]
X_test, y_test = test_df[FEATURES_FINALES], test_df[LABEL]

print(f"Features ({len(FEATURES_FINALES)}) : {FEATURES_FINALES}")
print(f"Train : {len(X_train):,} — taux fraude {y_train.mean()*100:.3f}%")
print(f"Test  : {len(X_test):,} — taux fraude {y_test.mean()*100:.3f}%")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Entraînement avec tracking MLflow

# COMMAND ----------

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score, roc_auc_score, precision_recall_curve,
    classification_report, confusion_matrix,
)
from sklearn.inspection import permutation_importance
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd

with mlflow.start_run(run_name="hgb_fraud_v2_14features") as run:

    # --- Gestion du déséquilibre ---
    sample_weight = np.where(y_train == 1, 15, 1)

    # --- Paramètres ---
    params = {
        "max_iter": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "l2_regularization": 1.0,
        "random_state": 42,
    }
    mlflow.log_params(params)
    mlflow.log_param("n_features", len(FEATURES_FINALES))
    mlflow.log_param("features", str(FEATURES_FINALES))
    mlflow.log_param("split_method", "train_test_split stratifié 80/20")
    mlflow.log_param("n_train", len(X_train))
    mlflow.log_param("n_test", len(X_test))
    mlflow.log_param("sample_weight_fraude", 15)

    # --- Entraînement ---
    model = HistGradientBoostingClassifier(**params)
    model.fit(X_train, y_train, sample_weight=sample_weight)

    # --- Prédictions ---
    y_proba = model.predict_proba(X_test)[:, 1]

    # --- Métriques globales ---
    pr_auc = average_precision_score(y_test, y_proba)
    roc_auc = roc_auc_score(y_test, y_proba)
    baseline_pr_auc = y_test.mean()
    lift = pr_auc / baseline_pr_auc if baseline_pr_auc > 0 else 0.0

    # --- Courbe précision-rappel ---
    precisions, recalls, thresholds = precision_recall_curve(y_test, y_proba)

    # Recall à precision >= 80%
    mask_80 = precisions >= 0.80
    recall_at_precision_80 = recalls[mask_80].max() if mask_80.any() else 0.0

    # --- Seuil optimal F1 ---
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-9)
    best_idx_f1 = np.argmax(f1_scores[:-1])
    best_threshold_f1 = thresholds[best_idx_f1]
    best_f1 = f1_scores[best_idx_f1]

    # --- Seuil optimal coût métier ---
    cout_fp, cout_fn = 10, 1000   # MAD
    costs = []
    for t in thresholds:
        y_pred_t = (y_proba >= t).astype(int)
        fp = ((y_pred_t == 1) & (y_test == 0)).sum()
        fn = ((y_pred_t == 0) & (y_test == 1)).sum()
        costs.append(fp * cout_fp + fn * cout_fn)
    best_idx_cost = int(np.argmin(costs))
    best_threshold_cost = thresholds[best_idx_cost]
    min_cost = costs[best_idx_cost]

    # --- Métriques à logger ---
    mlflow.log_metric("pr_auc", pr_auc)
    mlflow.log_metric("roc_auc", roc_auc)
    mlflow.log_metric("recall_at_precision_80", recall_at_precision_80)
    mlflow.log_metric("baseline_pr_auc", baseline_pr_auc)
    mlflow.log_metric("lift", lift)
    mlflow.log_metric("best_threshold_f1", best_threshold_f1)
    mlflow.log_metric("best_f1", best_f1)
    mlflow.log_metric("best_threshold_cost", best_threshold_cost)
    mlflow.log_metric("min_cost_mad", min_cost)

    # --- Rapport au seuil par défaut ---
    y_pred_default = (y_proba >= 0.5).astype(int)
    print("="*60)
    print("SEUIL PAR DÉFAUT (0.5)")
    print("="*60)
    print(classification_report(y_test, y_pred_default, target_names=["Normal", "Fraude"]))

    # --- Rapport au seuil optimal F1 ---
    y_pred_optimal = (y_proba >= best_threshold_f1).astype(int)
    print("\n" + "="*60)
    print(f"SEUIL OPTIMAL F1 ({best_threshold_f1:.4f})")
    print("="*60)
    print(classification_report(y_test, y_pred_optimal, target_names=["Normal", "Fraude"]))

    # --- Rapport au seuil optimal coût ---
    y_pred_cost = (y_proba >= best_threshold_cost).astype(int)
    print("\n" + "="*60)
    print(f"SEUIL OPTIMAL COÛT ({best_threshold_cost:.4f})")
    print("="*60)
    print(classification_report(y_test, y_pred_cost, target_names=["Normal", "Fraude"]))
    print(f"Coût total : {min_cost:,.0f} MAD")

    # --- Métriques finales ---
    print("\n" + "="*60)
    print("MÉTRIQUES GLOBALES")
    print("="*60)
    print(f"PR-AUC                    : {pr_auc:.4f}")
    print(f"ROC-AUC                   : {roc_auc:.4f}")
    print(f"Recall à precision >= 80% : {recall_at_precision_80:.4f}")
    print(f"Baseline (taux de fraude) : {baseline_pr_auc:.4f}")
    print(f"Lift vs baseline          : {lift:.2f}x")

    # --- Permutation importance ---
    sample_idx = np.random.choice(len(X_test), size=min(5000, len(X_test)), replace=False)
    perm_imp = permutation_importance(
        model, X_test.iloc[sample_idx], y_test.iloc[sample_idx],
        n_repeats=5, random_state=42, scoring="average_precision", n_jobs=-1
    )
    importance_df = pd.DataFrame({
        "feature": FEATURES_FINALES,
        "importance_mean": perm_imp.importances_mean,
        "importance_std": perm_imp.importances_std,
    }).sort_values("importance_mean", ascending=False)
    print("\n" + "="*60)
    print("TOP 10 FEATURES (Permutation Importance)")
    print("="*60)
    print(importance_df.head(10).to_string(index=False))
    importance_df.to_csv("/tmp/feature_importance.csv", index=False)
    mlflow.log_artifact("/tmp/feature_importance.csv")

    # --- Sauvegarde des prédictions ---
    predictions_df = X_test.copy()
    predictions_df["y_true"] = y_test.values
    predictions_df["y_proba"] = y_proba
    predictions_df["y_pred_default"] = y_pred_default
    predictions_df["y_pred_optimal"] = y_pred_optimal
    predictions_df.to_csv("/tmp/predictions_test.csv", index=False)
    mlflow.log_artifact("/tmp/predictions_test.csv")

    # --- Signature et logging du modèle ---
    input_example = X_train.head(5)
    signature = mlflow.models.infer_signature(
        input_example,
        model.predict_proba(input_example)[:, 1]
    )
    mlflow.sklearn.log_model(
        model,
        name="model",                              # ← corrigé
        signature=signature,
        input_example=input_example,
        registered_model_name=MODEL_NAME,
    )

    run_id = run.info.run_id
    print(f"\n✅ Run MLflow : {run_id}")

# COMMAND ----------

# ============================================================
# SAUVEGARDE PERSISTANTE DANS pfa_data.ml_outputs
# (à exécuter APRÈS l'entraînement — le modèle est déjà loggé)
# ============================================================

import pandas as pd
import mlflow
from mlflow.tracking import MlflowClient

# --- Récupération automatique du dernier run MLflow ---
client = MlflowClient()

# Récupérer run_id depuis la variable de session (Cell 8)
if 'run_id' not in dir():
    # Fallback : prendre le dernier run de l'expérience
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment:
        experiment_id = experiment.experiment_id
    else:
        raise ValueError(f"Expérience '{EXPERIMENT_NAME}' introuvable. Exécutez d'abord Cell 4.")
    
    # Récupérer le dernier run terminé
    runs = mlflow.search_runs(
        experiment_ids=[experiment_id],
        order_by=["start_time DESC"],
        max_results=1,
    )
    if len(runs) == 0:
        raise ValueError(f"Aucun run trouvé dans l'expérience '{EXPERIMENT_NAME}'. Exécutez d'abord Cell 8.")
    run_id = runs.iloc[0]["run_id"]

print(f"📌 Dernier run MLflow : {run_id}")


# ============================================================
# 1. Feature importance → Delta
# ============================================================
spark.createDataFrame(importance_df) \
    .write.mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable("pfa_data.ml_outputs.feature_importance")
print("✅ feature_importance → pfa_data.ml_outputs.feature_importance")


# ============================================================
# 2. Prédictions → Delta
# ============================================================
spark.createDataFrame(predictions_df) \
    .write.mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable("pfa_data.ml_outputs.predictions_test")
print("✅ predictions_test → pfa_data.ml_outputs.predictions_test")


# ============================================================
# 3. Métriques du modèle → Delta
# ============================================================
metrics_df = pd.DataFrame([{
    "run_id": run_id,
    "model_name": MODEL_NAME,
    "pr_auc": float(pr_auc),
    "roc_auc": float(roc_auc),
    "baseline_pr_auc": float(baseline_pr_auc),
    "lift": float(lift),
    "recall_at_precision_80": float(recall_at_precision_80),
    "best_threshold_f1": float(best_threshold_f1),
    "best_f1": float(best_f1),
    "best_threshold_cost": float(best_threshold_cost),
    "min_cost_mad": float(min_cost),
    "n_train": int(len(X_train)),
    "n_test": int(len(X_test)),
    "n_features": int(len(FEATURES_FINALES)),
    "date_entrainement": pd.Timestamp.now(),
}])

spark.createDataFrame(metrics_df) \
    .write.mode("append") \
    .option("mergeSchema", "true") \
    .saveAsTable("pfa_data.ml_outputs.model_metrics")
print("✅ model_metrics → pfa_data.ml_outputs.model_metrics")


# ============================================================
# 4. Vérification
# ============================================================
print("\n" + "=" * 60)
print("✅ SAUVEGARDE TERMINÉE")
print("=" * 60)
print(f"feature_importance : {spark.table('pfa_data.ml_outputs.feature_importance').count()} lignes")
print(f"predictions_test   : {spark.table('pfa_data.ml_outputs.predictions_test').count()} lignes")
print(f"model_metrics      : {spark.table('pfa_data.ml_outputs.model_metrics').count()} lignes")

print("\n--- Feature Importance ---")
display(spark.table("pfa_data.ml_outputs.feature_importance"))

print("\n--- Métriques du modèle ---")
display(spark.table("pfa_data.ml_outputs.model_metrics"))

# COMMAND ----------

import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix

# Matrice de confusion au seuil optimal F1
cm = confusion_matrix(y_test, y_pred_optimal)

plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
            xticklabels=['Normal', 'Fraude'], 
            yticklabels=['Normal', 'Fraude'])
plt.title(f'Matrice de confusion (seuil optimal F1 = {best_threshold_f1:.4f})')
plt.ylabel('Vraie classe')
plt.xlabel('Classe prédite')
plt.tight_layout()
plt.show()

print("\nInterprétation :")
print(f"Vrais Négatifs (TN)  : {cm[0,0]:,} transactions normales correctement identifiées")
print(f"Faux Positifs (FP)   : {cm[0,1]:,} transactions normales classées comme fraude")
print(f"Faux Négatifs (FN)   : {cm[1,0]:,} fraudes manquées")
print(f"Vrais Positifs (TP)  : {cm[1,1]:,} fraudes correctement détectées")

# COMMAND ----------

predictions_df = X_test.copy()
predictions_df["y_true"] = y_test.values
predictions_df["y_proba"] = y_proba
predictions_df["y_pred"] = y_pred_optimal
predictions_df["montant"] = test_df["montant"].values  # si dispo


spark.createDataFrame(predictions_df).write.mode("overwrite") \
    .saveAsTable("pfa_data.ml_outputs.predictions_test")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Passerelle de validation (gate sur le lift)

# COMMAND ----------

from mlflow.tracking import MlflowClient

client = MlflowClient()

SEUIL_LIFT_MINIMUM = 2.0

versions = client.search_model_versions(f"name='{MODEL_NAME}'")
derniere_version = max(versions, key=lambda v: int(v.version)).version

if lift >= SEUIL_LIFT_MINIMUM:
    client.set_registered_model_alias(MODEL_NAME, "champion", derniere_version)
    print(f"✅ Version {derniere_version} promue en 'champion' (lift {lift:.2f}x >= seuil {SEUIL_LIFT_MINIMUM}x)")
else:
    client.set_registered_model_alias(MODEL_NAME, "challenger", derniere_version)
    print(f"⚠️ Version {derniere_version} taguée 'challenger' (lift {lift:.2f}x < seuil {SEUIL_LIFT_MINIMUM}x)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Interprétabilité — importance des features par permutation

# COMMAND ----------

from sklearn.inspection import permutation_importance

perm_result = permutation_importance(
    model, X_test, y_test, n_repeats=5, random_state=42, scoring="average_precision"
)

importance_df = pd.DataFrame({
    "feature": FEATURES_FINALES,
    "importance_mean": perm_result.importances_mean,
    "importance_std": perm_result.importances_std,
}).sort_values("importance_mean", ascending=False)

print("Importance des features (permutation, scoring PR-AUC) :")
print(importance_df.to_string(index=False))

mlflow.log_table(importance_df, artifact_file="feature_importance.json")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Résumé
# MAGIC
# MAGIC | Élément | Valeur |
# MAGIC | :--- | :--- |
# MAGIC | Modèle | `HistGradientBoostingClassifier` |
# MAGIC | Features | 14 variables (jeu final, cf. notebook 05d) |
# MAGIC | Split | `train_test_split` stratifié, préparé en amont (05d) |
# MAGIC | Tracking | MLflow, run `hgb_fraud_v2_14features` |
# MAGIC | Registre | `pfa_data.ml_outputs.fraud_detection_model`, alias `champion`/`challenger` selon le lift |
# MAGIC
# MAGIC