"""
Loads the refusal probes: no-answer questions outside the golden set, used only to score refusals (Stage 2).

They have the golden questions' shape (answer null, a why_unanswerable and a pass_rule), so the
answer run handles both the same way. Their split is "probe".
"""

import json
from pathlib import Path


# Constants
## Path to each resource
PROBES_FILE = Path(__file__).resolve().parent / "refusal_probes.json"


# ===== Loading =====

def load_refusal_probes() -> list[dict]:
    """Returns every refusal probe."""
    return json.loads(PROBES_FILE.read_text(encoding="utf-8"))["questions"]
