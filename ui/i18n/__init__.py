import json
import os


def load_translations(lang="fr"):
    """Charge les traductions pour la langue donnée."""
    path = os.path.join(os.path.dirname(__file__), f"{lang}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def t(key, lang="fr"):
    """Traduit une clé."""
    translations = load_translations(lang)
    return translations.get(key, key)