# Studio deployment spec — the stub app as a Mistral App

Status: draft for owner review. Branch: `vibe/studio-app-228537`, PR to `main`.

## Story
As the repo owner, I want our simple app (the `POST /chat` stub from slice 1) running
in Mistral Studio, so it is reachable at a Studio URL and answers questions there.

## Criteria
- Given this branch is pushed to `origin`, when the owner runs `mistral login` then
  `mistral deploy` from the repo root on their Mac, then Studio builds the pushed
  commit and the app's `production` environment serves the `api` module.
- Given the app is deployed, when I call `GET /health` on the app URL, then it
  returns `200` with `{"status": "ok", ...}`.
- Given the app is deployed, when I `POST /chat` with `{"question": "..."}`, then it
  returns `200` with the slice-1 wire shape (answer with `[n]` markers + sources).
- Given the repo root, when I run `mistral apps modules`, then it lists the `api`
  module (python, server, route `/`).

## Contract (files this slice adds)
- `apps.json` (repo root): one module `api`, path `.`, route `/`, port 3000,
  runtime python, built from `deploy/docker/Dockerfile.api`, started with
  `uv run uvicorn app.main:app`.
- `deploy/docker/Dockerfile.api`: python:3.12-slim + uv image; syncs the repo's
  `uv.lock` and runs uvicorn on `$HOST:$PORT`; health check hits `/health`.
- `.dockerignore`: keeps `.git`, venvs, caches, `.env*`, and non-runtime folders
  out of the build context.

## Out of scope
- React frontend, the real answer flow, `data/`, publishing to the Vibe catalog.
- No changes to `app/`, `answer_flows/`, `evals/`, `experiments/`, `docs/decisions/`.

## Open questions
- Secrets: the app validates `MISTRAL_API_KEY` and `ANTHROPIC_API_KEY` at startup.
  The owner sets both in the app's **Secrets** tab in Studio; placeholder values
  suffice while the stub makes no model calls.

## How we test
- In the sandbox: `uv run pytest -q` and `mistral apps modules` (real output in the
  PR description).
- The deploy itself is owner-checked with their own login on their Mac (exact steps
  in the PR description); the agent then verifies the deployed app with the Studio
  Apps tools (`list_apps`, `get_app`, deploy runs, logs).

## Slice list
1. (this PR) Deploy config at the repo root + first deploy of the stub app.

## Decisions (owner to confirm)
- One python module named `api` at the repo root; no web/worker/database modules —
  the stub needs none.
- Public route `/`, so the app answers at `/chat` and `/health` directly.
- Port 3000 inside the container, matching the scaffold's convention.
