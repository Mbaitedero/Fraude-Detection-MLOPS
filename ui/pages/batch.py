"""Page Transactions notées de l'utilisateur connecté."""

from dash import dash_table, html

from ui.auth import database
from ui.components.sidebar import wrap_with_sidebar


def layout(session):
    imports = database.get_batch_imports(session.get("user_id"), limit=50)
    content = [
        html.Div([
            html.H3("Mes transactions notées", className="card-title"),
            html.P(
                "Retrouvez ici uniquement vos imports CSV et vos scorings manuels.",
                className="card-subtitle",
            ),
            html.Div(
                _render_import_history(imports),
                id="user-scoring-history",
            ),
        ], className="content-card"),
    ]

    return wrap_with_sidebar(
        session, "batch", content,
        title="Transactions notées",
        subtitle="Vos imports CSV et vos scorings manuels",
    )


def _render_import_history(imports):
    if not imports:
        return html.Div(
            "Aucune transaction notée pour le moment.",
            className="alert-info",
        )

    sections = []
    for imported in imports:
        results = imported["results"]
        fraud_count = sum(row.get("decision") == "FRAUDE" for row in results)
        sections.append(html.Div([
            html.Div([
                html.Strong(
                    "Scoring manuel" if imported["filename"] == "Scoring manuel"
                    else imported["filename"]
                ),
                html.Span(
                    f"{len(results)} transactions · {fraud_count} fraude(s) · "
                    f"{imported['created_at']}",
                    className="status-detail",
                ),
            ], className="status-banner"),
            dash_table.DataTable(
                data=results,
                columns=[
                    {"name": column, "id": column}
                    for column in (results[0].keys() if results else [])
                ],
                page_size=10,
                sort_action="native",
                filter_action="native",
                style_table={"overflowX": "auto", "marginBottom": "20px"},
                style_cell={"textAlign": "left", "padding": "10px"},
                style_header={"backgroundColor": "#f1f5f9", "fontWeight": "700"},
            ),
        ], className="batch-import-result"))
    return sections
