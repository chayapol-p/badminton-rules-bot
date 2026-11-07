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
8. Keep one-line comprehensions and conditions for the obvious cases only: one loop and one simple condition. Anything more (two loops, `and` or `or`, a lookup or call inside the condition) becomes a plain `for` loop with named steps, or a small helper whose name says what it checks. An inline `if … else` inside a call counts too: name the condition first (`is_hit = found_count > 0`), then use it.

```python
# Too much in one line
same_document = [chunk for chunk in chunks if chunk["document"] == location["doc"]
                 and location.get("alternative_format") in (None, chunk["alternative_format"])]

# Readable: a named helper and a plain loop with named steps
candidates = []
for chunk in chunks:
    is_same_document = chunk["document"] == location["doc"]
    if is_same_document and chunk_is_in_location_format(chunk, location):
        candidates.append(chunk)
```

9. Prefer words to symbols: built-in methods and keywords (`set.intersection()`, `issubset()`, `isdisjoint()`, `and`, `or`, `not`, `any()`, `all()`) instead of `&`, `|`, `^`, `~` or `<=` on sets. Bit flags from a library are the one exception: keep the `&` inside a small helper with a clear name, such as `is_italic_span()`. Type hints keep `X | None`.
10. File names say what the file does or holds: `build_rule_chunks.py`, not `ingest.py`; `golden_answer_chunks.py`, not `golden.py`. Python modules stay lowercase with underscores (PEP 8). A test file is named after what it tests: `test_<module>.py`.
11. Test words follow the standard test-double terms (Meszaros; Google's *Software Engineering at Google*): test data copied from the real files is a **sample** (`SAMPLE_CHUNKS`), a function that returns fixed results is a **stub** (`perfect_search`), and a value passed in but never used is a **placeholder** (`"test-mistral-key"`). Say **fake** only for a working stand-in with a shortcut inside (an in-memory database), and **mock** only for an object that records how it was called (`unittest.mock`).
12. Code Job writes himself is marked with the standard `TODO` comment, which editors highlight and list: `# TODO (Stage 1, Step 2): fill the blank, then delete the raise line`. Never "YOUR TURN" or other custom markers.
13. Add nothing the code doesn't need: no guard, conversion or check for a case the real callers never create (`numpy.asarray` on what is already an array). When a function depends on its inputs' types, say so in type hints (`chunk_vectors: numpy.ndarray`), so the editor warns at the call site, not in runtime conversions or comments.

## Experiment rules

1. Change one thing per run, and keep everything else fixed.
2. Fixed settings: temperature 0, a pinned model ID and a frozen corpus (the PDF hashes in `evals/golden_questions.json`).
3. Every run appends one line to `evals/runs.jsonl`: settings, scores, cost and latency.
4. Tune on the dev questions. Score the held-out questions once, for the published number. Never re-split.
5. One dev question is about 4 points of recall. Call a win only at 2 or more questions apart.

## Data rules

1. The ingest output is tested (`tests/test_rule_chunks.py`). After any ingest change, diff `data/rule_chunks.json` against the old file and explain every change.
2. A known bug gets a test marked `xfail(strict=True)` until it is fixed.
3. Raw findings go to `workshop/notes.md`, one line each, with a number.
4. Search reads `search_text` (a context header, then the clause), or `search_text_with_parents` (the header, the parent clauses, then the clause) once Stage 1 shows it helps. Answers quote and cite `text`, the clause as printed.

## Checks before every commit

```bash
uv run pytest -q
uv run python -m scripts.check_golden_questions
```
