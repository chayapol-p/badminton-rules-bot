"""
Appends one line per eval run to evals/runs.jsonl, so every result stays comparable.

Each line holds the time, the stage, the settings that changed, the scores and how long
the run took. Misses stay out of the log; print them when you need them.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


# Constants
## Path to each resource
RUNS_FILE = Path(__file__).resolve().parent / "runs.jsonl"


# ===== Writing one run =====

def append_run(stage, settings, scores, seconds):
    """Adds one run to the log: its stage, settings, scores (without misses) and duration."""
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": stage,
        "settings": settings,
        "scores": {name: value for name, value in scores.items() if name != "misses"},
        "seconds": round(seconds, 2),
    }
    with RUNS_FILE.open("a", encoding="utf-8") as runs_file:
        runs_file.write(json.dumps(record) + "\n")
