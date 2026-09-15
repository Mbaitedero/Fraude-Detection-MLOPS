"""
Tests de la base de données SQLite — Users + Alerts + Audit logs.
Utilise une base temporaire pour éviter de polluer la vraie.
"""

import contextlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(scope="function")
def temp_db():
    """Crée une base de données temporaire pour chaque test."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()

    # Patch le chemin de la DB
    with patch("ui.auth.database.DB_PATH", Path(tmp.name)):
        from ui.auth import database
        database.init_db()
        yield database

    # Nettoyage
    with contextlib.suppress(Exception):
        os.unlink(tmp.name)


# ═════════════════════════════════════════════════════════════
# TESTS : Création utilisateur
# ═════════════════════════════════════════════════════════════

class TestCreateUser:

    def test_create_user_success(self, temp_db):
        """Créer un utilisateur valide."""
        success, result = temp_db.create_user(
            nom="Dupont", prenom="Jean", email="jean@example.com",
            telephone="0612345678", adresse="Paris", password="password123"
        )
        assert success is True
        assert isinstance(result, int)  # user_id
        assert result > 0

    def test_create_user_missing_fields(self, temp_db):
        """Champs obligatoires manquants."""
        success, msg = temp_db.create_user(
            nom="", prenom="Jean", email="jean@example.com",
            telephone="", adresse="", password="pass"
        )
        assert success is False
        assert "obligatoires" in msg

    def test_create_user_short_password(self, temp_db):
        """Mot de passe trop court."""
        success, msg = temp_db.create_user(
            nom="Dupont", prenom="Jean", email="jean@example.com",
            telephone="", adresse="", password="123"
        )
        assert success is False
        assert "6 caractères" in msg

    def test_create_user_duplicate_email(self, temp_db):
        """Email déjà utilisé."""
        temp_db.create_user("A", "B", "dup@test.com", "", "", "password123")
        success, msg = temp_db.create_user("C", "D", "dup@test.com", "", "", "password456")
        assert success is False
        assert "déjà utilisé" in msg

    def test_create_user_email_lowercase(self, temp_db):
        """L'email doit être stocké en minuscules."""
        temp_db.create_user("A", "B", "TEST@EXAMPLE.COM", "", "", "password123")
        success, user = temp_db.authenticate("test@example.com", "password123")
        assert success is True
        assert user["email"] == "test@example.com"


# ═════════════════════════════════════════════════════════════
# TESTS : Authentification
# ═════════════════════════════════════════════════════════════

class TestAuthenticate:

    def test_authenticate_success(self, temp_db):
        """Authentification réussie."""
        temp_db.create_user("Dupont", "Jean", "jean@test.com", "", "", "secret123")
        success, user = temp_db.authenticate("jean@test.com", "secret123")
        assert success is True
        assert user["email"] == "jean@test.com"
        assert user["nom"] == "Dupont"
        assert user["prenom"] == "Jean"
        assert user["role"] == "analyst"
        assert user["langue"] == "fr"
        assert user["theme"] == "light"

    def test_authenticate_wrong_password(self, temp_db):
        """Mauvais mot de passe."""
        temp_db.create_user("Dupont", "Jean", "jean@test.com", "", "", "secret123")
        success, msg = temp_db.authenticate("jean@test.com", "wrong")
        assert success is False
        assert "incorrect" in msg.lower()

    def test_authenticate_unknown_email(self, temp_db):
        """Email inconnu."""
        success, msg = temp_db.authenticate("unknown@test.com", "any")
        assert success is False
        assert "incorrect" in msg.lower()

    def test_authenticate_case_insensitive(self, temp_db):
        """L'email est insensible à la casse."""
        temp_db.create_user("A", "B", "test@test.com", "", "", "pass123")
        success, _user = temp_db.authenticate("TEST@TEST.COM", "pass123")
        assert success is True


# ═════════════════════════════════════════════════════════════
# TESTS : Préférences utilisateur
# ═════════════════════════════════════════════════════════════

