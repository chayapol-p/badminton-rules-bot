"""
FastAPI app for the RAG workshop.

It has /health, which confirms the server is running and shows which models are
configured, and /chat, which answers one rules question. /chat currently serves
a stub answer (app/stub/answer.py) until the real flow can run with data/.
Neither endpoint calls Mistral or Claude yet, so both cost nothing to hit.

Run it from the project root:  uv run uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.chat import router as chat_router
from app.settings import load_settings


# Load the settings once at startup, so a missing key stops the server straight away
@asynccontextmanager
async def check_settings_at_startup(app: FastAPI):
    load_settings()
    yield


app = FastAPI(title="RAG workshop", lifespan=check_settings_at_startup)
app.include_router(chat_router)


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
