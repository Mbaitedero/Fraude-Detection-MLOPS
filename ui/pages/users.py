"""Page de gestion des utilisateurs (admin seulement)."""

from datetime import datetime

import dash
from dash import Input, Output, State, dcc, html

from ui.auth import database
from ui.components.sidebar import wrap_with_sidebar


def layout(session):
    if session.get("role") != "admin":
        content = [
            html.Div([
                html.H3("Accès refusé", className="card-title"),
                html.P("Cette page est réservée aux administrateurs.",
                       className="card-subtitle"),
            ], className="content-card"),
        ]
        return wrap_with_sidebar(
            session, "users", content,
            title="Gestion des utilisateurs",
            subtitle="Accès restreint",
        )

    users = database.get_all_users()

    content = [
        html.Div(id="users-kpis", children=_render_kpis(users), className="kpi-grid"),

        html.Div([
            html.H3("Actions administrateur", className="card-title"),
            html.Div([
                dcc.Dropdown(
                    id="users-selected-id",
                    options=[
                        {
                            "label": f"{user['prenom']} {user['nom']} - {user['email']}",
                            "value": user["id"],
                        }
                        for user in users
                    ],
                    placeholder="Sélectionner un utilisateur",
                    clearable=True,
                    className="form-dropdown",
                ),
                dcc.Dropdown(
                    id="users-role",
                    options=[
                        {"label": "Analyste", "value": "analyst"},
                        {"label": "Administrateur", "value": "admin"},
                    ],
                    value="analyst",
                    clearable=False,
                    className="form-dropdown",
                ),
            ], className="form-grid"),
            html.Div([
                html.Button("Enregistrer le rôle", id="users-role-btn", n_clicks=0,
                            className="btn-primary"),
                html.Button("Activer / désactiver", id="users-toggle-btn", n_clicks=0,
                            className="btn-secondary"),
                html.Button("Supprimer", id="users-delete-btn", n_clicks=0,
                            className="btn-danger"),
            ], className="form-actions"),
            html.Div(id="users-action-message", className="auth-message"),
        ], className="content-card"),

        html.Div([
            html.H3("Liste des utilisateurs", className="card-title"),
            html.Div(id="users-table", children=_render_table(users)),
        ], className="content-card"),
    ]

    return wrap_with_sidebar(
        session, "users", content,
        title="Gestion des utilisateurs",
        subtitle=f"{len(users)} utilisateurs au total",
    )


def _kpi(label, value, icon):
    return html.Div([
        html.Div(icon, className="kpi-icon"),
        html.Div([
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value"),
        ]),
    ], className="kpi-card")


def _render_kpis(users):
    return [
        _kpi("Utilisateurs", str(len(users)), ""),
        _kpi("Admins", str(sum(1 for user in users if user["role"] == "admin")), ""),
        _kpi("Actifs", str(sum(1 for user in users if user["actif"])), ""),
        _kpi("Inactifs", str(sum(1 for user in users if not user["actif"])), ""),
    ]


def _render_table(users):
    columns = [
        "ID", "Nom", "Prénom", "Email", "Téléphone", "Fonction",
        "Rôle", "Langue", "Thème", "Statut", "Créé le",
    ]
    rows = []
    for user in users:
        rows.append(html.Tr([
            html.Td(user.get("id", "-")),
            html.Td(_display(user.get("nom"))),
            html.Td(_display(user.get("prenom"))),
            html.Td(_display(user.get("email"))),
            html.Td(_display(user.get("telephone"))),
            html.Td(_display(user.get("fonction"))),
            html.Td(html.Span(
                "Administrateur" if user.get("role") == "admin" else "Analyste",
                className=f"user-badge user-role-{user.get('role', 'analyst')}",
            )),
            html.Td(_display(user.get("langue"))),
            html.Td(_display(user.get("theme"))),
            html.Td(html.Span(
                "Actif" if user.get("actif") else "Inactif",
                className=f"user-badge {'user-status-active' if user.get('actif') else 'user-status-inactive'}",
            )),
            html.Td(_format_date(user.get("created_at"))),
        ]))

    return html.Div([
        html.Table([
            html.Thead(html.Tr([html.Th(column) for column in columns])),
            html.Tbody(rows),
        ], className="user-table"),
    ], className="user-table-wrapper")


def _display(value):
    return value if value not in (None, "", "nan") else "-"


def _format_date(value):
    if not value:
        return "-"
    try:
        date = datetime.fromisoformat(str(value))
        months = [
            "Jan.", "Fév.", "Mars", "Avr.", "Mai", "Juin",
            "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc.",
        ]
        return f"{date.day} {months[date.month - 1]} {date.year}, {date:%H:%M}"
    except (TypeError, ValueError):
        return _display(value)


@dash.callback(
    Output("users-kpis", "children"),
    Output("users-table", "children"),
    Output("users-action-message", "children"),
    Input("users-role-btn", "n_clicks"),
    Input("users-toggle-btn", "n_clicks"),
    Input("users-delete-btn", "n_clicks"),
    State("users-selected-id", "value"),
    State("users-role", "value"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def manage_user(role_clicks, toggle_clicks, delete_clicks, selected_id,
                selected_role, session):
    if not selected_id or not session or session.get("role") != "admin":
        raise dash.exceptions.PreventUpdate

    trigger = dash.callback_context.triggered_id
    if trigger == "users-role-btn":
        success, message = _update_role(selected_id, selected_role)
    elif trigger == "users-toggle-btn":
        database.toggle_user_active(selected_id)
        success, message = True, "Statut du compte mis à jour."
    elif trigger == "users-delete-btn":
        if selected_id == session.get("user_id"):
            success, message = False, "Vous ne pouvez pas supprimer votre propre compte."
        else:
            database.delete_user(selected_id)
            success, message = True, "Utilisateur supprimé."
    else:
        raise dash.exceptions.PreventUpdate

    users = database.get_all_users()
    return (
        _render_kpis(users),
        _render_table(users),
        html.Div(message, className="auth-success" if success else "auth-error"),
    )


def _update_role(user_id, role):
    if role not in {"admin", "analyst"}:
        return False, "Rôle invalide."
    database.update_user_role(user_id, role)
    return True, "Rôle mis à jour."