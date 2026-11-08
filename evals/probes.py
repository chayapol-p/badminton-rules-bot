"""
Loads the probes: questions outside the golden set that test one behaviour each (Stage 2).

  refusal probes        no answer in the corpus: the bot should refuse
  false-premise probes  answerable, but the question assumes something the sources contradict:
                        the bot should correct the premise, then answer

Both have the golden questions' shape, so the answer run handles them the same way. Their split is
"probe", and the run scores them on their own lines, never in the answer pass rate.
"""

import json
from pathlib import Path


# Constants
## Path to each resource
EVALS_FOLDER = Path(__file__).resolve().parent
REFUSAL_PROBES_FILE = EVALS_FOLDER / "refusal_probes.json"
FALSE_PREMISE_PROBES_FILE = EVALS_FOLDER / "false_premise_probes.json"


# ===== Loading =====

def load_refusal_probes() -> list[dict]:
    """Returns every refusal probe."""
    return json.loads(REFUSAL_PROBES_FILE.read_text(encoding="utf-8"))["questions"]


def load_false_premise_probes() -> list[dict]:
    """Returns every false-premise probe."""
    return json.loads(FALSE_PREMISE_PROBES_FILE.read_text(encoding="utf-8"))["questions"]


def load_probes() -> list[dict]:
    """Returns every probe: the refusal probes, then the false-premise probes."""
    return load_refusal_probes() + load_false_premise_probes()
