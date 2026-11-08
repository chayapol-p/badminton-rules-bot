"""
Where answer runs and hand grades are saved, and how their JSON Lines files are read and written.

One home for the paths, so the run script, the re-score, the grading kit and the comparison
always read and write the same files.
  evals/answer_runs/<run>-answers.jsonl           per question: the sources, the answer and the code checks
  evals/answer_runs/<run>-grades.jsonl            per question: the judge's grade, or none when code failed it
  evals/answer_runs/<run>-rejudged-grades.jsonl   the same, graded again with the current rubric
  evals/human_grades.jsonl                        your own grades, one line per answer
"""

import json
from pathlib import Path


# Constants
## Path to each resource
EVALS_FOLDER = Path(__file__).resolve().parent
ANSWER_RUNS_FOLDER = EVALS_FOLDER / "answer_runs"
HUMAN_GRADES_FILE = EVALS_FOLDER / "human_grades.jsonl"


# ===== Reading and writing JSON Lines =====

def read_lines(path: Path) -> list[dict]:
    """Returns one dictionary per non-empty line of a JSON Lines file."""
    lines = []
    for text_line in path.read_text(encoding="utf-8").splitlines():
        if text_line.strip():
            lines.append(json.loads(text_line))
    return lines


def append_line(path: Path, line: dict) -> None:
    """Adds one JSON object as the last line of the file, which is saved when the file closes."""
    with path.open("a", encoding="utf-8") as output_file:
        output_file.write(json.dumps(line, ensure_ascii=False) + "\n")
