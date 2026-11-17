"""
FastAPI app for the RAG workshop.

Two endpoints:
- /health confirms the server is running and shows which models are configured.
  It never calls Mistral or Claude, so it costs nothing to hit.
- POST /chat answers one rules question as a stream of server-sent events
  (app/chat_endpoint.py; docs/specs/ask-a-rules-question.md).
- /rule-books/<file> serves the frozen rule-book PDFs the citations link to (app/pdf_links.py).

Run it from the project root:  uv run uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.chat_endpoint import router as chat_router
from app.pdf_links import RULE_BOOKS_ADDRESS, RULE_BOOKS_FOLDER
from app.settings import load_settings


# Load the settings once at startup, so a missing key stops the server straight away
@asynccontextmanager
async def check_settings_at_startup(app: FastAPI):
    load_settings()
    yield


app = FastAPI(title="RAG workshop", lifespan=check_settings_at_startup)
app.include_router(chat_router)

# The rule-book PDFs the citation links open. check_dir=False, because the PDFs are downloaded by hand and never
# committed: without them the app still answers, and only the PDF links answer 404
app.mount(RULE_BOOKS_ADDRESS, StaticFiles(directory=RULE_BOOKS_FOLDER, check_dir=False), name="rule-books")


# Health check: server status and the configured model names (never the keys)
@app.get("/health")
def read_health() -> dict:
    settings = load_settings()
    return {
        "status": "ok",
        "models": {
            "mistral_answer": settings.mistral_answer_model,
            "mistral_draft": settings.mistral_draft_model,
            "mistral_embedding": settings.mistral_embedding_model,
            "claude_comparison": settings.claude_comparison_model,
        },
    }
