"""Diagnostic connexion Databricks + MLflow."""
import traceback
from api.services import databricks_client as dbx

print("=" * 60)
print("DIAGNOSTIC DATABRICKS + MLFLOW")
print("=" * 60)

# 1. Champion info
print("\n[1] get_champion_info()")
try:
    v, r = dbx.get_champion_info()
    print(f"   Version : {v.version}")
    print(f"   Run ID   : {v.run_id}")
    print(f"   PR-AUC   : {r.data.metrics.get('pr_auc')}")
except Exception as e:
    print(f"   {type(e).__name__}: {e}")
    traceback.print_exc()

# 2. Modèle
print("\n[2] load_champion_model()")
try:
    m, f = dbx.load_champion_model()
    print(f"   {len(f)} features")
    print(f"   {f}")
except Exception as e:
    print(f"   {type(e).__name__}: {e}")
    traceback.print_exc()

# 3. Encoder
print("\n[3] load_encoder()")
try:
    e = dbx.load_encoder()
    print(f"   {len(e.feature_names_in_)} colonnes catégorielles")
    print(f"   {list(e.feature_names_in_)}")
except Exception as e:
    print(f"   {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("FIN DU DIAGNOSTIC")
print("=" * 60)