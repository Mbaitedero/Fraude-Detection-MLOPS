"""
Tests de l'API FastAPI.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_champion_info():
    version = MagicMock()
    version.version = "4"
    version.run_id = "abc123def456"
    run = MagicMock()
    run.data.metrics = {"pr_auc": 0.7215, "roc_auc": 0.9954, "lift": 53.05}
    run.data.tags = {"mlflow.user": "test_user"}
    return version, run


@pytest.fixture
def mock_model():
    model = MagicMock()
    model.predict_proba.return_value = np.array([[0.15, 0.85]])
    return model


@pytest.fixture
def mock_encoder():
    encoder = MagicMock()
    encoder.feature_names_in_ = ["type_transaction", "mode_paiement",
                                   "sens_operation", "tranche_horaire"]
    encoder.transform.return_value = np.array([[1, 1, 0, 2]])
    return encoder


# ═════════════════════════════════════════════════════════════
# TESTS EXISTANTS (inchangés)
# ═════════════════════════════════════════════════════════════

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


@patch("api.services.databricks_client.run_query")
@patch("api.services.databricks_client.load_encoder")
@patch("api.services.databricks_client.load_champion_model")
def test_health_ok(mock_load_model, mock_load_enc, mock_run_query, client, mock_model, mock_encoder):
    mock_load_model.return_value = (mock_model, ["feature1", "feature2"])
    mock_load_enc.return_value = mock_encoder
    mock_run_query.return_value = MagicMock()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@patch("api.services.databricks_client.load_champion_model")
def test_health_degraded(mock_load, client):
    mock_load.side_effect = Exception("Model not found")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


@patch("api.services.databricks_client.load_champion_model")
@patch("api.services.databricks_client.get_champion_info")
def test_model_info(mock_info, mock_load, client, mock_champion_info, mock_model):
    mock_info.return_value = mock_champion_info
    mock_load.return_value = (mock_model, ["montant", "is_night"])
    response = client.get("/model/info")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "4"
    assert data["pr_auc"] == 0.7215


@patch("api.services.model_service.dbx.load_encoder")
@patch("api.services.model_service.dbx.load_champion_model")
def test_predict_fraude(mock_load_model, mock_load_enc, client, mock_model, mock_encoder):
    mock_load_model.return_value = (mock_model, ["montant", "is_night"])
    mock_load_enc.return_value = mock_encoder
    payload = {
        "montant": 50000, "type_transaction": "Virement",
        "mode_paiement": "Virement", "heure": 3,
        "is_weekend": 1, "est_international": 1,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0.85
    assert data["decision"] == "FRAUDE"


@patch("api.services.model_service.dbx.load_encoder")
@patch("api.services.model_service.dbx.load_champion_model")
def test_predict_normal(mock_load_model, mock_load_enc, client, mock_encoder):
    model = MagicMock()
    model.predict_proba.return_value = np.array([[0.9, 0.1]])
    mock_load_model.return_value = (model, ["montant", "is_night"])
    mock_load_enc.return_value = mock_encoder
    payload = {
        "montant": 100, "type_transaction": "Paiement",
        "mode_paiement": "Carte", "heure": 14,
        "is_weekend": 0, "est_international": 0,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    assert response.json()["decision"] == "NORMAL"


def test_predict_invalid_payload(client):
    response = client.post("/predict", json={"montant": "abc"})
    assert response.status_code == 422


@patch("api.services.databricks_client.run_query")
def test_batch_ok(mock_query, client):
    import pandas as pd
    mock_df = pd.DataFrame({
        "transaction_id": ["TRX-001", "TRX-002"],
        "client_id": ["CLI-001", "CLI-002"],
        "montant": [5000, 12000],
        "fraud_proba": [0.95, 0.82],
        "fraud_predicted": [True, True],
        "date_scoring": ["2026-09-11", "2026-09-11"],
    })
    mock_query.return_value = mock_df
    response = client.get("/batch?seuil=0.5")
    assert response.status_code == 200
    assert len(response.json()) == 2


@patch("api.services.databricks_client.get_all_versions_df")
def test_versions_ok(mock_versions, client):
    import pandas as pd
    mock_df = pd.DataFrame({
        "version": ["4", "3", "2"],
        "alias": ["champion", "—", "—"],
        "run_name": ["hgb_v2", "hgb_v1", "test"],
        "pr_auc": [0.7215, 0.65, 0.58],
        "roc_auc": [0.9954, 0.98, 0.95],
        "lift": [53.05, 45.0, 30.0],
        "date": ["2026-09-11"] * 3,
        "run_id": ["abc", "def", "ghi"],
        "user": ["test"] * 3,
    })
    mock_versions.return_value = mock_df
    response = client.get("/versions")
    assert response.status_code == 200
    assert len(response.json()) == 3


@patch("api.services.databricks_client.promote_version")
def test_promote_ok(mock_promote, client):
    mock_promote.return_value = None
    response = client.post("/promote/3")
    assert response.status_code == 200
    assert response.json()["version"] == "3"


def test_openapi_schema(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/predict" in response.json()["paths"]


def test_docs_accessible(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ═════════════════════════════════════════════════════════════
# NOUVEAUX TESTS — Monitoring
# ═════════════════════════════════════════════════════════════

def test_metrics_endpoint(client):
    """L'endpoint /metrics doit exposer les métriques Prometheus."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text


def test_health_checks_all(client):
    """Le health check doit vérifier toutes les dépendances."""
    with patch("api.services.databricks_client.load_champion_model") as m1, \
         patch("api.services.databricks_client.load_encoder") as m2, \
         patch("api.services.databricks_client.run_query") as m3:
        m1.return_value = (MagicMock(), ["f1", "f2"])
        m2.return_value = MagicMock(feature_names_in_=["a", "b", "c", "d"])
        m3.return_value = MagicMock()
        response = client.get("/health")
        data = response.json()
        assert "checks" in data
        assert data["checks"]["api"] is True
