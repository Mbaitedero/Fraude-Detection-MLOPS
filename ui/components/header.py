"""
Header universel avec logo, navigation, toggle thème, toggle langue.
Utilisé sur toutes les pages (landing + dashboard).
"""

from dash import html, dcc
import dash


def render_header(session=None, active_page=None, lang="fr"):
    """
    Args:
        session: dict session (None si non connecté)
        active_page: id de la page active ("home", "scoring", ...)
        lang: "fr" ou "en"
    """
    
    # Textes selon la langue
    texts = {
        "fr": {
            "about": "À propos",
            "services": "Services",
            "contact": "Contact",
            "login": "Se connecter",
            "signup": "S'inscrire",
            "dashboard": "Tableau de bord",
            "logout": "Déconnexion",
            "lang": "FR",
        },
        "en": {
            "about": "About",
            "services": "Services",
            "contact": "Contact",
            "login": "Login",
            "signup": "Sign up",
            "dashboard": "Dashboard",
            "logout": "Logout",
            "lang": "EN",
        },
    }
    t = texts.get(lang, texts["fr"])
    
    # Liens de navigation
    nav_links = [
        html.A(t["about"], href="#about", className="header-link"),
        html.A(t["services"], href="#services", className="header-link"),
        html.A(t["contact"], href="#contact", className="header-link"),
    ]
    
    # Actions à droite
    right_actions = [
        # Toggle langue
        html.Button(
            t["lang"] if lang == "fr" else "EN",
            id="btn-lang-toggle",
            n_clicks=0,
            className="header-icon-btn",
            title="Changer de langue / Change language",
        ),
        # Toggle thème
        html.Button(
            "🌙",
            id="btn-theme-toggle",
            n_clicks=0,
            className="header-icon-btn",
            title="Changer de thème / Change theme",
        ),
    ]
    
    # Boutons login/signup OU dashboard/logout selon session
    if session and session.get("user_id"):
        right_actions.append(
            html.A(t["dashboard"], href="/home", className="header-btn header-btn-primary")
        )
        right_actions.append(
            html.Button(
                t["logout"],
                id="logout-btn",
                n_clicks=0,
                className="header-btn header-btn-outline",
            )
        )
    else:
        right_actions.append(
            html.A(t["login"], href="/login", className="header-btn header-btn-outline")
        )
        right_actions.append(
            html.A(t["signup"], href="/signup", className="header-btn header-btn-primary")
        )
    
    return html.Header([
        # ─── Logo (à gauche) ───
        html.A([
            html.Img(src="/assets/logo.svg", className="header-logo"),
            html.Div([
                html.Div("Mbaitedero", className="header-brand"),
                html.Div("BANK", className="header-brand-sub"),
            ], className="header-brand-text"),
        ], href="/", className="header-logo-container"),
        
        # ─── Navigation centrale ───
        html.Nav(nav_links, className="header-nav"),
        
        # ─── Actions (à droite) ───
        html.Div(right_actions, className="header-actions"),
    ], className="header", id="app-header")