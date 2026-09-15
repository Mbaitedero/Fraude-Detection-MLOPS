"""
Page Monitoring avec visuels Plotly (sans Grafana).
"""

import os

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from dash import Input, Output, dcc, html
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from ui.components.sidebar import wrap_with_sidebar


def layout(session):
    os.environ.get("API_URL", "http://api:8000")

    content = [
        # KPIs santé
        html.Div([
            html.H3("Santé du système", className="card-title"),
            html.Div(id="health-kpis", className="kpi-grid"),
        ], className="content-card"),

        # Graphiques
        html.Div([
            html.Div([
                html.H3("Distribution des scores de fraude", className="card-title"),
                dcc.Graph(id="chart-scores-distribution"),
            ], className="content-card"),

            html.Div([
                html.H3("Matrice de confusion", className="card-title"),
                dcc.Graph(id="chart-confusion"),
            ], className="content-card"),
        ], className="info-grid"),

        html.Div([
            html.Div([
                html.H3("Courbe ROC", className="card-title"),
                dcc.Graph(id="chart-roc"),
            ], className="content-card"),

            html.Div([
                html.H3("Courbe Précision-Rappel", className="card-title"),
                dcc.Graph(id="chart-pr"),
            ], className="content-card"),
        ], className="info-grid"),

        # Top features
        html.Div([
            html.H3("Importance des features", className="card-title"),
            dcc.Graph(id="chart-features"),
        ], className="content-card"),
    ]

    return wrap_with_sidebar(
        session, "monitoring", content,
        title="Monitoring du modèle",
        subtitle="Visualisation des performances et de la santé du système",
    )


