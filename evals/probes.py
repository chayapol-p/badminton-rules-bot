"""
Loads the probes: questions outside the golden set that test one behaviour each (Stage 2).

  refusal probes        no answer in the corpus: the bot should refuse
  false-premise probes  answerable, but the question assumes something the sources contradict:
                        the bot should correct the premise, then answer
  unseen questions      written after the rule map, never tuned on (Stage 3): each setup is
                        scored on them once, question by question against its "needs" tag
  Phase 2 questions     41 dev questions, 14 of them should be refused (slice 2), for the Phase 2 runs
                        after the measurement restart

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
UNSEEN_QUESTIONS_FILE = EVALS_FOLDER / "unseen_questions.json"
PHASE2_QUESTIONS_FILE = EVALS_FOLDER / "phase2_questions.json"


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


def load_unseen_questions() -> list[dict]:
    """Returns every unseen question (Stage 3)."""
    return json.loads(UNSEEN_QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]


def load_phase2_questions() -> list[dict]:
    """Returns every Phase 2 question (slice 2)."""
    return json.loads(PHASE2_QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
