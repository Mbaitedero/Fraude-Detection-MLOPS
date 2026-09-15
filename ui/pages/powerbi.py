"""
Page Dashboards BI — Galerie des captures Power BI.
"""

import os

from dash import dcc, html

from ui.components.sidebar import wrap_with_sidebar

# ─────────────────────────────────────────────────────────────
# CONFIGURATION — Ajoute autant de dashboards que tu veux
# ─────────────────────────────────────────────────────────────
# Pour ajouter une nouvelle page :
#   1. Place l'image dans ui/assets/bi_xxx.png
#   2. Ajoute une entrée dans la liste ci-dessous
#   3. Relance l'UI
# ─────────────────────────────────────────────────────────────

DASHBOARDS = [
    {
        "id": "accueil",
        "titre": "Vue d'ensemble du reporting BI",
        "description": "Profil de  l'Entreprise",
        "image": "/assets/bi_accueil.png",
    },
    {
        "id": "creances",
        "titre": "Reporting des Créances et Suivi du Risque",
        "description": "Analyse Bâle III : EAD, provisions, PD, LGD par catégorie réglementaire",
        "image": "/assets/bi_creances.png",
    },
    {
        "id": "liquidite",
        "titre": "Suivi de la Liquidité et des Ratios Réglementaires",
        "description": "LCR et NSFR sur 24 mois — conformité réglementaire",
        "image": "/assets/bi_liquidite.png",
    },
    {
        "id": "transactions",
        "titre": "Surveillance des Transactions et de la Fraude",
        "description": "Détection de fraude : évolution mensuelle, canaux, carte géographique",
        "image": "/assets/bi_transactions.png",
    },
    # Ajoute d'autres dashboards ici
]


# ─────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────

def layout(session):
    """Page Dashboards BI."""
    # ✅ APRÈS
    powerbi_url = os.environ.get("POWERBI_URL", "").strip()
    content = (
        [_render_iframe(powerbi_url)]
        if powerbi_url and "?r=" in powerbi_url
        else [_render_gallery()]
    )

    return wrap_with_sidebar(
        session, "powerbi", content,
        title="Dashboards BI",
        subtitle=f"Galerie de {len(DASHBOARDS)} rapports métier et réglementaires",
    )


# ─────────────────────────────────────────────────────────────
# MODE IFRAME
# ─────────────────────────────────────────────────────────────

def _render_iframe(url):
    return html.Div([
        html.H3("Rapport Power BI en direct", className="card-title"),
        html.P("Rapport publié sur le web — mise à jour automatique",
               className="card-subtitle"),
        html.Iframe(
            src=url,
            style={
                "width": "100%",
                "height": "800px",
                "border": "none",
                "borderRadius": "12px",
                "boxShadow": "0 4px 12px rgba(0,0,0,0.08)",
            },
        ),
    ], className="content-card")


# ─────────────────────────────────────────────────────────────
# MODE GALERIE
# ─────────────────────────────────────────────────────────────

def _render_gallery():
    return html.Div([
        # ─── En-tête ───
        html.Div([
            html.H3(f"Galerie des dashboards BI ({len(DASHBOARDS)} rapports)",
                    className="card-title"),
            html.P(
                "Tableaux de bord couvrant le reporting réglementaire "
                "(Bâle III, LCR/NSFR) et la détection de fraude.",
                className="card-subtitle",
            ),
        ], className="content-card"),

        # ─── Onglets ───
        dcc.Tabs(
            id="bi-tabs",
            value=DASHBOARDS[0]["id"],
            children=[
                dcc.Tab(
                    label=_short_label(d["titre"]),
                    value=d["id"],
                    children=_render_dashboard(d),
                    className="bi-tab",
                    selected_className="bi-tab-selected",
                )
                for d in DASHBOARDS
            ],
            className="bi-tabs-container",
        ),
    ])


def _short_label(titre):
    """Raccourcit les titres longs pour les onglets."""
    return titre[:40] + ("…" if len(titre) > 40 else "")


def _render_dashboard(dashboard):
    return html.Div([
        # ─── En-tête du dashboard ───
        html.Div([
            html.H2(dashboard["titre"], className="bi-dashboard-title"),
            html.P(dashboard["description"], className="bi-dashboard-desc"),
        ], className="bi-dashboard-header"),

        # ─── Image ───
        html.Div([
            html.Img(
                src=dashboard["image"],
                className="bi-dashboard-image",
                alt=dashboard["titre"],
            ),
        ], className="bi-dashboard-image-wrapper"),

        # ─── Actions ───
        html.Div([
            html.A(
                ["Ouvrir en grand"],
                href=dashboard["image"],
                target="_blank",
                className="bi-action-btn",
            ),
        ], className="bi-dashboard-actions"),
    ], className="bi-dashboard-card")
