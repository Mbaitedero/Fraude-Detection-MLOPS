"""Page Admin MLOps — avec sidebar."""

import os

import dash
import requests
from dash import Input, Output, html

from ui.components.sidebar import wrap_with_sidebar


def layout(session):
    if session.get("role") != "admin":
        return wrap_with_sidebar(
            session,
            "home",
            [html.Div([
                html.H3("Accès refusé", className="card-title"),
                html.P(
                    "Cette page est réservée à l'administrateur de l'application.",
                    className="card-subtitle",
                ),
            ], className="content-card")],
            title="Accès restreint",
            subtitle="Droits administrateur requis",
        )

    content = [
        html.Div(id="champion-info", className="content-card"),
        html.Div([
            html.H3("Toutes les versions enregistrées", className="card-title"),
            html.Div(id="versions-table"),
        ], className="content-card"),
        html.Div(id="promote-feedback"),
    ]

    return wrap_with_sidebar(
        session, "admin", content,
        title="Administration MLOps",
        subtitle="Cycle de vie du modèle — tracking, registre, promotion, rollback"
    )


@dash.callback(
    Output("champion-info", "children"),
    Output("versions-table", "children"),
    Input("champion-info", "id"),
    prevent_initial_call=False,
)
def load_admin(_):
    api_url = os.environ.get("API_URL", "http://api:8000")
    try:
        r_info = requests.get(f"{api_url}/model/info", timeout=10)
        r_versions = requests.get(f"{api_url}/versions", timeout=15)

        champion = r_info.json() if r_info.status_code == 200 else None
        versions = r_versions.json() if r_versions.status_code == 200 else []

        # ─── Champion ───
        if champion:
            champion_div = html.Div([
                html.H3("Modèle actuellement en production", className="card-title"),
                html.Div([
                    _kpi("Version", f"v{champion['version']}", "primary"),
                    _kpi("PR-AUC", f"{champion['pr_auc']:.4f}" if champion.get('pr_auc') else "—", "success"),
                    _kpi("ROC-AUC", f"{champion['roc_auc']:.4f}" if champion.get('roc_auc') else "—", "info"),
                    _kpi("Lift", f"{champion['lift']:.2f}×" if champion.get('lift') else "—", "warning"),
                ], className="kpi-grid"),
                html.P(f"Run ID : {champion.get('run_id', '')[:16]}...",
                       className="champion-meta"),
            ])
        else:
            champion_div = html.Div("Aucun champion disponible.",
                                    className="alert-warning")

        # ─── Versions ───
        if versions:
            rows = []
            for v in versions:
                is_champion = "champion" in (v.get("alias") or "")
                rows.append(html.Tr([
                    html.Td(f"v{v['version']}", className="td-bold"),
                    html.Td(
                        html.Span(v.get("alias", "—"),
                                  className=f"badge {'badge-champion' if is_champion else 'badge-default'}")
                    ),
                    html.Td(v.get("run_name", "—")),
                    html.Td(f"{v.get('pr_auc', 0):.4f}" if v.get('pr_auc') else "—"),
                    html.Td(f"{v.get('roc_auc', 0):.4f}" if v.get('roc_auc') else "—"),
                    html.Td(f"{v.get('lift', 0):.2f}×" if v.get('lift') else "—"),
                    html.Td(v.get("date", "—")[:19]),
                    html.Td(
                        html.Button("Promouvoir",
                            id={"type": "promote-btn", "index": v["version"]},
                            n_clicks=0, className="btn-sm",
                            disabled=is_champion)
                    ),
                ]))

            versions_div = html.Table([
                html.Thead(html.Tr([
                    html.Th("Version"), html.Th("Alias"), html.Th("Run"),
                    html.Th("PR-AUC"), html.Th("ROC-AUC"), html.Th("Lift"),
                    html.Th("Date"), html.Th("Action"),
                ])),
                html.Tbody(rows),
            ], className="versions-table")
        else:
            versions_div = html.Div("Aucune version enregistrée.",
                                    className="alert-info")

        return champion_div, versions_div
    except Exception as e:
        return html.Div(f"Erreur : {e}", className="alert-error"), html.Div()


def _kpi(label, value, color):
    return html.Div([
        html.Div(label, className="kpi-label"),
        html.Div(value, className="kpi-value"),
    ], className=f"kpi-card kpi-mini kpi-{color}")


@dash.callback(
    Output("promote-feedback", "children"),
    Input({"type": "promote-btn", "index": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_promote(n_clicks_list):
    if not any(n_clicks_list):
        raise dash.exceptions.PreventUpdate

    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    import json
    version = json.loads(button_id)["index"]

    api_url = os.environ.get("API_URL", "http://api:8000")
    try:
        r = requests.post(f"{api_url}/promote/{version}", timeout=15)
        if r.status_code == 200:
            return html.Div(f"Version {version} promue en champion ! Rechargez pour voir.",
                            className="alert-success")
        return html.Div(f"Erreur : {r.text[:200]}", className="alert-error")
    except Exception as e:
        return html.Div(f"Erreur : {e}", className="alert-error")
