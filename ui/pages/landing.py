"""Page d'accueil publique."""

from dash import dcc, html

from ui.components.header import render_header


def layout(session=None):
    current_session = session or {}
    lang = current_session.get("langue") or current_session.get("lang", "fr")

    return html.Div([
        # Header en haut (hors du container centré)
        render_header(session=session, active_page="landing", lang=lang),

        # Fond et contenu
        html.Div([
            html.Div(className="landing-bg"),
            html.Div([
                # Hero
                html.Div([
                    html.Img(src="/assets/logo.svg", className="landing-hero-logo"),
                    html.H1("Mbaitedero Bank", className="landing-brand-big"),
                    html.P("DÉTECTION DE FRAUDE · MLOPS", className="landing-brand-tagline"),

                    html.P("Bienvenue sur", className="landing-welcome"),
                    html.H1("Mbaitedero Bank", className="landing-hero-title"),
                          html.P("Protégez chaque transaction grâce à l'IA de précision, en temps réel.",
                           className="landing-tagline"),

                    html.Div([
                        dcc.Link("Se connecter", href="/login", className="btn-landing-primary"),
                        dcc.Link("S'inscrire", href="/signup", className="btn-landing-secondary"),
                    ], className="landing-cta"),
                ], className="landing-hero"),

                # Sections ancres
                html.Section([
                    html.Div("01 / À PROPOS", className="landing-section-kicker"),
                    html.H2("La confiance se construit avec des décisions lisibles.",
                            className="landing-section-title"),
                          html.P("Mbaitedero Bank réunit données, modèles et supervision dans "
                              "un même espace de travail. Les équipes bancaires identifient "
                              "les signaux de fraude plus tôt, réduisent les faux positifs et "
                              "gagnent un temps précieux dans l'analyse des alertes et la "
                              "prise de décision.", className="landing-section-text"),
                    html.Div([
                        html.Div([
                            html.Strong("Vision unifiée"),
                            html.Span("Une lecture consolidée des signaux de risque et des alertes prioritaires."),
                        ], className="landing-detail-item"),
                        html.Div([
                            html.Strong("Décisions traçables"),
                            html.Span("Des décisions explicables, historisées et prêtes à être auditées."),
                        ], className="landing-detail-item"),
                        html.Div([
                            html.Strong("Pilotage continu"),
                            html.Span("Une supervision continue de la santé du modèle et de ses performances."),
                        ], className="landing-detail-item"),
                    ], className="landing-detail-grid"),
                ], id="about", className="landing-section"),

                html.Section([
                    html.Div("02 / SERVICES", className="landing-section-kicker"),
                    html.H2("Une suite conçue pour le rythme du risque.",
                            className="landing-section-title"),
                    html.Div([
                        html.Div([
                            html.Div("01", className="service-number"),
                            html.H3("Scoring temps réel"),
                            html.P("Analysez une transaction en quelques secondes grâce à "
                                "une API de scoring synchrone, des variables dérivées et "
                                "un niveau de risque directement exploitable."),
                        ], className="service-card"),
                        html.Div([
                            html.Div("02", className="service-number"),
                            html.H3("Scoring batch"),
                            html.P("Importez un fichier CSV, lancez le scoring de masse et "
                                "retrouvez les résultats persistés pour accélérer la revue "
                                "des opérations et la qualification des alertes."),
                        ], className="service-card"),
                        html.Div([
                            html.Div("03", className="service-number"),
                            html.H3("Monitoring MLOps"),
                            html.P("Suivez la disponibilité de l'API, les métriques du modèle "
                                "et les courbes de performance avec une instrumentation "
                                "compatible Prometheus et Grafana."),
                        ], className="service-card"),
                    ], className="services-grid"),
                ], id="services", className="landing-section"),

                html.Section([
                    html.Div("03 / CONTACT", className="landing-section-kicker"),
                    html.H2("Construisons une détection adaptée à vos enjeux.", className="landing-section-title"),
                    html.P("Demandez une démonstration personnalisée de la plateforme et découvrez "
                           "comment l'IA peut renforcer vos contrôles anti-fraude.",
                           className="landing-section-text"),
                    html.Div([
                        html.Div([
                            _contact_field("Nom", "contact-nom", "text"),
                            _contact_field("Prénom", "contact-prenom", "text"),
                        ], className="contact-form-row"),
                        html.Div([
                            _contact_field("Email", "contact-email", "email"),
                            _contact_field(
                                "Téléphone", "contact-telephone", "tel", required=False
                            ),
                        ], className="contact-form-row"),
                        html.Div([
                            html.Label("Message", htmlFor="contact-message", className="contact-label"),
                            dcc.Textarea(
                                id="contact-message",
                                name="message",
                                required=True,
                                minLength=10,
                                placeholder="Décrivez votre besoin ou votre projet.",
                                className="contact-input contact-textarea",
                            ),
                        ], className="contact-field"),
                        html.Button(
                            "Envoyer le message",
                            id="contact-submit",
                            type="button",
                            className="contact-submit",
                        ),
                        html.Div(id="contact-feedback", className="contact-feedback"),
                    ],
                        className="contact-form",
                    ),
                ], id="contact", className="landing-section"),

                # Footer
                html.Div([
                    html.Div([
                        html.Div("Mbaitedero", className="footer-brand"),
                        html.Div("BANK", className="footer-brand-sub"),
                    ], className="footer-identity"),
                    html.Div("Détection de fraude · Data · BI bancaire",
                             className="footer-description"),
                    html.Div([
                        html.Span("Réseaux professionnels", className="social-label"),
                        html.Div([
                            _social_link(
                                "LinkedIn",
                                "https://www.linkedin.com/in/japhet-allah-n-diguim-764878320/",
                                "linkedin",
                            ),
                            _social_link("GitHub", "https://github.com/Mbaitedero", "github"),
                            _social_link("Email", "mailto:allahndiguimj@gmail.com", "email"),
                        ], className="social-links"),
                    ], className="footer-social"),
                    html.Div([
                        html.Span("Projet de Fin d'Année"),
                        html.Span("Auteur : Japhet Allah-N'diguim", className="landing-author"),
                    ], className="footer-meta"),
                ], className="landing-footer"),
            ], className="landing-content"),
        ], className="landing-wrapper"),
    ], className="landing-page")


def _contact_field(label, field_id, input_type, required=True):
    return html.Div([
        html.Label(label, htmlFor=field_id, className="contact-label"),
        dcc.Input(
            id=field_id,
            name=field_id,
            type=input_type,
            required=required,
            className="contact-input",
        ),
    ], className="contact-field")


def _social_link(label, href, icon):
    icons = {
        "linkedin": "/assets/linkedin.svg",
        "github": "/assets/github.svg",
        "email": "/assets/gmail.svg",
    }
    return html.A([
        html.Img(src=icons[icon], className="social-icon", alt=""),
        html.Span(label, className="sr-only"),
    ], href=href, target="_blank" if not href.startswith("mailto:") else None,
       rel="noreferrer" if not href.startswith("mailto:") else None,
       className="social-link", title=label)
