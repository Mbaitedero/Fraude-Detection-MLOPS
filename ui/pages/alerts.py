"""Centre des alertes de fraude de l'utilisateur connecté."""

from datetime import datetime

import dash
from dash import Input, Output, State, html

from ui.auth import database
from ui.components.sidebar import wrap_with_sidebar


def layout(session):
    alerts = database.get_alerts(session.get("user_id"), limit=100)
    return wrap_with_sidebar(
        session,
        "alerts",
        [
            html.Div([
                html.Div([
                    html.H3("Alertes de fraude", className="card-title"),
                    html.P(
                        "Consultez les transactions signalées par votre scoring.",
                        className="card-subtitle",
                    ),
                ], className="alerts-heading"),
                html.Button(
                    "Tout marquer comme lu",
                    id="mark-all-alerts-btn",
                    n_clicks=0,
                    className="btn-secondary",
                ),
            ], className="alerts-toolbar"),
            html.Div(id="alerts-list", children=_render_alerts(alerts)),
        ],
        title="Alertes",
        subtitle="Suivi des transactions à risque",
    )


def _render_alerts(alerts):
    if not alerts:
        return html.Div("Aucune alerte de fraude pour le moment.", className="alert-info")

    cards = []
    for alert in alerts:
        data = alert["transaction_data"] or {}
        cards.append(html.Div([
            html.Div([
                html.Div("Fraude détectée", className="alert-card-title"),
                html.Span(
                    "Lue" if alert["lu"] else "Non lue",
                    className=f"user-badge {'user-status-active' if alert['lu'] else 'alert-unread-badge'}",
                ),
            ], className="alert-card-header"),
            html.Div([
                _detail("Montant", f"{data.get('montant', '-')} MAD"),
                _detail("Score", f"{alert['score']:.2%}"),
                _detail("Risque", alert["niveau_risque"]),
                _detail("Date", _format_date(alert["created_at"])),
            ], className="alert-card-details"),
            html.Div([
                html.Span(f"{alert['decision']} · {data.get('type_transaction', '-')}", className="alert-decision"),
                html.Button(
                    "Marquer comme lue" if not alert["lu"] else "Déjà lue",
                    id={"type": "mark-alert-btn", "index": alert["id"]},
                    n_clicks=0,
                    disabled=alert["lu"],
                    className="btn-secondary btn-alert-action",
                ),
                html.Button(
                    "Supprimer",
                    id={"type": "delete-alert-btn", "index": alert["id"]},
                    n_clicks=0,
                    className="btn-danger btn-alert-action",
                ),
            ], className="alert-card-actions"),
        ], className=f"fraud-alert-card {'alert-card-unread' if not alert['lu'] else ''}"))
    return cards


def _detail(label, value):
    return html.Div([
        html.Div(label, className="alert-detail-label"),
        html.Div(value, className="alert-detail-value"),
    ], className="alert-detail-item")


def _format_date(value):
    try:
        date = datetime.fromisoformat(str(value))
        return f"{date:%d/%m/%Y %H:%M}"
    except (TypeError, ValueError):
        return str(value or "-")


@dash.callback(
    Output("alerts-list", "children"),
    Input("mark-all-alerts-btn", "n_clicks"),
    Input({"type": "mark-alert-btn", "index": dash.ALL}, "n_clicks"),
    Input({"type": "delete-alert-btn", "index": dash.ALL}, "n_clicks"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def update_alerts(_, __, ___, session):
    if not session or not session.get("user_id"):
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if triggered == "mark-all-alerts-btn":
        database.mark_all_alerts_read(session["user_id"])
    elif isinstance(triggered, dict):
        alert_id = triggered["index"]
        if triggered["type"] == "mark-alert-btn":
            database.mark_alert_read(alert_id)
        elif triggered["type"] == "delete-alert-btn":
            database.delete_alert(alert_id)
    return _render_alerts(database.get_alerts(session["user_id"], limit=100))
