"""
Saves and loads embeddings, so every eval run reuses the same vectors and calls no API.

Each set of embeddings is one .npz file in data/embeddings/, holding the ids, the vectors
and the model that made them. Loading checks the model, so vectors from an old model are
never mixed with new ones.

Use:
    save_embeddings("questions", ids, vectors, model)
    vector_by_id = load_embeddings("questions", model)
"""

from pathlib import Path

import numpy


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
EMBEDDINGS_FOLDER = PROJECT_FOLDER / "data" / "embeddings"


# ===== Paths =====

def embeddings_file(name):
    """Returns the file that holds one set of embeddings, such as "questions"."""
    return EMBEDDINGS_FOLDER / f"{name}.npz"


# ===== Saving and loading =====

def save_embeddings(name, ids, vectors, model):
    """Writes the ids, vectors and model name of one set to its .npz file."""
    EMBEDDINGS_FOLDER.mkdir(parents=True, exist_ok=True)
    numpy.savez(
        embeddings_file(name),
        ids=numpy.array(ids),
        vectors=numpy.array(vectors, dtype=numpy.float32),
        model=numpy.array(model),
    )


def load_embeddings(name, model):
    """Returns a dictionary from id to vector for one set, after checking it was made by this model."""
    stored = numpy.load(embeddings_file(name))

    # Vectors from another model live in another space, so they must never be compared
    stored_model = str(stored["model"])
    if stored_model != model:
        raise ValueError(f"{name} was embedded with {stored_model}, not {model}: run scripts.build_embeddings again")

    vector_by_id = {}
    for chunk_id, vector in zip(stored["ids"], stored["vectors"]):
        vector_by_id[str(chunk_id)] = vector
    return vector_by_id
