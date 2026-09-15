"""
Composant d'alerte (toast) quand une fraude est détectée.
"""

from dash import html


def render_alert_banner(n_alerts):
    """Affiche une bannière si des alertes non lues existent."""
    if n_alerts == 0:
        return html.Div()

    return html.Div([
        html.Div([
            html.Strong(f"{n_alerts} alerte{'s' if n_alerts > 1 else ''} de fraude non lue{'s' if n_alerts > 1 else ''}"),
            html.Div("Cliquez pour voir les détails", className="alert-detail"),
        ]),
    ], className="alert-banner", id="fraud-alert-banner")


def render_toast(message, type="success"):
    """Toast temporaire."""
    return html.Div([
        html.Span(message, className="toast-message"),
    ], className=f"toast toast-{type}")
