"""Page de connexion."""

from dash import dcc, html


def layout():
    return html.Div([
        html.Div(className="auth-bg"),
        
        html.Div([
            html.Div([
                html.Div("", className="auth-logo"),
                html.H1("Connexion", className="auth-title"),
                html.P("Accédez à votre tableau de bord", className="auth-subtitle"),
            ], className="auth-header"),
            
            html.Div([
                html.Div([
                    html.Label("Email", className="auth-label"),
                    dcc.Input(id="login-email", type="email", placeholder="vous@exemple.com",
                              className="auth-input"),
                ], className="auth-field"),
                
                html.Div([
                    html.Label("Mot de passe", className="auth-label"),
                    dcc.Input(id="login-password", type="password", placeholder="••••••••",
                              className="auth-input"),
                ], className="auth-field"),
                
                html.Button("Se connecter", id="login-btn", n_clicks=0,
                            className="auth-btn"),
                
                html.Div(id="login-message", className="auth-message"),
                
                html.Div([
                    html.Span("Pas encore de compte ? "),
                    dcc.Link("S'inscrire", href="/signup", className="auth-link"),
                ], className="auth-switch"),
                
                html.Div([
                    dcc.Link("← Retour à l'accueil", href="/", className="auth-back"),
                ], className="auth-back-container"),
            ], className="auth-card"),
        ], className="auth-wrapper"),
    ], className="auth-container")