"""Page d'inscription."""

from dash import dcc, html


def layout():
    return html.Div([
        html.Div(className="auth-bg"),
        
        html.Div([
            # En-tête
            html.Div([
                html.Div("", className="auth-logo"),
                html.H1("Créer un compte", className="auth-title"),
                html.P("Rejoignez Mbaitedero Bank", className="auth-subtitle"),
            ], className="auth-header"),
            
            # Formulaire
            html.Div([
                html.Div([
                    html.Div([
                        html.Label("Nom *", className="auth-label"),
                        dcc.Input(id="signup-nom", type="text", placeholder="Allah-N'diguim",
                                  className="auth-input"),
                    ], className="auth-field"),
                    
                    html.Div([
                        html.Label("Prénom *", className="auth-label"),
                        dcc.Input(id="signup-prenom", type="text", placeholder="Japhet",
                                  className="auth-input"),
                    ], className="auth-field"),
                ], className="auth-row"),
                
                html.Div([
                    html.Label("Email *", className="auth-label"),
                    dcc.Input(id="signup-email", type="email", placeholder="vous@exemple.com",
                              className="auth-input"),
                ], className="auth-field"),
                
                html.Div([
                    html.Label("Téléphone", className="auth-label"),
                    dcc.Input(id="signup-telephone", type="tel", placeholder="06 12 34 56 78",
                              className="auth-input"),
                ], className="auth-field"),
                
                html.Div([
                    html.Label("Adresse", className="auth-label"),
                    dcc.Input(id="signup-adresse", type="text", placeholder="12 rue Exemple, Casablanca",
                              className="auth-input"),
                ], className="auth-field"),
                
                html.Div([
                    html.Div([
                        html.Label("Mot de passe *", className="auth-label"),
                        dcc.Input(id="signup-password", type="password", placeholder="••••••••",
                                  className="auth-input"),
                    ], className="auth-field"),
                    
                    html.Div([
                        html.Label("Confirmation *", className="auth-label"),
                        dcc.Input(id="signup-password-confirm", type="password", placeholder="••••••••",
                                  className="auth-input"),
                    ], className="auth-field"),
                ], className="auth-row"),
                
                html.Button("Créer mon compte", id="signup-btn", n_clicks=0,
                            className="auth-btn"),
                
                html.Div(id="signup-message", className="auth-message"),
                
                html.Div([
                    html.Span("Déjà un compte ? "),
                    dcc.Link("Se connecter", href="/login", className="auth-link"),
                ], className="auth-switch"),
            ], className="auth-card"),
        ], className="auth-wrapper"),
    ], className="auth-container")