# House rules for this repo

Every coding session in this repo follows these rules, by hand or with an AI coding tool.

## Coding style

Job's coding style has one home: the `writing-readable-code` skill. Load it before writing or reviewing code in this repo, and follow it. This file holds no coding rules of its own, so the style stays the same in every project. To add or change a rule, use the `updating-coding-style` skill.

Only what is specific to this repo:

- Written by hand here, because a reader must understand them to trust the results: rank fusion, the scorers, the citation check, the agent loop, the retry helper and the streaming endpoint. Everything else uses the installed packages (`mistralai`, `rank_bm25`, `numpy`, `httpx`, `pytest`, `fastapi`).
- Job's exercise blanks are marked `# TODO (Stage N, Step M): …`.
- In this repo, instead of deleting the code a change replaces (rule 15), a retired answer flow moves to `experiments/retired_flows/` and stays runnable, because it shows how the experiments were set up. Delete nothing that produced a logged result. Product code (`answer_flows/`, `app/`, `evals/`, `retrieval/`) never imports from `experiments/` (`tests/test_product_imports.py` checks it).

## Experiment rules

1. Change one thing per run, and keep everything else fixed.
2. Fixed settings: temperature 0, a pinned model ID and a frozen corpus (the PDF hashes in `evals/golden_questions.json`).
3. Every run appends one line to `evals/runs.jsonl`: settings, scores, cost and latency.
4. Tune on the dev questions. Score the held-out questions once, for the published number. Never re-split.
5. One dev question is about 4 points of recall. Call a win only at 2 or more questions apart. Phase 2 runs: 3 runs per flow, and a win only when the flows' ranges of scores don't overlap (record 0026).
6. Every decision Job makes gets a record in `docs/decisions/` (MADR format; see its README): the options weighed, the decision and the runs behind it. Claude's suggestions get no record until Job picks one.
7. When a run compares chunkings or search types, run every search type at matched word budgets in the same batch (add them to `experiments/run_all_search_setups.py`), so one batch settles the question.

## Data rules

1. The ingest output is tested (`tests/test_rule_chunks.py`). After any ingest change, diff `data/rule_chunks.json` against the old file and explain every change.
2. A known bug gets a test marked `xfail(strict=True)` until it is fixed.
3. Raw findings go to `workshop/notes.md`, one line each, with a number.
4. Search reads `search_text` (a context header, then the clause), or `search_text_with_parents` (the header, the parent clauses, then the clause) once Stage 1 shows it helps. Answers quote and cite `text`, the clause as printed.

## The app

The web app is built spec-first, one thin slice at a time, with the `co-writing-agile-specs` skill. Load it before any app work.

- **Stack (Job's pick, 14 Nov):** FastAPI back end in `app/`, React front end.
- **Vision and spec:** Job writes the vision in `docs/vision.md`. The one-screen spec lives in `docs/specs/`, next to the code. Detail only the next slice.
- **The only way in:** the app answers through `load_rules_bot()` and `RulesBot.answer(question, report_progress=...)` in `answer_flows/rules_bot.py`. It never calls the flow's inner functions and never imports from `experiments/`.
- **The wait (record 0028):** an answer takes 9–104 s. While it works, the flow sends `ProgressUpdate`s (`answer_flows/shared/progress_updates.py`): the steps in plain words, then the quoted sources early, then "still writing · N s" every 5 s during the write call. Those last updates come from a second thread, so `report_progress` must be safe to call from another thread. Show the answer only once it arrives whole. An `AnswerFormatError` is shown as an error, never as an empty answer.
- **The answer (record 0027):** `answer_sentences` holds the answer with `[n]` markers; marker `[n]` is `citations[n - 1]` (its quote and source name).
- **Tests never call a paid API:** app tests use a stub bot that returns a fixed, correctly shaped answer. A live check calls Mistral once, by hand, on Job's Mac.

## Checks before every commit

```bash
uv run pytest -q
uv run python -m scripts.check_golden_questions
```
