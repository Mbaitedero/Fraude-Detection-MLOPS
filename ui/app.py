"""
Dash UI — Routeur principal avec authentification, i18n, theme.
"""

import os
import smtplib
from email.message import EmailMessage

import dash
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv

from ui.auth import database
from ui.auth.session import is_logged_in
from ui.pages import (
    admin,
    alerts,
    batch,
    batch_upload,
    contact_messages,
    home,
    landing,
    login,
    monitoring,
    powerbi,
    profile,
    scoring,
    signup,
    users,
)

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Initialisation DB
# ─────────────────────────────────────────────────────────────
database.init_db()

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="Mbaitedero Bank — Détection de fraude",
    update_title=None,
)
server = app.server
# ─────────────────────────────────────────────────────────────
# Layout principal
# ─────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="session-store", storage_type="session"),
    dcc.Store(id="ui-store", storage_type="local", data={"theme": "light", "lang": "fr"}),

    # Wrapper thème (light/dark)
    html.Div(id="theme-wrapper", children=[
        html.Div(id="page-content"),
    ]),
])


# ─────────────────────────────────────────────────────────────
# ROUTES PUBLIQUES / PRIVÉES
# ─────────────────────────────────────────────────────────────
PUBLIC_ROUTES = {"/", "/login", "/signup"}
PROTECTED_ROUTES = {
    "/home", "/scoring", "/batch", "/batch-upload",
    "/monitoring", "/admin", "/powerbi", "/users", "/profile",
    "/alerts", "/contact-messages",
}
ADMIN_ROUTES = {"/admin", "/users", "/contact-messages"}


# ─────────────────────────────────────────────────────────────
# ROUTEUR PRINCIPAL
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("page-content", "children"),
    Output("url", "pathname", allow_duplicate=True),
    Input("url", "pathname"),
    Input("session-store", "data"),
    Input("ui-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def router(pathname, session, ui_data):
    logged_in = is_logged_in(session)

    # Fusionner la session et les préférences locales avec les mêmes clés
    # que celles attendues par les pages et la sidebar.
    merged = {**(session or {}), **(ui_data or {})}
    if logged_in:
        current_user = database.get_user(session["user_id"])
        if not current_user or not current_user["actif"]:
            return login.layout(merged), "/login"
        merged.update({
            "user_id": current_user["id"],
            "nom": current_user["nom"],
            "prenom": current_user["prenom"],
            "email": current_user["email"],
            "telephone": current_user["telephone"],
            "adresse": current_user["adresse"],
            "fonction": current_user["fonction"],
            "profile_image": current_user["profile_image"],
            "role": current_user["role"],
            "langue": current_user["langue"],
            "theme": current_user["theme"],
        })
    if ui_data and ui_data.get("lang"):
        merged["langue"] = ui_data["lang"]

    # ─── URL inconnue ───
    if pathname not in PUBLIC_ROUTES and pathname not in PROTECTED_ROUTES:
        if logged_in:
            return home.layout(merged), "/home"
        return landing.layout(merged), "/"

    # ─── Route protégée + non connecté → /login ───
    if pathname in PROTECTED_ROUTES and not logged_in:
        return login.layout(merged), "/login"

    if pathname in ADMIN_ROUTES and merged.get("role") != "admin":
        return home.layout(merged), "/home"

    # ─── Route publique / + connecté → /home ───
    if pathname == "/" and logged_in:
        return home.layout(merged), "/home"

    # ─── Login/Signup + connecté → /home ───
    if pathname in ("/login", "/signup") and logged_in:
        return home.layout(merged), "/home"

    # ─── Routes publiques ───
    if pathname == "/":
        return landing.layout(merged), dash.no_update
    if pathname == "/signup":
        return signup.layout(), dash.no_update
    if pathname == "/login":
        return login.layout(), dash.no_update

    # ─── Routes protégées + connecté ───
    routes = {
        "/home": home,
        "/scoring": scoring,
        "/batch": batch,
        "/batch-upload": batch_upload,
        "/monitoring": monitoring,
        "/admin": admin,
        "/powerbi": powerbi,
        "/users": users,
        "/profile": profile,
        "/alerts": alerts,
        "/contact-messages": contact_messages,
    }
    if pathname in routes:
        return routes[pathname].layout(merged), dash.no_update

    return landing.layout(merged), dash.no_update


@app.callback(
    Output("contact-feedback", "children"),
    Input("contact-submit", "n_clicks"),
    State("contact-nom", "value"),
    State("contact-prenom", "value"),
    State("contact-email", "value"),
    State("contact-telephone", "value"),
    State("contact-message", "value"),
    prevent_initial_call=True,
)
def handle_contact_message(n_clicks, nom, prenom, email, telephone, message):
    """Enregistre une demande et tente d'envoyer sa notification email."""
    if not n_clicks:
        raise PreventUpdate

    nom = str(nom or "").strip()
    prenom = str(prenom or "").strip()
    email = str(email or "").strip()
    telephone = str(telephone or "").strip()
    message = str(message or "").strip()

    fields = {
        "Nom": nom,
        "Prénom": prenom,
        "Email": email,
        "Message": message,
    }
    missing_fields = [label for label, value in fields.items() if not value]
    if missing_fields:
        return html.Div(
            "Veuillez remplir : " + ", ".join(missing_fields) + ".",
            className="contact-feedback-error",
        )
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return html.Div(
            "Veuillez saisir une adresse email valide.",
            className="contact-feedback-error",
        )
    if len(message.strip()) < 10:
        return html.Div(
            "Le message doit contenir au moins 10 caractères.",
            className="contact-feedback-error",
        )

    message_id = database.save_contact_message(
        nom, prenom, email, telephone, message
    )
    recipient = os.getenv("CONTACT_EMAIL", "allahndiguimj@gmail.com")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_host, smtp_user, smtp_password]):
        return html.Div(
            f"Message reçu et enregistré (référence #{message_id}). "
            "La notification email doit encore être configurée.",
            className="contact-feedback-warning",
        )

    email_message = EmailMessage()
    email_message["Subject"] = f"Nouvelle demande de contact #{message_id}"
    email_message["From"] = smtp_user
    email_message["To"] = recipient
    email_message["Reply-To"] = email.strip()
    email_message.set_content(
        f"Nouvelle demande de contact\n\n"
        f"Nom : {prenom.strip()} {nom.strip()}\n"
        f"Email : {email.strip()}\n"
        f"Téléphone : {telephone.strip()}\n\n"
        f"Message :\n{message.strip()}\n"
    )

    try:
        with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(email_message)
    except Exception:
        return html.Div(
            f"Message enregistré (référence #{message_id}), mais la notification "
            "email n'a pas pu être envoyée.",
            className="contact-feedback-warning",
        )

    return html.Div(
        "Votre message a été envoyé. Nous vous répondrons rapidement.",
        className="contact-feedback-success",
    )

