"""
DAG complet du PFA — orchestration de bout en bout :

  1. Génération des données synthétiques (local, machine où tourne Airflow)
  2. Upload des CSV vers le volume Unity Catalog Databricks
  3. Ingestion Bronze (notebook Databricks)
  4. Transformations Silver (notebook Databricks)
  5. Gold BI + Gold ML en parallèle (notebooks Databricks)
  6. Pipeline ML séquentiel : exploration -> cleaning -> analyse -> features -> modèle
     (ce dernier notebook fait le tracking MLflow + promotion champion/challenger)
  7. Batch scoring (charge le modèle @champion depuis le Model Registry)
  8. Notification de rafraîchissement à l'API FastAPI locale (pour le dashboard Dash)

Prérequis Airflow :
  pip install apache-airflow-providers-databricks databricks-sdk

Connexion Airflow à créer AVANT de lancer ce DAG (Admin > Connections) :
  Conn Id   : databricks_default
  Conn Type : Databricks
  Host      : https://<ton-workspace>.cloud.databricks.com   (sans slash final)
  Password  : <ton personal access token Databricks>

Variables Airflow à définir (Admin > Variables), à adapter à ton environnement :
  pfa_local_project_dir   -> ex: C:\\Users\\hp\\Desktop\\PFA
  pfa_databricks_catalog  -> ex: pfa_data
  pfa_databricks_schema   -> ex: default (ou celui de tes tables bronze/silver/gold)
  pfa_databricks_volume   -> ex: pfa_raw_data
  pfa_notebook_root       -> ex: /Workspace/Users/allahjaphet9@gmail.com/PFA_PROJECT
  pfa_fastapi_refresh_url -> ex: http://localhost:8000/refresh   (optionnel)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.utils.task_group import TaskGroup
from airflow.providers.databricks.operators.databricks import DatabricksSubmitRunOperator

# ---------------------------------------------------------------------------
# Paramètres généraux
# ---------------------------------------------------------------------------

LOCAL_PROJECT_DIR = Variable.get("pfa_local_project_dir", default_var=r"C:\Users\hp\Desktop\PFA")
CATALOG = Variable.get("pfa_databricks_catalog", default_var="pfa_data")
SCHEMA = Variable.get("pfa_databricks_schema", default_var="default")
VOLUME_NAME = Variable.get("pfa_databricks_volume", default_var="pfa_raw_data")
NOTEBOOK_ROOT = Variable.get(
    "pfa_notebook_root",
    default_var="/Workspace/Users/allahjaphet9@gmail.com/PFA_PROJECT",
)
FASTAPI_REFRESH_URL = Variable.get("pfa_fastapi_refresh_url", default_var="")

FICHIERS_CSV = [
    "agences.csv", "clients.csv", "comptes.csv", "transactions.csv",
    "credits.csv", "classification_creances.csv", "ratios_liquidite.csv",
]

VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME_NAME}"

default_args = {
    "owner": "japhet",
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}

# ---------------------------------------------------------------------------
# Étape 2 — Upload des CSV vers le volume Unity Catalog (via Databricks SDK)
# ---------------------------------------------------------------------------

def upload_csvs_to_volume(**context):
    """Upload chaque CSV généré localement vers le volume Databricks.

    Utilise databricks-sdk, qui lit la connexion Airflow 'databricks_default'
    via les variables d'environnement DATABRICKS_HOST / DATABRICKS_TOKEN
    injectées juste avant (voir get_databricks_env ci-dessous), donc aucune
    config supplémentaire n'est nécessaire au-delà de la connexion Airflow.
    """
    from databricks.sdk import WorkspaceClient
    from airflow.hooks.base import BaseHook
    databricks_conn = BaseHook.get_connection("databricks_default")

    host = databricks_conn.host
    token = databricks_conn.password
    w = WorkspaceClient(host=host, token=token)

    data_dir = os.path.join(LOCAL_PROJECT_DIR, "data", "raw")
    if not os.path.isdir(data_dir):
        data_dir = os.path.join(LOCAL_PROJECT_DIR, "data")

    for nom_fichier in FICHIERS_CSV:
        chemin_local = os.path.join(data_dir, nom_fichier)
        chemin_distant = f"{VOLUME_PATH}/{nom_fichier}"
        with open(chemin_local, "rb") as f:
            w.files.upload(chemin_distant, f, overwrite=True)
        print(f"Uploadé : {chemin_local} -> {chemin_distant}")


# ---------------------------------------------------------------------------
# Helper — soumission d'un notebook Databricks en run serverless (pas de
# cluster spécifié : le workspace Free Edition n'a que du compute serverless,
# la Jobs API l'utilise automatiquement quand aucun new_cluster/existing_
# cluster_id n'est fourni).
# ---------------------------------------------------------------------------

def notebook_task(task_id: str, notebook_relative_path: str, depends_timeout_min: int = 30):
    return DatabricksSubmitRunOperator(
        task_id=task_id,
        databricks_conn_id="databricks_default",
        run_name=f"pfa_pipeline__{task_id}",
        timeout_seconds=depends_timeout_min * 60,
        notebook_task={
            "notebook_path": f"{NOTEBOOK_ROOT}/{notebook_relative_path}",
            "source": "WORKSPACE",
        },
        # Pas de new_cluster / existing_cluster_id -> run serverless
    )


# ---------------------------------------------------------------------------
# Étape 8 — notifier l'API FastAPI locale pour rafraîchir le dashboard Dash
# ---------------------------------------------------------------------------

def notify_fastapi(**context):
    if not FASTAPI_REFRESH_URL:
        print("pfa_fastapi_refresh_url non configurée — étape ignorée.")
        return
    import requests
    try:
        resp = requests.post(FASTAPI_REFRESH_URL, timeout=10)
        print(f"Notification FastAPI : {resp.status_code}")
    except Exception as e:
        print(f"Échec de la notification FastAPI (non bloquant) : {e}")


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

with DAG(
    dag_id="pfa_pipeline_bancaire_complet",
    description="Générateur -> Databricks (Bronze/Silver/Gold/ML) -> batch scoring -> notify",
    default_args=default_args,
    schedule=None,  # déclenchement manuel ; mets "@daily" si tu veux l'automatiser
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["pfa", "banque", "fraude", "databricks"],
) as dag:

    # 1. Génération locale des données
    generate_data = BashOperator(
        task_id="generate_data",
        bash_command=f'cd "{LOCAL_PROJECT_DIR}" && python generate_data.py',
    )

    # 2. Upload vers le volume Databricks
    upload_csvs = PythonOperator(
        task_id="upload_csvs_to_volume",
        python_callable=upload_csvs_to_volume,
    )

    # 3. Bronze
    bronze = notebook_task("bronze_ingestion", "BRONZE/01_bronze_ingestion")

    # 4. Silver
    silver = notebook_task("silver_transformations", "SILVER/02_silver_transformations")

    # 5. Gold BI + Gold ML (en parallèle après Silver)
    gold_bi = notebook_task("gold_bi", "GOLD/03_gold_bi")
    gold_ml = notebook_task("gold_ml", "GOLD/04_gold_ml")

    # 6. Pipeline ML séquentiel
    with TaskGroup("ml_pipeline") as ml_pipeline:
        ml_exploration = notebook_task("ml_exploration", "ML/05a_ml_exploration")
        ml_cleaning = notebook_task("ml_cleaning", "ML/05b_ml_cleaning")
        ml_analyse = notebook_task("ml_analyse", "ML/05c_ml_analyse")
        ml_features = notebook_task("ml_features", "ML/05d_ml_features")
        ml_modele = notebook_task("ml_modele", "ML/05e_ml_modele", depends_timeout_min=60)

        ml_exploration >> ml_cleaning >> ml_analyse >> ml_features >> ml_modele

    # 7. Batch scoring (charge le modèle @champion)
    batch_scoring = notebook_task("ml_batch_scoring", "ML/06_ml_batch_scoring")

    # 8. Notification FastAPI/Dash (optionnelle, best-effort)
    notify = PythonOperator(
        task_id="notify_fastapi",
        python_callable=notify_fastapi,
        trigger_rule="all_done",  # se déclenche même si la notification échoue en amont
    )

    # ------------------------------------------------------------------
    # Dépendances
    # ------------------------------------------------------------------
    generate_data >> upload_csvs >> bronze >> silver
    silver >> gold_bi
    silver >> gold_ml >> ml_pipeline >> batch_scoring >> notify
    gold_bi >> notify