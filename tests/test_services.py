"""
Tests des services : databricks_client + model_service.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
import pandas as pd


# ─────────────────────────────────────────────────────────────
# TESTS : databricks_client
# ─────────────────────────────────────────────────────────────

class TestDatabricksClient:

    @patch("api.services.databricks_client._client")
    def test_get_champion_info(self, mock_client):
        from api.services import databricks_client as dbx
        
        mock_version = MagicMock()
        mock_version.version = "4"
        mock_version.run_id = "run_abc"
        
        mock_run = MagicMock()
        mock_run.data.metrics = {"pr_auc": 0.72}
        
        mock_client.get_model_version_by_alias.return_value = mock_version
        mock_client.get_run.return_value = mock_run
        
        version, run = dbx.get_champion_info()
        
        assert version.version == "4"
        assert run.data.metrics["pr_auc"] == 0.72

    @patch("api.services.databricks_client._client")
    def test_get_all_versions_df(self, mock_client):
        from api.services import databricks_client as dbx
        
        v1 = MagicMock(); v1.version = "1"; v1.run_id = "run_1"
        v2 = MagicMock(); v2.version = "2"; v2.run_id = "run_2"
        mock_client.search_model_versions.return_value = [v1, v2]
        
        def mock_get_run(run_id):
            run = MagicMock()
            run.data.metrics = {"pr_auc": 0.5, "roc_auc": 0.9, "lift": 20}
            run.data.tags = {"mlflow.runName": f"run_{run_id}", "mlflow.user": "test"}
            run.info.start_time = 1700000000000
            return run
        
        mock_client.get_run.side_effect = mock_get_run
        
        def mock_get_version(name, version):
            mv = MagicMock()
            mv.aliases = ["champion"] if version == "2" else []
            return mv
        
        mock_client.get_model_version.side_effect = mock_get_version
        
        df = dbx.get_all_versions_df()
        
        assert not df.empty
        assert len(df) == 2
        assert df.iloc[0]["version"] == "2"

    @patch("api.services.databricks_client._client")
    def test_promote_version(self, mock_client):
        from api.services import databricks_client as dbx
        dbx._cache["model"] = None
        
        with patch("api.services.databricks_client.load_champion_model") as mock_load:
            dbx.promote_version("3")
            mock_client.set_registered_model_alias.assert_called_once_with(
                "pfa_data.ml_outputs.fraud_detection_model", "champion", "3",
            )


# ─────────────────────────────────────────────────────────────
# TESTS : model_service
# ─────────────────────────────────────────────────────────────

class TestModelService:

    @patch("api.services.model_service.dbx.load_encoder")
    @patch("api.services.model_service.dbx.load_champion_model")
    def test_predict_transaction_fraude(self, mock_load_model, mock_load_enc):
        from api.services.model_service import predict_transaction
        
        model = MagicMock()
        model.predict_proba.return_value = np.array([[0.05, 0.95]])
        
        encoder = MagicMock()
        encoder.feature_names_in_ = ["type_transaction", "mode_paiement",
                                       "sens_operation", "tranche_horaire"]
        encoder.transform.return_value = np.array([[1, 1, 0, 2]])
        
        mock_load_model.return_value = (model, ["montant", "is_night"])
        mock_load_enc.return_value = encoder
        
        payload = {
            "montant": 50000, "type_transaction": "Virement",
            "mode_paiement": "Virement", "heure": 3,
            "is_weekend": 1, "est_international": 1,
        }
        
        result = predict_transaction(payload)
        
        assert result["score"] == 0.95
        assert result["decision"] == "FRAUDE"
        assert result["est_fraude"] is True
        assert result["niveau_risque"] == "Très élevé"
        assert result["pourcentage"] == 95.0

    @patch("api.services.model_service.dbx.load_encoder")
    @patch("api.services.model_service.dbx.load_champion_model")
    def test_predict_transaction_normal(self, mock_load_model, mock_load_enc):
        from api.services.model_service import predict_transaction
        
        model = MagicMock()
        model.predict_proba.return_value = np.array([[0.92, 0.08]])
        
        encoder = MagicMock()
        encoder.feature_names_in_ = ["type_transaction", "mode_paiement",
                                       "sens_operation", "tranche_horaire"]
        encoder.transform.return_value = np.array([[0, 1, 1, 1]])
        
        mock_load_model.return_value = (model, ["montant", "is_night"])
        mock_load_enc.return_value = encoder
        
        payload = {
            "montant": 100, "type_transaction": "Paiement",
            "mode_paiement": "Carte", "heure": 14,
            "is_weekend": 0, "est_international": 0,
        }
        
        result = predict_transaction(payload)
        
        assert result["score"] == 0.08
        assert result["decision"] == "NORMAL"
        assert result["est_fraude"] is False
        assert result["niveau_risque"] == "Faible"

    @patch("api.services.model_service.dbx.load_encoder")
    @patch("api.services.model_service.dbx.load_champion_model")
    def test_predict_feature_engineering(self, mock_load_model, mock_load_enc):
        """Vérifie le feature engineering :
        - Numériques (is_night, is_weekend, est_international) sur le df final
        - Catégorielles (sens_operation, tranche_horaire) AVANT encodage."""
        from api.services.model_service import predict_transaction

        model = MagicMock()
        model.predict_proba.return_value = np.array([[0.5, 0.5]])

        # ─── Capture des catégorielles AVANT encodage ───
        captured_cat = []

        def mock_transform(df):
            captured_cat.append(df.copy())
            return np.array([[1, 1, 0, 2]])

        encoder = MagicMock()
        encoder.feature_names_in_ = ["type_transaction", "mode_paiement",
                                    "sens_operation", "tranche_horaire"]
        encoder.transform.side_effect = mock_transform

        # Liste complète des features attendues (numériques + catégorielles)
        feature_names = [
            "montant", "frais_transaction", "ecart_relatif_montant",
            "ratio_montant_revenu", "taux_utilisation_30j",
            "montant_moyen_client_30j", "ecart_type_client_30j",
            "nb_transactions_client_30j", "montant_cumule_client",
            "type_transaction", "mode_paiement", "sens_operation", "tranche_horaire",
            "is_night", "is_weekend", "est_international",
        ]
        mock_load_model.return_value = (model, feature_names)
        mock_load_enc.return_value = encoder

        # ═══════════════════════════════════════════════════════
        # TEST 1 — 3h du matin, Retrait (doit être Débit/Nuit)
        # ═══════════════════════════════════════════════════════
        predict_transaction({
            "montant": 1000, "type_transaction": "Retrait",
            "mode_paiement": "Carte", "heure": 3,
            "is_weekend": 0, "est_international": 0,
        })

        # ─── A) Numériques : sur le df FINAL (avant predict_proba) ───
        final_input = model.predict_proba.call_args[0][0]
        assert final_input.iloc[0]["is_night"] == 1
        assert final_input.iloc[0]["is_weekend"] == 0
        assert final_input.iloc[0]["est_international"] == 0

        # ─── B) Catégorielles : sur le df capturé AVANT encodage ───
        cat_before = captured_cat[0]
        assert cat_before.iloc[0]["sens_operation"] == "Débit"
        assert cat_before.iloc[0]["tranche_horaire"] == "Nuit"
        assert cat_before.iloc[0]["type_transaction"] == "Retrait"

        # ═══════════════════════════════════════════════════════
        # TEST 2 — 14h, Virement (doit être Crédit/Après-midi)
        # ═══════════════════════════════════════════════════════
        predict_transaction({
            "montant": 1000, "type_transaction": "Virement",
            "mode_paiement": "Virement", "heure": 14,
            "is_weekend": 0, "est_international": 0,
        })

        final_input = model.predict_proba.call_args[0][0]
        assert final_input.iloc[0]["is_night"] == 0

        cat_before = captured_cat[1]
        assert cat_before.iloc[0]["sens_operation"] == "Crédit"
        assert cat_before.iloc[0]["tranche_horaire"] == "Après-midi"


class TestConfig:

    def test_config_model_name(self):
        from shared.config import Config
        assert Config.MODEL_NAME == "pfa_data.ml_outputs.fraud_detection_model"
        assert Config.CATALOG == "pfa_data"
        assert Config.SCHEMA == "ml_outputs"
        assert Config.MODEL_ALIAS == "champion"

    def test_config_check_missing(self):
        from shared.config import Config
        with patch.object(Config, "DATABRICKS_HOST", ""):
            with pytest.raises(ValueError, match="Variables manquantes"):
                Config.check()