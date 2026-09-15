"""
Gestion de session simplifiée via dcc.Store.
"""


def is_logged_in(session_data):
    """Vérifie si l'utilisateur est connecté."""
    return bool(session_data and session_data.get("user_id"))


def get_user_from_session(session_data):
    """Extrait le user du session store."""
    if not is_logged_in(session_data):
        return None
    return {
        "id": session_data["user_id"],
        "nom": session_data.get("nom", ""),
        "prenom": session_data.get("prenom", ""),
        "email": session_data.get("email", ""),
    }
