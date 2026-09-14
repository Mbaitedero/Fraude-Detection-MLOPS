"""Gestion des messages de contact réservée à l'administration."""

from datetime import datetime

import dash
from dash import Input, Output, State, html

from ui.auth import database
from ui.components.sidebar import wrap_with_sidebar


def layout(session):
    if session.get("role") != "admin":
        return wrap_with_sidebar(
            session, "contact_messages", [html.Div([
                html.H3("Accès refusé", className="card-title"),
                html.P("Cette page est réservée à l'administrateur.", className="card-subtitle"),
            ], className="content-card")],
            title="Messages de contact",
            subtitle="Droits administrateur requis",
        )

    return wrap_with_sidebar(
        session,
        "contact_messages",
        [
            html.Div([
                html.H3("Messages de contact", className="card-title"),
                html.P("Demandes reçues depuis le formulaire public.", className="card-subtitle"),
                html.Div(id="contact-messages-table", children=_render_messages()),
            ], className="content-card"),
        ],
        title="Messages de contact",
        subtitle="Suivi des demandes de démonstration",
    )


def _render_messages():
    messages = database.get_contact_messages()
    if not messages:
        return html.Div("Aucun message reçu.", className="alert-info")

    rows = []
    for message in messages:
        rows.append(html.Tr([
            html.Td(message["id"]),
            html.Td(f"{message['prenom']} {message['nom']}"),
            html.Td(message["email"]),
            html.Td(message["telephone"] or "-"),
            html.Td(message["message"], className="contact-message-cell"),
            html.Td(html.Span(
                _status_label(message["statut"]),
                className=f"user-badge contact-status-{message['statut']}",
            )),
            html.Td(_format_date(message["created_at"])),
            html.Td(_status_actions(message["id"], message["statut"])),
        ]))

    headers = ["ID", "Contact", "Email", "Téléphone", "Message", "Statut", "Date", "Action"]
    return html.Div([
        html.Table([
            html.Thead(html.Tr([html.Th(header) for header in headers])),
            html.Tbody(rows),
        ], className="user-table contact-messages-table"),
    ], className="user-table-wrapper")


def _status_actions(message_id, status):
    actions = []
    if status == "nouveau":
        actions.append(html.Button(
            "Marquer lu", id={"type": "contact-read-btn", "index": message_id},
            n_clicks=0, className="btn-secondary btn-alert-action",
        ))
    if status != "traite":
        actions.append(html.Button(
            "Traité", id={"type": "contact-done-btn", "index": message_id},
            n_clicks=0, className="btn-primary btn-alert-action",
        ))
    return html.Div(actions, className="contact-actions")


def _status_label(status):
    return {"nouveau": "Nouveau", "lu": "Lu", "traite": "Traité"}.get(status, status)


def _format_date(value):
    try:
        date = datetime.fromisoformat(str(value))
        return f"{date:%d/%m/%Y %H:%M}"
    except (TypeError, ValueError):
        return str(value or "-")


@dash.callback(
    Output("contact-messages-table", "children"),
    Input({"type": "contact-read-btn", "index": dash.ALL}, "n_clicks"),
    Input({"type": "contact-done-btn", "index": dash.ALL}, "n_clicks"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def update_contact_messages(_, __, session):
    if not session or session.get("role") != "admin":
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if isinstance(triggered, dict):
        status = "lu" if triggered["type"] == "contact-read-btn" else "traite"
        database.update_contact_message_status(triggered["index"], status)
    return _render_messages()