class TestUserPreferences:

    def test_update_language(self, temp_db):
        """Changer la langue."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.update_user_preferences(user_id, langue="en")
        user = temp_db.get_user(user_id)
        assert user["langue"] == "en"

    def test_update_theme(self, temp_db):
        """Changer le thème."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.update_user_preferences(user_id, theme="dark")
        user = temp_db.get_user(user_id)
        assert user["theme"] == "dark"

    def test_update_both(self, temp_db):
        """Changer langue + thème."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.update_user_preferences(user_id, langue="en", theme="dark")
        user = temp_db.get_user(user_id)
        assert user["langue"] == "en"
        assert user["theme"] == "dark"

    def test_update_user_profile_and_password(self, temp_db):
        """Mettre à jour les informations et le mot de passe."""
        _, user_id = temp_db.create_user(
            "A", "B", "a@test.com", "0600000000", "Ancienne adresse", "pass123"
        )

        success, message = temp_db.update_user_profile(
            user_id, "Nouveau nom", "Nouveau prénom", "new@test.com",
            "0611111111", "Nouvelle adresse", password="newpass123",
        )

        assert success is True
        assert "mis à jour" in message
        user = temp_db.get_user(user_id)
        assert user["nom"] == "Nouveau nom"
        assert user["email"] == "new@test.com"
        assert temp_db.authenticate("new@test.com", "newpass123")[0] is True
        assert temp_db.authenticate("a@test.com", "pass123")[0] is False


# ═════════════════════════════════════════════════════════════
# TESTS : Rôles et administration
# ═════════════════════════════════════════════════════════════

class TestUserRoles:

    def test_default_role_is_analyst(self, temp_db):
        """Rôle par défaut = analyst."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        user = temp_db.get_user(user_id)
        assert user["role"] == "analyst"

    def test_create_admin(self, temp_db):
        """Créer un admin."""
        _, user_id = temp_db.create_user(
            "A", "B", "admin@test.com", "", "", "pass123", role="admin"
        )
        user = temp_db.get_user(user_id)
        assert user["role"] == "admin"

    def test_update_role(self, temp_db):
        """Changer le rôle."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.update_user_role(user_id, "admin")
        user = temp_db.get_user(user_id)
        assert user["role"] == "admin"

    def test_toggle_active(self, temp_db):
        """Désactiver un utilisateur."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.toggle_user_active(user_id)
        user = temp_db.get_user(user_id)
        assert user["actif"] is False

        # Vérifier que l'auth échoue
        success, msg = temp_db.authenticate("a@test.com", "pass123")
        assert success is False
        assert "désactivé" in msg.lower()

    def test_get_all_users(self, temp_db):
        """Lister tous les utilisateurs."""
        temp_db.create_user("A", "1", "a@test.com", "", "", "pass123")
        temp_db.create_user("B", "2", "b@test.com", "", "", "pass123")
        temp_db.create_user("C", "3", "c@test.com", "", "", "pass123")
        users = temp_db.get_all_users()
        assert len(users) == 3

    def test_delete_user(self, temp_db):
        """Supprimer un utilisateur."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.delete_user(user_id)
        assert temp_db.get_user(user_id) is None

    def test_save_and_get_batch_import(self, temp_db):
        """Conserver et retrouver les résultats d'un import CSV."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        results = [{
            "montant": 100,
            "type_transaction": "Paiement",
            "score": 0.8,
            "decision": "FRAUDE",
            "niveau_risque": "Élevé",
        }]

        import_id = temp_db.save_batch_import(user_id, "transactions.csv", results)
        imports = temp_db.get_batch_imports(user_id)

        assert import_id > 0
        assert imports[0]["filename"] == "transactions.csv"
        assert imports[0]["results"] == results


# ═════════════════════════════════════════════════════════════
# TESTS : Alertes
# ═════════════════════════════════════════════════════════════

