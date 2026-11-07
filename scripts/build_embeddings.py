"""
Embeds the chunks, the windows and the golden questions with mistral-embed, once, and saves them.

Five sets, each saved to data/embeddings/<name>.npz:
  clauses_search_text  each clause chunk's search_text (context header, then the clause)
  clauses_text         each clause chunk's text alone, for the context header comparison
  clauses_search_text_with_parents   the header, the parent clauses, then the clause
  windows              each fixed-size window's text
  questions            each golden question, keyed by its id

A set that is already saved with the same model is skipped, so a rerun costs nothing.
Pass --force to embed everything again.

  Input:  data/rule_chunks.json, evals/golden_questions.json, MISTRAL_API_KEY in .env
  Output: data/embeddings/*.npz

Run from the project root:
    uv run python -m scripts.build_embeddings
"""

import argparse
import json
import time

from mistralai.client import Mistral

from app.settings import load_settings
from evals.golden_answer_chunks import QUESTIONS_FILE, load_chunks
from retrieval.stored_embeddings import embeddings_file, load_embeddings, save_embeddings
from retrieval.window_chunks import build_windows


# Constants
## Inputs per request: small enough to stay under the request size limit with 500-token windows
BATCH_SIZE = 16

## Pause between requests, to stay under the API's requests-per-second limit
SECONDS_BETWEEN_REQUESTS = 1.0


# ===== Calling the embedding API in batches =====

def embed_in_batches(client, model, texts, batch_size=BATCH_SIZE, pause_seconds=SECONDS_BETWEEN_REQUESTS):
    """Returns one vector per text, in the same order, sending batch_size texts per request."""
    vectors = []
    for batch_start in range(0, len(texts), batch_size):
        batch = texts[batch_start:batch_start + batch_size]
        response = client.embeddings.create(model=model, inputs=batch)
        for item in response.data:
            vectors.append(item.embedding)

        # Wait before the next request, but not after the last one
        has_more_batches = batch_start + batch_size < len(texts)
        if has_more_batches:
            time.sleep(pause_seconds)
    return vectors


# ===== The sets to embed =====

def texts_to_embed():
    """Returns each set's name, ids and texts."""
    chunks = load_chunks()
    windows = build_windows(chunks)
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    return {
        "clauses_search_text": ([chunk["id"] for chunk in chunks], [chunk["search_text"] for chunk in chunks]),
        "clauses_text": ([chunk["id"] for chunk in chunks], [chunk["text"] for chunk in chunks]),
        "clauses_search_text_with_parents": ([chunk["id"] for chunk in chunks],
                                             [chunk["search_text_with_parents"] for chunk in chunks]),
        "windows": ([window["id"] for window in windows], [window["text"] for window in windows]),
        "questions": ([question["id"] for question in questions], [question["question"] for question in questions]),
    }


def is_already_saved(name, model):
    """True when the set is saved and was made by this model."""
    if not embeddings_file(name).exists():
        return False
    try:
        load_embeddings(name, model)
    except ValueError:
        return False
    return True


# ===== Running every set =====

def main() -> None:
    parser = argparse.ArgumentParser(description="Embed the chunks, windows and golden questions once.")
    parser.add_argument("--force", action="store_true", help="embed every set again, even if already saved")
    arguments = parser.parse_args()

    settings = load_settings()
    model = settings.mistral_embedding_model
    client = Mistral(api_key=settings.mistral_api_key.get_secret_value())

    for name, (ids, texts) in texts_to_embed().items():
        if is_already_saved(name, model) and not arguments.force:
            print(f"{name}: already saved with {model}, skipped")
            continue

        print(f"{name}: embedding {len(texts)} texts with {model}")
        vectors = embed_in_batches(client, model, texts)
        save_embeddings(name, ids, vectors, model)
        print(f"{name}: saved to {embeddings_file(name).name}")


if __name__ == "__main__":
    main()