@dash.callback(
    Output("health-kpis", "children"),
    Output("chart-scores-distribution", "figure"),
    Output("chart-confusion", "figure"),
    Output("chart-roc", "figure"),
    Output("chart-pr", "figure"),
    Output("chart-features", "figure"),
    Input("health-kpis", "id"),
)
def load_monitoring(_):
    api_url = os.environ.get("API_URL", "http://api:8000")

    # 1. KPIs de santé
    try:
        r = requests.get(f"{api_url}/health", timeout=5)
        health = r.json() if r.status_code == 200 else {}
    except Exception:
        health = {}

    kpis = [
        _kpi("Statut API", "OK" if health.get("status") == "ok" else "Dégradé", ""),
        _kpi("Modèle chargé", "Oui" if health.get("model_loaded") else "Non", ""),
        _kpi("Encoder", "Oui" if health.get("checks", {}).get("encoder") else "Non", ""),
        _kpi("Databricks", "Connecté" if health.get("checks", {}).get("databricks") else "Indisponible", ""),
    ]

    # 2. Charger les prédictions
    try:
        r = requests.get(f"{api_url}/batch?seuil=0.0&limit=40000", timeout=30)
        data = r.json() if r.status_code == 200 else []
    except Exception:
        data = []

    if not data:
        empty = go.Figure().update_layout(title="Aucune donnée")
        return kpis, empty, empty, empty, empty, empty

    df = pd.DataFrame(data)

    # Distribution des scores
    dist_data = df.copy()
    if "actual_label" in dist_data.columns or "fraud_flag_reel" in dist_data.columns:
        actual_column = "actual_label" if "actual_label" in dist_data.columns else "fraud_flag_reel"
        dist_data["Classe réelle"] = pd.to_numeric(
            dist_data[actual_column], errors="coerce"
        ).map({0: "Normal", 1: "Fraude"}).fillna("Inconnue")
        fig_dist = px.histogram(
            dist_data,
            x="fraud_proba",
            color="Classe réelle",
            nbins=60,
            barmode="overlay",
            opacity=0.78,
            color_discrete_map={"Normal": "#2563eb", "Fraude": "#dc2626", "Inconnue": "#94a3b8"},
            title="Distribution des scores par classe réelle",
            labels={"fraud_proba": "Probabilité de fraude", "count": "Transactions"},
        )
    else:
        fig_dist = px.histogram(
            dist_data,
            x="fraud_proba",
            nbins=60,
            title="Distribution des scores",
            labels={"fraud_proba": "Probabilité de fraude", "count": "Transactions"},
            color_discrete_sequence=["#2563eb"],
        )
    fig_dist.add_vline(
        x=0.8394,
        line_dash="dash",
        line_color="#f59e0b",
        annotation_text="Seuil F1 0.8394",
        annotation_position="top right",
    )
    fig_dist.update_layout(
        height=380,
        margin={"t": 60, "b": 45, "l": 45, "r": 25},
        legend_title_text="Classe",
        bargap=0.04,
        template="plotly_white",
    )

    # Matrice de confusion réelle : vérité terrain contre seuil optimal du modèle.
    if "actual_label" in df.columns or "fraud_flag_reel" in df.columns:
        actual_column = "actual_label" if "actual_label" in df.columns else "fraud_flag_reel"
        y_true = pd.to_numeric(df[actual_column], errors="coerce")
        scores = pd.to_numeric(df["fraud_proba"], errors="coerce")
        valid = y_true.notna() & scores.notna()
        y_true = y_true[valid].astype(bool).astype(int)
        scores = scores[valid]
        y_pred = (scores >= 0.8394).astype(int)
        matrix = confusion_matrix(y_true, y_pred, labels=[0, 1])
        matrix_text = matrix.tolist()
        cm_title = "Matrice de confusion réelle (seuil F1 = 0.8394)"
    else:
        matrix_text = [[0, 0], [0, 0]]
        cm_title = "Matrice indisponible : vérité terrain absente"

    matrix_annotations = []
    max_cell = max(max(row) for row in matrix_text) or 1
    row_labels = ["Réel Normal", "Réel Fraude"]
    column_labels = ["Prédit Normal", "Prédit Fraude"]
    for row_index, row in enumerate(matrix_text):
        for column_index, value in enumerate(row):
            matrix_annotations.append({
                "x": column_labels[column_index],
                "y": row_labels[row_index],
                "text": f"<b>{value:,}</b>",
                "showarrow": False,
                "font": {
                    "size": 18,
                    "color": "white" if value >= max_cell * 0.35 else "#0f172a",
                },
            })

    fig_cm = go.Figure(data=go.Heatmap(
        z=matrix_text,
        x=column_labels,
        y=row_labels,
        colorscale=[
            [0, "#eff6ff"],
            [0.02, "#bfdbfe"],
            [0.35, "#60a5fa"],
            [1, "#123b78"],
        ],
        text=[[f"{value:,}" for value in row] for row in matrix_text],
        texttemplate="",
        showscale=False,
        hovertemplate="%{y}<br>%{x}<br>Transactions : %{z}<extra></extra>",
    ))
    fig_cm.update_layout(
        title=cm_title,
        height=350,
        margin={"t": 60, "b": 40, "l": 80, "r": 20},
        template="plotly_white",
        annotations=matrix_annotations,
        yaxis={"categoryorder": "array", "categoryarray": row_labels},
    )

    if "actual_label" in df.columns or "fraud_flag_reel" in df.columns:
        fpr, tpr, _ = roc_curve(y_true, scores)
        roc_auc = roc_auc_score(y_true, scores)
        precision, recall, _ = precision_recall_curve(y_true, scores)
        average_precision = average_precision_score(y_true, scores)

        fig_roc = go.Figure([
            go.Scatter(
                x=[0, 1], y=[0, 1], mode="lines",
                line={"dash": "dash", "color": "#94a3b8"}, name="Aléatoire",
            ),
            go.Scatter(
                x=fpr, y=tpr, mode="lines", fill="tozeroy",
                line={"color": "#2563eb", "width": 3},
                name=f"ROC (AUC = {roc_auc:.4f})",
            ),
        ])
        fig_pr = go.Figure([
            go.Scatter(
                x=recall, y=precision, mode="lines", fill="tozeroy",
                line={"color": "#10b981", "width": 3},
                name=f"PR (AP = {average_precision:.4f})",
            ),
        ])
    else:
        fig_roc = go.Figure().update_layout(title="ROC indisponible : vérité terrain absente")
        fig_pr = go.Figure().update_layout(title="PR indisponible : vérité terrain absente")

    fig_roc.update_layout(
        title="Courbe ROC réelle", height=380,
        xaxis_title="Taux de faux positifs", yaxis_title="Taux de vrais positifs",
        margin={"t": 60, "b": 45, "l": 50, "r": 25}, template="plotly_white",
        xaxis={"range": [0, 1]}, yaxis={"range": [0, 1]},
    )
    fig_pr.update_layout(
        title="Courbe Précision-Rappel réelle", height=380,
        xaxis_title="Rappel", yaxis_title="Précision",
        margin={"t": 60, "b": 45, "l": 50, "r": 25}, template="plotly_white",
        xaxis={"range": [0, 1]}, yaxis={"range": [0, 1]},
    )

    # Top features (statiques)
    features = pd.DataFrame({
        "feature": ["est_international", "montant", "is_night", "is_weekend",
                    "ecart_relatif_montant", "montant_cumule_client", "frais_transaction"],
        "importance": [0.470, 0.367, 0.354, 0.251, 0.141, 0.074, 0.062],
    }).sort_values("importance")

    fig_feat = px.bar(
        features, x="importance", y="feature", orientation="h",
        title="Top 7 features",
        color="importance", color_continuous_scale="Viridis",
    )
    fig_feat.update_layout(
        height=420,
        showlegend=False,
        margin={"t": 55, "b": 45, "l": 170, "r": 25},
        template="plotly_white",
        xaxis_title="Importance",
        yaxis_title="",
    )

    return kpis, fig_dist, fig_cm, fig_roc, fig_pr, fig_feat


def _kpi(label, value, icon):
    return html.Div([
        html.Div(icon, className="kpi-icon"),
        html.Div([
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value", style={"fontSize": "1.3rem"}),
        ]),
    ], className="kpi-card")
