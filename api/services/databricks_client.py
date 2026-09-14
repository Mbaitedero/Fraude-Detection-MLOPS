"""
Connexions Databricks + cache des appels coûteux.
"""

import os
import joblib
import mlflow
import pandas as pd
from cachetools import TTLCache
from databricks import sql as databricks_sql
from functools import wraps
from mlflow.tracking import MlflowClient

from shared.config import Config

# ─────────────────────────────────────────────────────────────
# Auth Databricks
# ─────────────────────────────────────────────────────────────

os.environ.setdefault("DATABRICKS_HOST", Config.DATABRICKS_HOST)
os.environ.setdefault("DATABRICKS_TOKEN", Config.DATABRICKS_TOKEN)

mlflow.set_tracking_uri("databricks")
mlflow.set_registry_uri("databricks-uc")

_client = MlflowClient()

# Cache en mémoire du modèle (évite de recharger à chaque requête)
_cache = {"model": None, "feature_names": None, "encoder": None}


# ─────────────────────────────────────────────────────────────
# Décorateur de cache TTL
# ─────────────────────────────────────────────────────────────

def cached(ttl_seconds=300, maxsize=100):
    """Cache les résultats d'une fonction pendant ttl_seconds."""
    def decorator(func):
        cache = TTLCache(maxsize=maxsize, ttl=ttl_seconds)

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            if key in cache:
                return cache[key]
            result = func(*args, **kwargs)
            cache[key] = result
            return result

        wrapper.cache_clear = cache.clear
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────
# Client MLflow
# ─────────────────────────────────────────────────────────────

def get_mlflow_client():
    return _client


# ─────────────────────────────────────────────────────────────
# Connexion SQL
# ─────────────────────────────────────────────────────────────

def get_sql_connection():
    """Nouvelle connexion à chaque appel."""
    return databricks_sql.connect(
        server_hostname=Config.DATABRICKS_HOST.replace("https://", ""),
        http_path=Config.DATABRICKS_HTTP_PATH,
        access_token=Config.DATABRICKS_TOKEN,
    )


def run_query(query: str) -> pd.DataFrame:
    with get_sql_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall_arrow().to_pandas()


# ─────────────────────────────────────────────────────────────
# Modèle champion (avec cache mémoire + flag force_reload)
# ─────────────────────────────────────────────────────────────

def load_champion_model(force_reload: bool = False):
    if _cache["model"] is None or force_reload:
        model_uri = f"models:/{Config.MODEL_NAME}@{Config.MODEL_ALIAS}"
        _cache["model"] = mlflow.sklearn.load_model(model_uri)
        model_info = mlflow.models.get_model_info(model_uri)
        _cache["feature_names"] = [
            inp.name for inp in model_info.signature.inputs.inputs
        ]
    return _cache["model"], _cache["feature_names"]


def load_encoder(force_reload: bool = False):
    if _cache["encoder"] is None or force_reload:
        _cache["encoder"] = joblib.load(Config.ENCODER_PATH)
    return _cache["encoder"]


# ─────────────────────────────────────────────────────────────
# Champion info (avec cache TTL 5 min)
# ─────────────────────────────────────────────────────────────

@cached(ttl_seconds=300)
def get_champion_info():
    """Version, run, métriques du champion actuel."""
    version = _client.get_model_version_by_alias(
        Config.MODEL_NAME, Config.MODEL_ALIAS
    )
    run = _client.get_run(version.run_id)
    return version, run


# ─────────────────────────────────────────────────────────────
# Versions (avec cache TTL 1 min)
# ─────────────────────────────────────────────────────────────

@cached(ttl_seconds=60)
def get_all_versions_df() -> pd.DataFrame:
    versions = _client.search_model_versions(f"name='{Config.MODEL_NAME}'")
    rows = []
    for v in versions:
        try:
            run = _client.get_run(v.run_id)
            aliases = _client.get_model_version(
                Config.MODEL_NAME, v.version
            ).aliases
            rows.append({
                "version": v.version,
                "alias": ", ".join(aliases) if aliases else "—",
                "run_name": run.data.tags.get("mlflow.runName", "—"),
                "pr_auc": run.data.metrics.get("pr_auc"),
                "roc_auc": run.data.metrics.get("roc_auc"),
                "lift": run.data.metrics.get("lift"),
                "date": pd.to_datetime(
                    run.info.start_time, unit="ms"
                ).isoformat(),
                "run_id": v.run_id,
                "user": run.data.tags.get("mlflow.user", "inconnu"),
            })
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("version", ascending=False)


# ─────────────────────────────────────────────────────────────
# Promotion
# ─────────────────────────────────────────────────────────────

def promote_version(version: str):
    """Promeut une version en champion et invalide les caches."""
    _client.set_registered_model_alias(
        Config.MODEL_NAME, Config.MODEL_ALIAS, version
    )
    load_champion_model(force_reload=True)
    get_champion_info.cache_clear()
    get_all_versions_df.cache_clear()