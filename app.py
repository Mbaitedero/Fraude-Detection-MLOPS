"""
Point d'entrée racine — expose l'app Dash pour gunicorn/Render.
"""

from ui.app import app, server  # noqa: F401

if __name__ == "__main__":
    app.run(debug=True, port=8050, host="0.0.0.0")