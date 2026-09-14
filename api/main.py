"""
FastAPI — API MLOps de détection de fraude.

Lancer :
    uvicorn api.main:app --reload --port 8000

Docs auto :
    http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.schemas import (
    TransactionInput, PredictionOutput, ModelInfo, HealthOutput,
)
from api.services import databricks_client as dbx
from api.services.model_service import predict_transaction
from shared.config import Config
from shared.logger import logger


# ═════════════════════════════════════════════════════════════
# LIFESPAN — Préchargement au démarrage
# ═════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge le modèle + l'encoder au démarrage."""
    logger.info("api_startup", message="Démarrage de l'API")
    try:
        model, features = dbx.load_champion_model()
        logger.info("model_loaded", n_features=len(features))

        encoder = dbx.load_encoder()
        logger.info("encoder_loaded",
                    n_categories=len(encoder.feature_names_in_))

        logger.info("api_ready", message="✨ API prête à recevoir des requêtes")
    except Exception as e:   # noqa: BLE001
        logger.error("startup_error", error=str(e), exc_info=True)

    yield

    logger.info("api_shutdown", message="Arrêt de l'API")


# ═════════════════════════════════════════════════════════════
# APP FASTAPI
# ═════════════════════════════════════════════════════════════

app = FastAPI(
    title="Fraud Detection API",
    description="API MLOps — PFA Détection de fraude bancaire",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Prometheus — expose /metrics
Instrumentator().instrument(app).expose(app)


# ═════════════════════════════════════════════════════════════
# ROUTES
# ═════════════════════════════════════════════════════════════

@app.get("/", tags=["root"])
def root():
    return {"message": "Fraud Detection API", "docs": "/docs"}


@app.get("/health", response_model=HealthOutput, tags=["monitoring"])
def health():
    """Vérifie toutes les dépendances de l'API."""
    checks = {
        "api": True,
        "model": False,
        "encoder": False,
        "databricks": False,
    }
    details = {}

    try:
        model, features = dbx.load_champion_model()
        checks["model"] = model is not None
        details["n_features"] = len(features)
    except Exception as e:  # noqa: BLE001
        details["model_error"] = str(e)[:100]

    try:
        encoder = dbx.load_encoder()
        checks["encoder"] = encoder is not None
        details["n_categories"] = len(encoder.feature_names_in_)
    except Exception as e:  # noqa: BLE001
        details["encoder_error"] = str(e)[:100]

    try:
        dbx.run_query("SELECT 1 AS ping")
        checks["databricks"] = True
    except Exception as e: # noqa: BLE001
        details["databricks_error"] = str(e)[:100]

    all_ok = all(checks.values())
    logger.info("health_check", status="ok" if all_ok else "degraded", **checks)

    return HealthOutput(
        status="ok" if all_ok else "degraded",
        model_loaded=checks["model"],
        checks=checks,
        details=details,
    )


@app.get("/model/info", response_model=ModelInfo, tags=["model"])
def model_info():
    """Informations sur le modèle en production."""
    try:
        version, run = dbx.get_champion_info()
        _, features = dbx.load_champion_model()
        return ModelInfo(
            name=Config.MODEL_NAME,
            alias=Config.MODEL_ALIAS,
            version=version.version,
            features=features,
            pr_auc=run.data.metrics.get("pr_auc"),
            roc_auc=run.data.metrics.get("roc_auc"),
            lift=run.data.metrics.get("lift"),
            run_id=version.run_id,
        )
    except Exception as e:      # noqa: BLE001
        logger.error("model_info_error", error=str(e))
        raise HTTPException(status_code=503, detail=f"Modèle indisponible : {e}")


@app.post("/predict", response_model=PredictionOutput, tags=["scoring"])
@limiter.limit("100/minute")
def predict(request: Request, transaction: TransactionInput):
    """Score une transaction."""
    logger.info("predict_request",
                montant=transaction.montant,
                type_tx=transaction.type_transaction)
    try:
        result = predict_transaction(transaction.model_dump())
        logger.info("predict_success",
                    score=result["score"],
                    decision=result["decision"])
        return PredictionOutput(**result)
    except Exception as e:  # noqa: BLE001
        logger.error("predict_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/batch", tags=["scoring"])
def batch(
    seuil: float = Query(0.5, ge=0, le=1),
    limit: int = Query(500, ge=1, le=100000),
):
    """Retourne les transactions scorées en batch avec score ≥ seuil."""
    query = f"""
        SELECT *
        FROM {Config.CATALOG}.{Config.SCHEMA}.fraud_scores_batch
        WHERE fraud_proba >= {seuil}
        ORDER BY fraud_proba DESC
        LIMIT {limit}
    """
    try:
        df = dbx.run_query(query)
        # Les jeux de données peuvent nommer la vérité terrain différemment.
        # On l'expose sous un nom stable pour le monitoring si elle existe.
        actual_candidates = (
            "fraud_flag_reel", "fraud_actual", "actual_label", "fraud_label",
            "label", "target", "is_fraud", "fraud",
        )
        actual_column = next(
            (column for column in actual_candidates if column in df.columns),
            None,
        )
        if actual_column and actual_column != "actual_label":
            df["actual_label"] = df[actual_column]
        return df.to_dict(orient="records")
    except Exception as e:    # noqa: BLE001
        logger.error("batch_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Erreur SQL : {e}")


@app.get("/versions", tags=["admin"])
def versions():
    """Liste toutes les versions du modèle enregistrées."""
    try:
        df = dbx.get_all_versions_df()
        return df.to_dict(orient="records")
    except Exception as e: # noqa: BLE001
        logger.error("versions_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Erreur : {e}")


@app.post("/promote/{version}", tags=["admin"])
def promote(version: str):
    """Promeut une version en champion."""
    try:
        dbx.promote_version(version)
        logger.info("model_promoted", version=version, alias=Config.MODEL_ALIAS)
        return {
            "status": "success",
            "version": version,
            "alias": Config.MODEL_ALIAS,
        }
    except Exception as e: # noqa: BLE001
        logger.error("promote_error", version=version, error=str(e))
        raise HTTPException(status_code=500, detail=f"Erreur promotion : {e}")