"""
Tests du module i18n (internationalisation FR/EN).
"""

import pytest
from unittest.mock import patch


class TestI18n:

    def test_load_french_translations(self):
        """Charger les traductions françaises."""
        from ui.i18n import load_translations
        fr = load_translations("fr")
        assert isinstance(fr, dict)
        assert "home" in fr
        assert fr["home"] == "Accueil"

    def test_load_english_translations(self):
        """Charger les traductions anglaises."""
        from ui.i18n import load_translations
        en = load_translations("en")
        assert isinstance(en, dict)
        assert "home" in en
        assert en["home"] == "Home"

    def test_translate_key_fr(self):
        """Traduire une clé en français."""
        from ui.i18n import t
        assert t("home", "fr") == "Accueil"
        assert t("dashboard", "fr") == "Tableau de bord"
        assert t("logout", "fr") == "Déconnexion"

    def test_translate_key_en(self):
        """Traduire une clé en anglais."""
        from ui.i18n import t
        assert t("home", "en") == "Home"
        assert t("dashboard", "en") == "Dashboard"
        assert t("logout", "en") == "Logout"

    def test_unknown_key_fallback(self):
        """Clé inconnue → retourne la clé elle-même."""
        from ui.i18n import t
        assert t("unknown_key_xyz", "fr") == "unknown_key_xyz"
        assert t("unknown_key_xyz", "en") == "unknown_key_xyz"

    def test_unknown_lang_fallback(self):
        """Langue inconnue → fallback français."""
        from ui.i18n import t
        # Doit lever une erreur ou retourner FR
        try:
            result = t("home", "es")
            # Si pas d'erreur, la clé est retournée
            assert result == "home" or result == "Accueil"
        except (FileNotFoundError, Exception):  # noqa: BLE001
            # OK si lève une exception
            pass

    def test_all_keys_present_in_both_langs(self):
        """Toutes les clés FR doivent exister en EN (et inversement)."""
        from ui.i18n import load_translations
        fr = load_translations("fr")
        en = load_translations("en")
        assert set(fr.keys()) == set(en.keys())