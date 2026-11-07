# House rules for this repo

Every coding session in this repo follows these rules, by hand or with an AI coding tool.

## Coding style

1. Start each file and function with what the code is going to do. Comment any part that isn't straightforward.
2. Split code into groups by what they do. Put a comment above each group, and leave a blank line between groups.
3. No abbreviations when a word can be spelled out: `row`, not `r`; `fixture`, not `fx`. Short names that are normal in readable code are fine, such as `i` for a loop index.
4. Names say what they hold, and function names say exactly what they do. A variable that holds an index is never named like an item.
5. Write Pythonic loops: `for` over items, with `enumerate` when an index is needed, never `while` with index arithmetic.
6. Use the packages a real team would install (`mistralai`, `rank_bm25`, `numpy`, `httpx`, `pytest`, `fastapi`). Write by hand only what a reader must understand to trust the results: rank fusion, the scorers, the citation check, the agent loop, the retry helper and the streaming endpoint.
7. Keys live in `.env` and are never written in code.

## Experiment rules

1. Change one thing per run, and keep everything else fixed.
2. Fixed settings: temperature 0, a pinned model ID and a frozen corpus (the PDF hashes in `evals/golden_questions.json`).
3. Every run appends one line to `evals/runs.jsonl`: settings, scores, cost and latency.
4. Tune on the dev questions. Score the held-out questions once, for the published number. Never re-split.
5. One dev question is about 4 points of recall. Call a win only at 2 or more questions apart.

## Data rules

1. The ingest output is tested (`tests/test_chunks.py`). After any ingest change, diff `data/rule_chunks.json` against the old file and explain every change.
2. A known bug gets a test marked `xfail(strict=True)` until it is fixed.
3. Raw findings go to `workshop/notes.md`, one line each, with a number.

## Checks before every commit

```bash
uv run pytest -q
uv run python -m scripts.check_golden_questions
```
