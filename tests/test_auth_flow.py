"""
Tests du flux complet d'authentification (signup → login → logout).
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch


@pytest.fixture(scope="function")
def temp_db():
    """Base de données temporaire."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    with patch("ui.auth.database.DB_PATH", Path(tmp.name)):
        from ui.auth import database
        database.init_db()
        yield database
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


class TestAuthFlow:

    def test_full_signup_login_flow(self, temp_db):
        """Flux complet : inscription → connexion → vérification."""
        # 1. Inscription (mot de passe ≥ 6 caractères)
        success, user_id = temp_db.create_user(
            "Dupont", "Jean", "jean@flow.com", "0612345678",
            "Paris", "password123"
        )
        assert success, "L'inscription doit réussir"
        assert user_id > 0

        # 2. Connexion
        success, user = temp_db.authenticate("jean@flow.com", "password123")
        assert success, "La connexion doit réussir"
        assert user["id"] == user_id
        assert user["email"] == "jean@flow.com"

        # 3. Vérifier les préférences par défaut
        assert user["langue"] == "fr"
        assert user["theme"] == "light"
        assert user["role"] == "analyst"

    def test_login_then_change_preferences(self, temp_db):
        """Connexion → modifier préférences → vérifier persistance."""
        temp_db.create_user("A", "B", "a@test.com", "", "", "password123")

        # Login
        success, user = temp_db.authenticate("a@test.com", "password123")
        assert success
        user_id = user["id"]

        # Modifier préférences
        temp_db.update_user_preferences(user_id, langue="en", theme="dark")

        # Vérifier
        user_after = temp_db.get_user(user_id)
        assert user_after is not None
        assert user_after["langue"] == "en"
        assert user_after["theme"] == "dark"

    def test_multiple_users_isolation(self, temp_db):
        """Plusieurs utilisateurs : isolation des données."""
        # ⭐ FIX : mots de passe ≥ 6 caractères + assert sur le succès
        success1, uid1 = temp_db.create_user(
            "User1", "A", "user1@test.com", "", "", "password1"
        )
        success2, uid2 = temp_db.create_user(
            "User2", "B", "user2@test.com", "", "", "password2"
        )
        assert success1, f"Création user1 échouée : {uid1}"
        assert success2, f"Création user2 échouée : {uid2}"
        assert uid1 != uid2, "Les deux utilisateurs doivent avoir des IDs différents"

        # Chacun change ses préférences
        temp_db.update_user_preferences(uid1, langue="en")
        temp_db.update_user_preferences(uid2, theme="dark")

        # Vérifier l'isolation
        user1 = temp_db.get_user(uid1)
        user2 = temp_db.get_user(uid2)
        assert user1 is not None, "user1 doit exister"
        assert user2 is not None, "user2 doit exister"

        assert user1["langue"] == "en"
        assert user1["theme"] == "light"   # non modifié
        assert user2["langue"] == "fr"     # non modifié
        assert user2["theme"] == "dark"

    def test_admin_can_manage_users(self, temp_db):
        """Un admin peut gérer les utilisateurs."""
        # Créer un admin
        success_a, admin_id = temp_db.create_user(
            "Admin", "Root", "admin@test.com", "", "", "admin123", role="admin"
        )
        assert success_a
        # Créer un user normal
        success_u, user_id = temp_db.create_user(
            "User", "Normal", "user@test.com", "", "", "user1234"
        )
        assert success_u

        # Admin peut promouvoir
        temp_db.update_user_role(user_id, "admin")
        user = temp_db.get_user(user_id)
        assert user["role"] == "admin"

        # Admin peut désactiver
        temp_db.toggle_user_active(user_id)
        user = temp_db.get_user(user_id)
        assert user["actif"] is False

        # Vérifier qu'un compte désactivé ne peut plus se connecter
        success, msg = temp_db.authenticate("user@test.com", "user1234")
        assert success is False
        assert "désactivé" in msg.lower()

        # Admin peut supprimer
        temp_db.delete_user(user_id)
        assert temp_db.get_user(user_id) is None


class TestAlertsFlow:

    def test_fraud_alert_creation_and_read(self, temp_db):
        """Créer une alerte → vérifier non lue → marquer lue."""
        success, user_id = temp_db.create_user(
            "A", "B", "a@test.com", "", "", "password123"
        )
        assert success

        # Créer alerte de fraude
        alert_id = temp_db.create_alert(
            user_id=user_id,
            transaction_data={"montant": 50000, "type": "Virement"},
            score=0.95,
            decision="FRAUDE",
            niveau_risque="Très élevé"
        )
        assert alert_id is not None
        assert alert_id > 0

        # Vérifier
        assert temp_db.count_unread_alerts(user_id) == 1
        alerts = temp_db.get_alerts(user_id, unread_only=True)
        assert len(alerts) == 1
        assert alerts[0]["score"] == 0.95
        assert alerts[0]["lu"] is False

        # Marquer comme lue
        temp_db.mark_alert_read(alert_id)
        assert temp_db.count_unread_alerts(user_id) == 0