class TestAlerts:

    def test_create_alert(self, temp_db):
        """Créer une alerte."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        alert_id = temp_db.create_alert(
            user_id=user_id,
            transaction_data={"montant": 50000, "type": "Virement"},
            score=0.95,
            decision="FRAUDE",
            niveau_risque="Très élevé"
        )
        assert alert_id is not None
        assert alert_id > 0

    def test_get_alerts(self, temp_db):
        """Récupérer les alertes."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.create_alert(user_id, {"montant": 1000}, 0.9, "FRAUDE")
        temp_db.create_alert(user_id, {"montant": 2000}, 0.85, "FRAUDE")

        alerts = temp_db.get_alerts(user_id)
        assert len(alerts) == 2
        assert alerts[0]["score"] == 0.9 or alerts[0]["score"] == 0.85
        assert alerts[0]["transaction_data"]["montant"] in [1000, 2000]

    def test_count_unread_alerts(self, temp_db):
        """Compter les alertes non lues."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.create_alert(user_id, {}, 0.9, "FRAUDE")
        temp_db.create_alert(user_id, {}, 0.85, "FRAUDE")
        assert temp_db.count_unread_alerts(user_id) == 2

    def test_mark_alert_read(self, temp_db):
        """Marquer une alerte comme lue."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        alert_id = temp_db.create_alert(user_id, {}, 0.9, "FRAUDE")
        temp_db.mark_alert_read(alert_id)
        assert temp_db.count_unread_alerts(user_id) == 0

    def test_mark_all_alerts_read(self, temp_db):
        """Marquer toutes les alertes comme lues."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.create_alert(user_id, {}, 0.9, "FRAUDE")
        temp_db.create_alert(user_id, {}, 0.85, "FRAUDE")
        temp_db.mark_all_alerts_read(user_id)
        assert temp_db.count_unread_alerts(user_id) == 0

    def test_delete_alert(self, temp_db):
        """Supprimer une alerte."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        alert_id = temp_db.create_alert(user_id, {}, 0.9, "FRAUDE")
        temp_db.delete_alert(alert_id)
        assert len(temp_db.get_alerts(user_id)) == 0

    def test_alerts_isolated_per_user(self, temp_db):
        """Les alertes d'un user ne sont pas visibles par un autre."""
        _, uid1 = temp_db.create_user("A", "1", "a@test.com", "", "", "pass123")
        _, uid2 = temp_db.create_user("B", "2", "b@test.com", "", "", "pass123")

        temp_db.create_alert(uid1, {}, 0.9, "FRAUDE")
        temp_db.create_alert(uid2, {}, 0.85, "FRAUDE")
        temp_db.create_alert(uid2, {}, 0.80, "FRAUDE")

        assert len(temp_db.get_alerts(uid1)) == 1
        assert len(temp_db.get_alerts(uid2)) == 2


# ═════════════════════════════════════════════════════════════
# TESTS : Audit logs
# ═════════════════════════════════════════════════════════════

class TestAuditLogs:

    def test_log_action(self, temp_db):
        """Enregistrer une action."""
        _, user_id = temp_db.create_user("A", "B", "a@test.com", "", "", "pass123")
        temp_db.log_action(user_id, "login", "User logged in")
        logs = temp_db.get_audit_logs(user_id)
        assert len(logs) == 1
        assert logs[0]["action"] == "login"

    def test_get_all_logs(self, temp_db):
        """Récupérer tous les logs."""
        _, uid1 = temp_db.create_user("A", "1", "a@test.com", "", "", "pass123")
        _, uid2 = temp_db.create_user("B", "2", "b@test.com", "", "", "pass123")
        temp_db.log_action(uid1, "login")
        temp_db.log_action(uid2, "signup")
        temp_db.log_action(uid1, "predict")
        logs = temp_db.get_audit_logs()
        assert len(logs) == 3


# ═════════════════════════════════════════════════════════════
# TESTS : Statistiques
# ═════════════════════════════════════════════════════════════

class TestStats:

    def test_get_stats(self, temp_db):
        """Récupérer les statistiques."""
        _, uid1 = temp_db.create_user("A", "1", "a@test.com", "", "", "pass123")
        _, uid2 = temp_db.create_user("B", "2", "b@test.com", "", "", "pass123")

        temp_db.create_alert(uid1, {}, 0.9, "FRAUDE")
        temp_db.create_alert(uid2, {}, 0.85, "FRAUDE")
        temp_db.create_alert(uid2, {}, 0.1, "NORMAL")
        temp_db.mark_alert_read(1)

        stats = temp_db.get_stats()
        assert stats["n_users"] == 2
        assert stats["n_alerts"] == 3
        assert stats["n_unread"] == 2
        assert stats["n_frauds"] == 2

    def test_stats_empty_db(self, temp_db):
        """Stats sur base vide."""
        stats = temp_db.get_stats()
        assert stats["n_users"] == 0
        assert stats["n_alerts"] == 0
        assert stats["n_unread"] == 0