# ─────────────────────────────────────────────────────────────
# INSCRIPTION
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("signup-message", "children"),
    Output("session-store", "data", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Input("signup-btn", "n_clicks"),
    State("signup-nom", "value"),
    State("signup-prenom", "value"),
    State("signup-email", "value"),
    State("signup-telephone", "value"),
    State("signup-adresse", "value"),
    State("signup-password", "value"),
    State("signup-password-confirm", "value"),
    prevent_initial_call=True,
)
def handle_signup(n_clicks, nom, prenom, email, telephone, adresse,
                  password, password_confirm):
    if n_clicks == 0:
        raise PreventUpdate

    if password != password_confirm:
        return (html.Div("Les mots de passe ne correspondent pas.",
                         className="auth-error"),
                dash.no_update, dash.no_update)

    success, result = database.create_user(
        nom, prenom, email, telephone, adresse, password
    )

    if not success:
        return (html.Div(f"{result}", className="auth-error"),
                dash.no_update, dash.no_update)

    user = database.get_user(result)
    session = {
        "user_id": user["id"],
        "nom": user["nom"],
        "prenom": user["prenom"],
        "email": user["email"],
        "telephone": user["telephone"],
        "adresse": user["adresse"],
        "fonction": user["fonction"],
        "profile_image": user["profile_image"],
        "role": user["role"],
        "langue": user["langue"],
        "theme": user["theme"],
    }
    database.log_action(user["id"], "signup", f"New user {user['email']}")

    return (html.Div("Compte créé ! Redirection...", className="auth-success"),
            session, "/home")


# ─────────────────────────────────────────────────────────────
# CONNEXION
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("login-message", "children"),
    Output("session-store", "data", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Input("login-btn", "n_clicks"),
    State("login-email", "value"),
    State("login-password", "value"),
    prevent_initial_call=True,
)
def handle_login(n_clicks, email, password):
    if n_clicks == 0:
        raise PreventUpdate

    if not email or not password:
        return (html.Div("Veuillez remplir tous les champs.", className="auth-error"),
                dash.no_update, dash.no_update)

    success, result = database.authenticate(email, password)

    if not success:
        return (html.Div(f"{result}", className="auth-error"),
                dash.no_update, dash.no_update)

    session = {
        "user_id": result["id"],
        "nom": result["nom"],
        "prenom": result["prenom"],
        "email": result["email"],
        "telephone": result["telephone"],
        "adresse": result["adresse"],
        "fonction": result["fonction"],
        "profile_image": result["profile_image"],
        "role": result["role"],
        "langue": result["langue"],
        "theme": result["theme"],
    }
    database.log_action(result["id"], "login", f"User {result['email']} logged in")

    return (html.Div("Connexion réussie !", className="auth-success"),
            session, "/home")


