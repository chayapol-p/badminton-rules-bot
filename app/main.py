"""
FastAPI app for the RAG workshop.

For now it has one endpoint, /health. It confirms the server is running and
shows which models are configured. It never calls Mistral or Claude, so it
costs nothing to hit. Later labs add the /chat endpoint.

Run it from the project root:  uv run uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.settings import load_settings


# Load the settings once at startup, so a missing key stops the server straight away
@asynccontextmanager
async def check_settings_at_startup(app: FastAPI):
    load_settings()
    yield


app = FastAPI(title="RAG workshop", lifespan=check_settings_at_startup)


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
