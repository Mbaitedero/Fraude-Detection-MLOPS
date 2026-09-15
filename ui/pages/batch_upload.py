"""
Page d'upload CSV et prédiction batch.
"""

import base64
import io
import os

import dash
import pandas as pd
import requests
from dash import Input, Output, State, dash_table, dcc, html

from ui.auth import database
from ui.components.sidebar import wrap_with_sidebar


def _parse_hour(value):
    """Convertit une heure CSV (14 ou 14:32) en heure entière 0-23."""
    if pd.isna(value) or str(value).strip() == "":
        return 14

    text = str(value).strip()
    if ":" in text:
        parts = text.split(":")
        if len(parts) < 2:
            raise ValueError(f"Heure invalide : {value}")
        hour = int(parts[0])
        minute = int(parts[1])
        if not 0 <= minute <= 59:
            raise ValueError(f"Minutes invalides : {value}")
    else:
        hour = int(float(text))

    if not 0 <= hour <= 23:
        raise ValueError(f"Heure hors limites (0-23) : {value}")
    return hour


def _upload_content(filename=None):
    """Construit le contenu de la zone d'import selon le fichier sélectionné."""
    if filename:
        return html.Div([
            html.Div("Fichier sélectionné", className="upload-selected-label"),
            html.Div(filename, className="upload-selected-name"),
            html.Div("Cliquez ici pour remplacer le fichier", className="upload-hint"),
        ])

    return html.Div([
        html.Div([
            "Glissez-déposez ou ",
            html.A("parcourez vos fichiers", className="upload-link"),
        ]),
        html.Div("Format supporté : CSV (max 10 MB)", className="upload-hint"),
    ])


def layout(session):
    content = [
        html.Div([
            html.H3("Importer un fichier CSV", className="card-title"),
            html.P(
                "Déposez un fichier CSV contenant des transactions à scorer. "
                "Le fichier doit contenir les colonnes : montant, type_transaction, "
                "mode_paiement, heure, is_weekend, est_international.",
                className="card-subtitle",
            ),
            
            dcc.Upload(
                id="upload-csv",
                children=_upload_content(),
                className="upload-zone",
                multiple=False,
            ),

            html.Button(
                "Lancer la prédiction",
                id="launch-batch-prediction",
                n_clicks=0,
                className="btn-primary-lg",
                style={"marginTop": "16px"},
            ),
            
            dcc.Loading(
                html.Div(id="upload-status"),
                type="circle",
                color="#2563eb",
                fullscreen=False,
            ),
        ], className="content-card"),
        
        dcc.Loading(
            html.Div(id="batch-results-container"),
            type="circle",
            color="#2563eb",
            fullscreen=False,
        ),
    ]
    
    return wrap_with_sidebar(
        session, "batch_upload", content,
        title="Prédiction batch (CSV)",
        subtitle="Importez un fichier CSV et obtenez les prédictions",
    )


@dash.callback(
    Output("upload-csv", "children"),
    Input("upload-csv", "filename"),
    prevent_initial_call=True,
)
def display_selected_filename(filename):
    return _upload_content(filename)


