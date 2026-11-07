"""
Embeds the chunks, the windows, the golden questions and the refusal probes with mistral-embed, once, and saves them.

Seven sets, each saved to data/embeddings/<name>.npz:
  clauses_search_text  each clause chunk's search_text (context header, then the clause)
  clauses_text         each clause chunk's text alone, for the context header comparison
  clauses_search_text_with_parents   the header, the parent clauses, then the clause
  windows              each fixed-size window's text
  section_groups       each section group's search_text (context header, then its clauses)
  questions            each golden question, keyed by its id
  refusal_probes       each refusal probe (Stage 2), keyed by its id

A set that is already saved with the same model is skipped, so a rerun costs nothing.
Pass --force to embed everything again.

  Input:  data/rule_chunks.json, evals/golden_questions.json, evals/refusal_probes.json, MISTRAL_API_KEY in .env
  Output: data/embeddings/*.npz

Run from the project root:
    uv run python -m scripts.build_embeddings
"""

import argparse
import itertools
import json
import math
import time

from mistralai.client import Mistral
from tqdm import tqdm

from app.settings import load_settings
from evals.golden_answer_chunks import QUESTIONS_FILE, load_chunks
from evals.refusal_probes import load_refusal_probes
from retrieval.stored_embeddings import embeddings_file, load_embeddings, save_embeddings
from retrieval.section_groups import build_section_groups
from retrieval.window_chunks import build_windows


# Constants
## Inputs per request: small enough to stay under the request size limit with 500-token windows
BATCH_SIZE = 16

## Pause between requests, to stay under the API's requests-per-second limit
SECONDS_BETWEEN_REQUESTS = 1.0


# ===== Calling the embedding API in batches =====

def embed_in_batches(client: Mistral, model: str, embedding_inputs: list[str], progress_label: str,
                     batch_size: int = BATCH_SIZE, pause_seconds: float = SECONDS_BETWEEN_REQUESTS) -> list[list[float]]:
    """Returns one vector per embedding input, in the same order, sending batch_size inputs per request."""
    vectors = []

    # Show a progress bar, because a set takes up to a minute
    batch_count = math.ceil(len(embedding_inputs) / batch_size)
    progress_bar = tqdm(itertools.batched(embedding_inputs, batch_size), total=batch_count,
                        desc=progress_label, unit="batch")

    for batch_number, batch in enumerate(progress_bar):

        # Wait between requests, to stay under the rate limit; the first request goes right away
        is_first_batch = batch_number == 0
        if not is_first_batch:
            time.sleep(pause_seconds)

        # batched gives tuples, and the API takes a list
        response = client.embeddings.create(model=model, inputs=list(batch))
        for item in response.data:
            vectors.append(item.embedding)
    return vectors


# ===== The sets to embed =====

def build_embedding_inputs_by_set() -> dict[str, tuple[list[str], list[str]]]:
    """Returns each set's name, with its ids and embedding inputs."""

    # Load the sources; read the questions file directly, because load_questions keeps one split and every split needs a vector
    chunks = load_chunks()
    windows = build_windows(chunks)
    section_groups = build_section_groups(chunks)
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    probes = load_refusal_probes()

    # Collect the ids, shared by the three clause sets
    chunk_ids = [chunk["id"] for chunk in chunks]
    window_ids = [window["id"] for window in windows]
    section_group_ids = [group["id"] for group in section_groups]
    question_ids = [question["id"] for question in questions]
    probe_ids = [probe["id"] for probe in probes]

    # Pair each set's ids with the text it embeds
    return {
        "clauses_search_text": (chunk_ids, [chunk["search_text"] for chunk in chunks]),
        "clauses_text": (chunk_ids, [chunk["text"] for chunk in chunks]),
        "clauses_search_text_with_parents": (chunk_ids, [chunk["search_text_with_parents"] for chunk in chunks]),
        "windows": (window_ids, [window["text"] for window in windows]),
        "section_groups": (section_group_ids, [group["search_text"] for group in section_groups]),
        "questions": (question_ids, [question["question"] for question in questions]),
        "refusal_probes": (probe_ids, [probe["question"] for probe in probes]),
    }


def is_already_saved(name: str, model: str) -> bool:
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
    """Embeds every set that isn't saved yet, or every set with --force."""
    parser = argparse.ArgumentParser(description="Embed the chunks, windows, section groups, golden questions and refusal probes once.")
    parser.add_argument("--force", action="store_true", help="embed every set again, even if already saved")
    arguments = parser.parse_args()

    settings = load_settings()
    model = settings.mistral_embedding_model
    client = Mistral(api_key=settings.mistral_api_key.get_secret_value())

    for name, (ids, embedding_inputs) in build_embedding_inputs_by_set().items():
        if is_already_saved(name, model) and not arguments.force:
            print(f"{name}: already saved with {model}, skipped")
            continue

        print(f"{name}: embedding {len(embedding_inputs)} inputs with {model}")
        vectors = embed_in_batches(client, model, embedding_inputs, progress_label=name)
        save_embeddings(name, ids, vectors, model)
        print(f"{name}: saved to {embeddings_file(name).name}")


if __name__ == "__main__":
    main()
