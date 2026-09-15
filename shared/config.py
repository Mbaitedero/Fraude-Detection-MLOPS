
"""
Configuration centrale — chargée depuis .env.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
        # Databricks
    DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
    DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
    DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH", "")

    # Unity Catalog
    CATALOG = os.getenv("CATALOG", "pfa_data")
    SCHEMA = os.getenv("SCHEMA", "ml_outputs")
    MODEL_NAME = f"{CATALOG}.{SCHEMA}.fraud_detection_model"
    MODEL_ALIAS = os.getenv("MODEL_ALIAS", "champion")

    # Encoder
    ENCODER_PATH = os.getenv(
        "ENCODER_PATH",
        "./models/ml_ordinal_encoder.joblib",
    )

    # API
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    API_URL = os.getenv("API_URL", "http://localhost:8000")

    # Dash
    DASH_PORT = int(os.getenv("DASH_PORT", 8050))

    @classmethod
    def check(cls):
        """Vérifie que les variables critiques sont définies."""
        missing = []
        if not cls.DATABRICKS_HOST:
            missing.append("DATABRICKS_HOST")
        if not cls.DATABRICKS_TOKEN:
            missing.append("DATABRICKS_TOKEN")
        if not cls.DATABRICKS_HTTP_PATH:
            missing.append("DATABRICKS_HTTP_PATH")
        if missing:
            raise ValueError(f"Variables manquantes : {', '.join(missing)}")
