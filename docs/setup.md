# Setup: run the real bot

The [README](../README.md#try-it) shows how to run the chat with the stub bot, at no cost. This page adds the real bot: the rule books, the build steps, the checks and the tests.

Needs [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 and the packages) and Node.js for the chat page.

## 1. Keys

```bash
cp .env.example .env
```

- `MISTRAL_API_KEY`: required. Answers, embeddings and the topic check all run on Mistral.
- `ANTHROPIC_API_KEY`: optional. Only the answer judge and the experiment runs need it.
- `RULES_BOT=real`: switches `/chat` from the stub to the real bot. Each question then costs about $0.04.

`.env` is in `.gitignore`, so the keys never reach git.

## 2. The rule books

The PDFs belong to BWF and are never committed. One script downloads the three books into `data/bwf/` and checks each against the hash the results were measured on:

```bash
uv sync
uv run python -m scripts.download_rule_books   # prints "<file>: downloaded and checked" for each book
```

If BWF has published a new version, the hash differs and the script stops without saving it: every chunk, test and score assumes the frozen version.

## 3. Build and check the chunks

```bash
uv run python -m scripts.build_rule_chunks       # writes data/rule_chunks.json
uv run python -m scripts.build_rule_links        # writes data/rule_links.json
uv run python -m scripts.build_embeddings        # writes data/embeddings/*.npz (calls Mistral)
uv run python -m scripts.check_golden_questions  # every answer location found?
```

When it works, the check prints `golden questions: 39 | duplicate ids: 0` and `phase2 questions: 41 | duplicate ids: 0`, each followed by `missing locations: none`, and ends with `in both sets: none`.

These checks call no API; the last two read the saved vectors:

```bash
uv run python -m scripts.check_rule_links        # which multi-clause questions one hit plus the map solves
uv run python -m scripts.check_unseen_questions  # each unseen question's tag against vector search
uv run python -m scripts.check_refusal_probes    # no clause answers a refusal probe
```

## 4. Start the server and the chat page

```bash
uv run uvicorn app.main:app --reload        # FastAPI on http://127.0.0.1:8000 (try /health)
cd frontend && npm install && npm run dev   # the chat page on http://localhost:5173
```

The page talks only to Vite on port 5173, and Vite passes `/chat` and `/rule-books` on to FastAPI on port 8000. The PDF links work once the rule books are in `data/bwf/`.

## 5. Tests

```bash
uv run pytest -q                 # the Python tests, no API calls, no network
cd frontend && npm test          # the page tests
cd frontend && npm run test:e2e  # the browser tests, on their own stub servers (ports 8001 and 5174)
```

No test calls a paid API.

## 6. Experiments

House rules for runs are in [`CLAUDE.md`](../CLAUDE.md) ("Experiment rules"): one change per run, fixed settings, every run logged to `evals/runs.jsonl`, and 3 runs per flow before calling a win.

```bash
uv run python -m experiments.run_answer_experiment --setup hybrid --phase2 --parallel 4
uv run python -m experiments.compare_flow_runs --flow-a <name> <run> <run> <run> --flow-b <name> <run> <run> <run>
```

A 41-question run takes about 6 minutes at `--parallel 4`, and grading needs `ANTHROPIC_API_KEY`.
