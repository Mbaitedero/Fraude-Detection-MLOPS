"""Page du profil de l'utilisateur connecté."""

from dash import dcc, html

from ui.components.sidebar import wrap_with_sidebar


def layout(session):
    profile_image = session.get("profile_image")
    image_preview = html.Img(
        src=profile_image,
        className="profile-image-preview",
    ) if profile_image else html.Div(
        (session.get("prenom", "")[:1] + session.get("nom", "")[:1]).upper(),
        className="profile-image-placeholder",
    )

    return wrap_with_sidebar(
        session,
        "profile",
        [
            html.Div([
                html.Div([
                    image_preview,
                    dcc.Upload(
                        id="profile-image-upload",
                        children=html.Button(
                            "Choisir une photo",
                            className="btn-secondary",
                        ),
                        accept="image/png,image/jpeg,image/webp",
                        multiple=False,
                    ),
                    html.Div(
                        "PNG, JPG ou WEBP · 2 Mo maximum",
                        className="form-help",
                    ),
                ], className="profile-image-section"),
                _field("Fonction", "profile-fonction", session.get("fonction", "")),
            ], className="profile-identity-row"),
            html.Div([
                html.H3("Informations personnelles", className="card-title"),
                html.Div([
                    _field("Nom", "profile-nom", session.get("nom", "")),
                    _field("Prénom", "profile-prenom", session.get("prenom", "")),
                ], className="form-grid"),
                html.Div([
                    _field("Email", "profile-email", session.get("email", ""), "email"),
                    _field("Téléphone", "profile-telephone", session.get("telephone", ""), "tel"),
                ], className="form-grid"),
                _field("Adresse", "profile-adresse", session.get("adresse", "")),
                html.Button(
                    "Enregistrer les informations",
                    id="profile-save-btn",
                    n_clicks=0,
                    className="btn-primary-lg",
                ),
                html.Div(id="profile-save-message", className="auth-message"),
            ], className="content-card"),
            html.Div([
                html.H3("Sécurité", className="card-title"),
                html.P(
                    "Laissez ces champs vides pour conserver votre mot de passe actuel.",
                    className="card-subtitle",
                ),
                html.Div([
                    _field("Nouveau mot de passe", "profile-password", "", "password"),
                    _field("Confirmer le mot de passe", "profile-password-confirm", "", "password"),
                ], className="form-grid"),
                html.Button(
                    "Modifier le mot de passe",
                    id="profile-password-btn",
                    n_clicks=0,
                    className="btn-secondary",
                ),
                html.Div(id="profile-password-message", className="auth-message"),
            ], className="content-card"),
        ],
        title="Mon profil",
        subtitle="Gérez vos informations personnelles et votre accès",
    )


def _field(label, component_id, value, input_type="text"):
    return html.Div([
        html.Label(label, className="form-label"),
        dcc.Input(
            id=component_id,
            type=input_type,
            value=value,
            className="form-input",
        ),
    ], className="form-group")