# ─────────────────────────────────────────────────────────────
# PROFIL UTILISATEUR
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("profile-save-message", "children"),
    Output("session-store", "data", allow_duplicate=True),
    Input("profile-save-btn", "n_clicks"),
    State("profile-nom", "value"),
    State("profile-prenom", "value"),
    State("profile-email", "value"),
    State("profile-telephone", "value"),
    State("profile-adresse", "value"),
    State("profile-fonction", "value"),
    State("profile-image-upload", "contents"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def save_profile(n_clicks, nom, prenom, email, telephone, adresse, fonction,
                 profile_image, session):
    if not n_clicks or not session or not session.get("user_id"):
        raise PreventUpdate

    success, message = database.update_user_profile(
        session["user_id"], nom, prenom, email, telephone, adresse,
        fonction=fonction, profile_image=profile_image,
    )
    if not success:
        return html.Div(message, className="auth-error"), dash.no_update

    user = database.get_user(session["user_id"])
    updated_session = {
        **session,
        "nom": user["nom"],
        "prenom": user["prenom"],
        "email": user["email"],
        "telephone": user["telephone"],
        "adresse": user["adresse"],
        "fonction": user["fonction"],
        "profile_image": user["profile_image"],
    }
    database.log_action(user["id"], "profile_update", "Personal information updated")
    return html.Div(message, className="auth-success"), updated_session


@app.callback(
    Output("profile-password-message", "children"),
    Input("profile-password-btn", "n_clicks"),
    State("profile-password", "value"),
    State("profile-password-confirm", "value"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def change_password(n_clicks, password, password_confirm, session):
    if not n_clicks or not session or not session.get("user_id"):
        raise PreventUpdate
    if not password or password != password_confirm:
        return html.Div(
            "Les mots de passe ne correspondent pas.", className="auth-error"
        )

    user = database.get_user(session["user_id"])
    success, message = database.update_user_profile(
        user["id"], user["nom"], user["prenom"], user["email"],
        user["telephone"], user["adresse"], password=password,
        fonction=user["fonction"], profile_image=user["profile_image"],
    )
    if success:
        database.log_action(user["id"], "password_update", "Password updated")
    return html.Div(message, className="auth-success" if success else "auth-error")


# ─────────────────────────────────────────────────────────────
# DÉCONNEXION
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("session-store", "data", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Input("logout-btn", "n_clicks"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def handle_logout(n_clicks, session):
    if n_clicks == 0:
        raise PreventUpdate

    if session and session.get("user_id"):
        database.log_action(session["user_id"], "logout",
                            f"User {session.get('email')} logged out")

    return None, "/"


# ─────────────────────────────────────────────────────────────
# TOGGLE THÈME (light/dark) — fonctionne même sans session
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("ui-store", "data", allow_duplicate=True),
    Output("theme-wrapper", "className"),
    Input("btn-theme-toggle", "n_clicks"),
    State("ui-store", "data"),
    prevent_initial_call=True,
)
def toggle_theme(n_clicks, ui_data):
    if not n_clicks:
        raise PreventUpdate

    ui_data = ui_data or {"theme": "light", "lang": "fr"}
    current = ui_data.get("theme", "light")
    new_theme = "dark" if current == "light" else "light"
    ui_data["theme"] = new_theme

    return ui_data, f"theme-{new_theme}"


# ─────────────────────────────────────────────────────────────
# TOGGLE LANGUE (FR/EN) — fonctionne même sans session
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("ui-store", "data", allow_duplicate=True),
    Input("btn-lang-toggle", "n_clicks"),
    State("ui-store", "data"),
    prevent_initial_call=True,
)
def toggle_lang(n_clicks, ui_data):
    if not n_clicks:
        raise PreventUpdate

    ui_data = ui_data or {"theme": "light", "lang": "fr"}
    current = ui_data.get("lang", "fr")
    new_lang = "en" if current == "fr" else "fr"
    ui_data["lang"] = new_lang

    return ui_data


# ─────────────────────────────────────────────────────────────
# APPLIQUER LE THÈME AU DÉMARRAGE (depuis ui-store)
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("theme-wrapper", "className", allow_duplicate=True),
    Input("ui-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def apply_theme_on_load(ui_data):
    if not ui_data:
        return "theme-light"
    return f"theme-{ui_data.get('theme', 'light')}"
# ─────────────────────────────────────────────────────────────
# MARQUER ALERTES COMME LUES
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("session-store", "data", allow_duplicate=True),
    Input("mark-alerts-read-btn", "n_clicks"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def mark_alerts_read(n_clicks, session):
    if not n_clicks or not session:
        raise PreventUpdate
    if session.get("user_id"):
        database.mark_all_alerts_read(session["user_id"])
    return session


# ─────────────────────────────────────────────────────────────
# LANCEMENT
# ─────────────────────────────────────────────────────────────
# Exposé pour gunicorn (Render)
server = app.server

if __name__ == "__main__":
    app.run(debug=True, port=8050, host="0.0.0.0")
