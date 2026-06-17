"""Custom Swagger UI that follows the OS light/dark preference.

FastAPI's bundled Swagger UI is light-only. We reuse its HTML generator and
inject a dark theme guarded by ``@media (prefers-color-scheme: dark)`` so the
page automatically matches the user's system setting with no toggle needed.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

# Dark theme scoped entirely under prefers-color-scheme: dark. In light mode
# none of these rules apply and the stock Swagger UI shows through unchanged.
DARK_MODE_CSS = """
@media (prefers-color-scheme: dark) {
  body, .swagger-ui { background: #0d1117; color: #c9d1d9; }
  .swagger-ui .topbar { background: #161b22; border-bottom: 1px solid #30363d; }
  .swagger-ui .info .title,
  .swagger-ui .info h1, .swagger-ui .info h2,
  .swagger-ui .info h3, .swagger-ui .info h4, .swagger-ui .info h5,
  .swagger-ui .info p, .swagger-ui .info li,
  .swagger-ui .info table, .swagger-ui label,
  .swagger-ui .scheme-container .schemes > label,
  .swagger-ui .opblock-tag,
  .swagger-ui .opblock .opblock-summary-operation-id,
  .swagger-ui .opblock .opblock-summary-path,
  .swagger-ui .opblock .opblock-summary-path__deprecated,
  .swagger-ui .opblock .opblock-summary-description,
  .swagger-ui .opblock-description-wrapper p,
  .swagger-ui .opblock-external-docs-wrapper p,
  .swagger-ui .opblock-title_normal p,
  .swagger-ui table thead tr th,
  .swagger-ui table thead tr td,
  .swagger-ui .parameter__name,
  .swagger-ui .parameter__type,
  .swagger-ui .response-col_status,
  .swagger-ui .response-col_links,
  .swagger-ui .responses-inner h4,
  .swagger-ui .responses-inner h5,
  .swagger-ui .model-title,
  .swagger-ui .model,
  .swagger-ui section.models h4,
  .swagger-ui .tab li,
  .swagger-ui .markdown p, .swagger-ui .markdown li,
  .swagger-ui .renderedMarkdown p { color: #c9d1d9; }

  .swagger-ui .scheme-container { background: #161b22; box-shadow: none; }
  .swagger-ui .opblock-tag { border-bottom: 1px solid #30363d; }

  .swagger-ui .opblock { background: #161b22; border: 1px solid #30363d;
    box-shadow: none; }
  .swagger-ui .opblock .opblock-section-header { background: #1c2128;
    box-shadow: none; }
  .swagger-ui .opblock .opblock-section-header h4,
  .swagger-ui .opblock .opblock-section-header > label { color: #c9d1d9; }

  /* HTTP method badges keep their accent but darken their tinted bodies. */
  .swagger-ui .opblock.opblock-post { background: rgba(73,204,144,.08);
    border-color: #2ea043; }
  .swagger-ui .opblock.opblock-get { background: rgba(97,175,254,.08);
    border-color: #1f6feb; }
  .swagger-ui .opblock.opblock-delete { background: rgba(249,62,62,.08);
    border-color: #da3633; }

  .swagger-ui input, .swagger-ui textarea, .swagger-ui select {
    background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; }
  .swagger-ui .btn { color: #c9d1d9; border-color: #30363d; }
  .swagger-ui .btn.execute { background: #238636; border-color: #2ea043;
    color: #fff; }
  .swagger-ui .btn.authorize { color: #3fb950; border-color: #3fb950; }
  .swagger-ui .btn.authorize svg { fill: #3fb950; }

  /* Code / examples / models. */
  .swagger-ui .highlight-code, .swagger-ui .microlight,
  .swagger-ui .model-box, .swagger-ui section.models,
  .swagger-ui .responses-inner, .swagger-ui table.model tbody tr td {
    background: #0d1117; }
  .swagger-ui section.models { border: 1px solid #30363d; }
  .swagger-ui .model-box { box-shadow: none; }
  .swagger-ui .prop-type { color: #79c0ff; }
  .swagger-ui .prop-format { color: #8b949e; }

  .swagger-ui svg:not(:root) { fill: #c9d1d9; }
  .swagger-ui .opblock-summary-method { color: #fff; }
}
"""


def configure_dark_mode_docs(app: FastAPI) -> None:
    """Replace the default /docs with a system-theme-aware Swagger UI."""

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui() -> HTMLResponse:
        response = get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - Docs",
        )
        html = response.body.decode("utf-8")
        html = html.replace("</head>", f"<style>{DARK_MODE_CSS}</style></head>")
        return HTMLResponse(html)
