"""Page Scoring manuel — avec sidebar."""

import os

import dash
import requests
from dash import Input, Output, State, dcc, html

from ui.auth import database
from ui.components.sidebar import wrap_with_sidebar
from ui.i18n import t


def layout(session):
    lang = session.get("langue") or session.get("lang", "fr")
    os.environ.get("API_URL", "http://api:8000")
    
    content = [
        html.Div([
            html.H3(t("transaction_form", lang), className="card-title"),
            html.P(t("transaction_prompt", lang),
                   className="card-subtitle"),
            
            html.Div([
                # Colonne 1
                html.Div([
                    html.Div([
                        html.Label(t("amount", lang), className="form-label"),
                        dcc.Input(id="montant", type="number", value=500, min=0,
                                  className="form-input"),
                    ], className="form-group"),
                    
                    html.Div([
                        html.Label(t("transaction_type", lang), className="form-label"),
                        dcc.Dropdown(id="type_transaction",
                            options=[{"label": t, "value": t} for t in
                                ["Paiement", "Virement", "Retrait", "Dépôt", "Prélèvement"]],
                            value="Paiement", className="form-dropdown", clearable=False),
                    ], className="form-group"),
                    
                    html.Div([
                        html.Label(t("payment_method", lang), className="form-label"),
                        dcc.Dropdown(id="mode_paiement",
                            options=[{"label": m, "value": m} for m in
                                ["Carte", "Espèces", "Chèque", "Virement", "Non_applicable"]],
                            value="Carte", className="form-dropdown", clearable=False),
                    ], className="form-group"),
                ], className="form-column"),
                
                # Colonne 2
                html.Div([
                    html.Div([
                        html.Label(["Heure : ", html.Span(id="heure_val",
                            children="14", className="heure-badge"), "h"],
                            className="form-label"),
                        dcc.Slider(id="heure", min=0, max=23, value=14,
                            marks={i: str(i) for i in range(0, 24, 6)},
                            className="form-slider"),
                    ], className="form-group"),
                    
                    html.Div([
                        dcc.Checklist(id="is_weekend",
                            options=[{"label": f" {t('weekend', lang)}", "value": 1}], value=[],
                            className="form-check"),
                        dcc.Checklist(id="est_international",
                            options=[{"label": f" {t('international_transaction', lang)}", "value": 1}],
                            value=[], className="form-check"),
                    ], className="form-group"),
                ], className="form-column"),
            ], className="form-grid"),
            
            html.Button(t("score_transaction", lang), id="btn_score", n_clicks=0,
                        className="btn-primary-lg"),
        ], className="content-card"),
        
        html.Div(id="resultat", className="resultat-container"),
    ]
    
    return wrap_with_sidebar(
        session, "scoring", content,
        title=t("scoring", lang),
        subtitle=t("production_model", lang)
    )


@dash.callback(
    Output("heure_val", "children"),
    Input("heure", "value"),
    prevent_initial_call=True,
)
def update_heure(h):
    return str(h)


@dash.callback(
    Output("resultat", "children"),
    Input("btn_score", "n_clicks"),
    State("montant", "value"),
    State("type_transaction", "value"),
    State("mode_paiement", "value"),
    State("heure", "value"),
    State("is_weekend", "value"),
    State("est_international", "value"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def score(n_clicks, montant, type_transaction, mode_paiement, heure,
          is_weekend, est_international, session):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    api_url = os.environ.get("API_URL", "http://api:8000")
    
    payload = {
        "montant": montant,
        "type_transaction": type_transaction,
        "mode_paiement": mode_paiement,
        "heure": heure,
        "is_weekend": 1 if is_weekend else 0,
        "est_international": 1 if est_international else 0,
    }
    
    try:
        r = requests.post(f"{api_url}/predict", json=payload, timeout=15)
        if r.status_code != 200:
            return html.Div(f"Erreur API : {r.status_code} — {r.text[:200]}",
                            className="alert-error")
        
        result = r.json()
        is_fraude = result["est_fraude"]
        pct = result["pourcentage"]

        if session and session.get("user_id"):
            if is_fraude:
                database.create_alert(
                    session["user_id"], payload, result["score"],
                    result["decision"], result["niveau_risque"],
                )
            database.save_batch_import(
                session["user_id"],
                "Scoring manuel",
                [{
                    "montant": montant,
                    "type_transaction": type_transaction,
                    "mode_paiement": mode_paiement,
                    "heure": heure,
                    "is_weekend": 1 if is_weekend else 0,
                    "est_international": 1 if est_international else 0,
                    "score": round(result["score"], 4),
                    "decision": result["decision"],
                    "niveau_risque": result["niveau_risque"],
                }],
            )
        
        return html.Div([
            html.Div([
                html.Div("", className="result-icon"),
                html.Div([
                    html.H2("FRAUDE PROBABLE" if is_fraude else "Transaction normale",
                            className=f"result-title {'result-fraude' if is_fraude else 'result-normal'}"),
                    html.P(f"Score de risque : {pct}%", className="result-score"),
                    html.P(f"Niveau : {result['niveau_risque']}", className="result-level"),
                ]),
            ], className="result-header"),
            
            html.Div([
                html.Div(
                    style={"width": f"{pct}%"},
                    className=f"result-bar {'bar-fraude' if is_fraude else 'bar-normal'}",
                ),
            ], className="result-progress"),
            
            html.P(f"Décision : {result['decision']} — seuil champion 0.5",
                   className="result-detail"),
        ], className="result-card")
    except Exception as e: # noqa: BLE001
        return html.Div(f"Erreur : {e}", className="alert-error")