@dash.callback(
    Output("upload-status", "children"),
    Output("batch-results-container", "children"),
    Input("launch-batch-prediction", "n_clicks"),
    State("upload-csv", "contents"),
    State("upload-csv", "filename"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def handle_upload(n_clicks, contents, filename, session):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    if not contents:
        return (
            html.Div(
                "Veuillez d'abord sélectionner un fichier CSV.",
                className="alert-error",
            ),
            html.Div(),
        )
    
    # Décoder le fichier
    try:
        _content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
    except Exception as e:
        return html.Div(f"Erreur de lecture : {e}", className="alert-error"), html.Div()
    
    # Vérifier les colonnes requises
    required = ["montant", "type_transaction", "mode_paiement", "heure"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return html.Div(
            f"Colonnes manquantes : {', '.join(missing)}",
            className="alert-error",
        ), html.Div()
    
    # Appeler l'API pour chaque ligne
    api_url = os.environ.get("API_URL", "http://api:8000")
    results = []
    
    for _, row in df.iterrows():
        try:
            payload = {
                "montant": float(row.get("montant", 0)),
                "type_transaction": str(row.get("type_transaction", "Paiement")),
                "mode_paiement": str(row.get("mode_paiement", "Carte")),
                "heure": _parse_hour(row.get("heure", 14)),
                "is_weekend": int(row.get("is_weekend", 0)),
                "est_international": int(row.get("est_international", 0)),
            }
        except (TypeError, ValueError) as error:
            results.append({
                "montant": row.get("montant"),
                "type_transaction": str(row.get("type_transaction", "")),
                "score": None,
                "decision": "ERREUR",
                "niveau_risque": str(error)[:80],
            })
            continue
        
        try:
            r = requests.post(f"{api_url}/predict", json=payload, timeout=10)
            if r.status_code == 200:
                res = r.json()
                if res["est_fraude"] and session and session.get("user_id"):
                    database.create_alert(
                        session["user_id"], payload, res["score"],
                        res["decision"], res["niveau_risque"],
                    )
                results.append({
                    "montant": payload["montant"],
                    "type_transaction": payload["type_transaction"],
                    "score": round(res["score"], 4),
                    "decision": res["decision"],
                    "niveau_risque": res["niveau_risque"],
                })
            else:
                results.append({
                    "montant": payload["montant"],
                    "type_transaction": payload["type_transaction"],
                    "score": None,
                    "decision": "ERREUR",
                    "niveau_risque": f"HTTP {r.status_code}",
                })
        except Exception as e:
            results.append({
                "montant": payload["montant"],
                "type_transaction": payload["type_transaction"],
                "score": None,
                "decision": "ERREUR",
                "niveau_risque": str(e)[:50],
            })
    
    df_results = pd.DataFrame(results)
    n_fraudes = (df_results["decision"] == "FRAUDE").sum()
    n_total = len(df_results)
    
    import_id = None
    if session and session.get("user_id"):
        import_id = database.save_batch_import(session["user_id"], filename, results)
        database.log_action(
            session["user_id"], "batch_import",
            f"CSV {filename} ({n_total} transactions, import {import_id})",
        )

    # Statut
    status = html.Div([
        html.Div(className="status-icon"),
        html.Div([
            html.Strong(f"Fichier '{filename}' traité avec succès"),
            html.Div(
                f"{n_total} transactions · {n_fraudes} fraudes détectées "
                f"({n_fraudes/n_total:.1%})",
                className="status-detail",
            ),
            dcc.Link(
                "Voir cet import dans Transactions notées",
                href="/batch",
                className="btn-primary",
            ),
        ]),
    ], className="status-banner")
    
    # Résultats
    results_content = html.Div([
        html.H3("Résultats de la prédiction", className="card-title"),
        
        # KPIs
        html.Div([
            _kpi_card("Total", f"{n_total}", ""),
            _kpi_card("Fraudes", f"{n_fraudes}", ""),
            _kpi_card("Taux", f"{n_fraudes/n_total:.1%}", ""),
            _kpi_card("Normales", f"{n_total - n_fraudes}", ""),
        ], className="kpi-grid"),
        
        # Téléchargement
        html.Div([
            html.Button("Télécharger les résultats (CSV)",
                        id="btn-download-csv", className="btn-primary-lg"),
            dcc.Download(id="download-csv"),
        ], style={"marginTop": "20px"}),
        
        # Table des résultats
        html.Div([
            dash_table.DataTable(
                data=df_results.to_dict("records"),
                columns=[{"name": c, "id": c} for c in df_results.columns],
                page_size=20,
                sort_action="native",
                filter_action="native",
                style_table={"overflowX": "auto", "marginTop": "20px"},
                style_cell={"textAlign": "left", "padding": "12px", "fontFamily": "Inter, sans-serif"},
                style_header={"backgroundColor": "#f1f5f9", "fontWeight": "700"},
                style_data_conditional=[
                    {
                        "if": {"filter_query": '{decision} = "FRAUDE"'},
                        "backgroundColor": "#fee2e2",
                        "color": "#991b1b",
                    },
                ],
            ),
        ]),
        
        # Stockage des résultats pour téléchargement
        dcc.Store(id="store-results", data=df_results.to_dict("records")),
    ], className="content-card")
    
    return status, results_content


def _kpi_card(label, value, icon):
    return html.Div([
        html.Div(icon, className="kpi-icon"),
        html.Div([
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value"),
        ]),
    ], className="kpi-card")


@dash.callback(
    Output("download-csv", "data"),
    Input("btn-download-csv", "n_clicks"),
    State("store-results", "data"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, data):
    if not n_clicks or not data:
        raise dash.exceptions.PreventUpdate
    df = pd.DataFrame(data)
    return dcc.send_data_frame(df.to_csv, "predictions_fraude.csv", index=False)