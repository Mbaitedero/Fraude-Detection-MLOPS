"""Dashboard principal après connexion."""

from dash import html
import requests
import os

from ui.components.sidebar import render_header_controls, render_sidebar
from ui.i18n import t


def layout(session):
    lang = session.get("langue") or session.get("lang", "fr")
    user_name = f"{session.get('prenom', '')} {session.get('nom', '')}".strip()
    
    # ── Récupération des KPIs avec capture d'erreur détaillée ──
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    kpis = None
    error_msg = None
    
    try:
        r = requests.get(f"{api_url}/model/info", timeout=60)
        if r.status_code == 200:
            kpis = r.json()
        else:
            error_msg = f"HTTP {r.status_code} — {r.text[:200]}"
    except Exception as e: # noqa: BLE001
        error_msg = f"{type(e).__name__} : {e}"
    
    # ── Debug : log dans la console ──
    print(f"[DEBUG] api_url = {api_url}")
    print(f"[DEBUG] kpis = {kpis is not None}")
    print(f"[DEBUG] error = {error_msg}")
    
    # ── Bannière de statut ──
    if kpis:
        banner = html.Div([
            html.Div("", className="status-icon"),
            html.Div([
                html.Strong(t("model_operational", lang)),
                html.Div(t("champion_ready", lang),
                         className="status-detail"),
            ]),
        ], className="status-banner")
    else:
        banner = html.Div([
            html.Div("", className="status-icon"),
            html.Div([
                html.Strong("Modèle indisponible"),
                html.Div(f"API URL : {api_url}", className="status-detail",
                         style={"fontFamily": "monospace", "fontSize": "0.8rem"}),
                html.Div(f"Erreur : {error_msg}", className="status-detail",
                         style={"fontFamily": "monospace", "fontSize": "0.8rem",
                                "color": "#991b1b", "marginTop": "6px"}),
            ]),
        ], className="status-banner status-warning")
    
    # ── KPIs ──
    kpi_cards = [
        _kpi_card("PR-AUC", f"{kpis['pr_auc']:.4f}" if kpis and kpis.get('pr_auc') else "—",
                  "", "primary"),
        _kpi_card("ROC-AUC", f"{kpis['roc_auc']:.4f}" if kpis and kpis.get('roc_auc') else "—",
                  "", "success"),
        _kpi_card("Lift", f"{kpis['lift']:.2f}×" if kpis and kpis.get('lift') else "—",
                  "", "warning"),
        _kpi_card("Version champion", f"v{kpis['version']}" if kpis else "—",
                  "", "info"),
    ]
    
    return html.Div([
        render_sidebar(session, "home", lang),
        
        # ─── CONTENU ───
        html.Div([
            html.Div([
                html.Div([
                    html.H1(t("dashboard", lang), className="page-title"),
                    html.Div(f"{t('connected_as', lang)} {user_name}", className="page-subtitle"),
                ], className="topbar-heading"),
                render_header_controls(session.get("langue") or session.get("lang", "fr")),
            ], className="topbar"),
            
            html.Div(kpi_cards, className="kpi-grid"),
            
            html.Div([
                html.Div([
                    html.H3(t("technical_stack", lang)),
                    html.P("Databricks · Delta Lake · Unity Catalog · MLflow · "
                           "scikit-learn · FastAPI · Dash"),
                ], className="info-card"),
                html.Div([
                    html.H3(t("architecture", lang)),
                    html.P("Bronze → Silver → Gold → Modèle ML → API FastAPI → UI Dash"),
                ], className="info-card"),
            ], className="info-grid"),
            
            banner,
        ], className="main-content"),
    ], className="dashboard-container")


def _kpi_card(label, value, icon, color):
    return html.Div([
        html.Div([
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value"),
        ]),
    ], className="kpi-card")

def _kpi_card(label, value, icon, color):
    return html.Div([
        html.Div([
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value"),
        ]),
    ], className="kpi-card")