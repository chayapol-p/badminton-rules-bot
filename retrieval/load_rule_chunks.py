"""
Loads the clause chunks the ingest step writes (scripts/build_rule_chunks.py), for the bot, the evals and the scripts.

Use:
    chunks = load_chunks()
"""

import json
from pathlib import Path


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"


# ===== Loading =====

def load_chunks() -> list[dict]:
    """Returns every clause chunk from the ingest step."""
    return json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
