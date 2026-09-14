"""
Sidebar réutilisable pour toutes les pages du dashboard.
"""

from dash import html, dcc
from ui.i18n import t
from ui.auth import database


# ═════════════════════════════════════════════════════════════
# Configuration de la navigation
# ═════════════════════════════════════════════════════════════

NAV_ITEMS = [
    {"href": "/home",         "icon": "", "label": "Accueil",             "id": "home",         "admin_only": False},
    {"href": "/scoring",      "icon": "", "label": "Scoring manuel",      "id": "scoring",      "admin_only": False},
    {"href": "/batch-upload", "icon": "", "label": "Import CSV",          "id": "batch_upload", "admin_only": False},
    {"href": "/batch",        "icon": "", "label": "Transactions notées", "id": "batch",        "admin_only": False},
        {"href": "/alerts",       "icon": "", "label": "Alertes",              "id": "alerts",       "admin_only": False},
    {"href": "/monitoring",   "icon": "", "label": "Monitoring",          "id": "monitoring",   "admin_only": False},
    {"href": "/admin",        "icon": "", "label": "Admin MLOps",         "id": "admin",        "admin_only": True},
    {"href": "/users",        "icon": "", "label": "Utilisateurs",        "id": "users",        "admin_only": True},
        {"href": "/contact-messages", "icon": "", "label": "Messages contact",    "id": "contact_messages", "admin_only": True},
    {"href": "/powerbi",      "icon": "", "label": "Power BI",            "id": "powerbi",      "admin_only": False},
    {"href": "/profile",      "icon": "", "label": "Mon profil",          "id": "profile",      "admin_only": False},
]


# ═════════════════════════════════════════════════════════════
# Render sidebar
# ═════════════════════════════════════════════════════════════

def render_sidebar(session, active_page, lang="fr"):
    """Rend la sidebar complète."""
    user_name = f"{session.get('prenom', '')} {session.get('nom', '')}".strip()
    initial = user_name[:1].upper() if user_name else "?"
    role = session.get("role", "analyst")
    profile_image = session.get("profile_image")
    avatar = (
        html.Img(src=profile_image, className="user-avatar user-avatar-image")
        if profile_image
        else html.Div(initial, className="user-avatar")
    )

    # Filtrer les items admin_only
    items = [i for i in NAV_ITEMS if not i["admin_only"] or role == "admin"]
    unread_alerts = database.count_unread_alerts(session["user_id"]) if session.get("user_id") else 0

    nav_links = []
    for item in items:
        is_active = item["id"] == active_page
        nav_links.append(
            dcc.Link(
                [
                    html.Span(t(item["id"], lang), className="nav-label"),
                    html.Span(str(unread_alerts), className="alert-count-badge")
                    if item["id"] == "alerts" and unread_alerts else None,
                ],
                href=item["href"],
                className=f"nav-item {'nav-item-active' if is_active else ''}",
            )
        )

    return html.Div([
        # ─── En-tête logo ───
        html.Div([
            html.Img(src="/assets/logo.svg", className="sidebar-logo-img"),
            html.Div([
                html.Div("Mbaitedero", className="sidebar-brand"),
                html.Div("BANK", className="sidebar-brand-sub"),
            ], className="sidebar-brand-text"),
        ], className="sidebar-header"),

        # ─── Navigation ───
        html.Nav(nav_links, className="sidebar-nav"),

        # ─── Footer utilisateur ───
        html.Div([
            html.Div([
                avatar,
                html.Div([
                    html.Div(user_name or "Utilisateur", className="user-name"),
                    html.Div(session.get("fonction", ""), className="user-function"),
                    html.Div(session.get("email", ""), className="user-email"),
                ], className="user-details"),
            ], className="user-info"),
            html.Button(t("logout", lang), id="logout-btn", n_clicks=0,
                        className="logout-btn"),
        ], className="sidebar-footer"),
    ], className="sidebar")


def wrap_with_sidebar(session, active_page, content, title=None, subtitle=None):
    """Enveloppe une page avec la sidebar + topbar."""
    lang = session.get("langue") or session.get("lang", "fr")

    topbar_children = []
    if title:
        topbar_children.append(html.H1(title, className="page-title"))
    if subtitle:
        topbar_children.append(html.Div(subtitle, className="page-subtitle"))
    else:
        user_name = f"{session.get('prenom', '')} {session.get('nom', '')}".strip()
        topbar_children.append(
            html.Div(
                f"{t('connected_as', lang)} {user_name}",
                className="page-subtitle",
            )
        )

    header_controls = render_header_controls(lang)

    return html.Div([
        render_sidebar(session, active_page, lang),
        html.Div([
            html.Div([
                html.Div(topbar_children, className="topbar-heading"),
                header_controls,
            ], className="topbar"),
            html.Div(content, className="page-body"),
        ], className="main-content"),
    ], className="dashboard-container")


def render_header_controls(lang="fr"):
    """Rend les contrôles globaux dans le header du dashboard."""
    return html.Div([
        html.Button(
            "🌙",
            id="btn-theme-toggle",
            n_clicks=0,
            className="dashboard-header-btn",
            title="Changer le thème",
        ),
        html.Button(
            "FR" if lang == "fr" else "EN",
            id="btn-lang-toggle",
            n_clicks=0,
            className="dashboard-header-btn dashboard-language-btn",
            title="Changer la langue",
        ),
    ], className="dashboard-header-controls")