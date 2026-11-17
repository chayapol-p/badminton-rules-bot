# Slice 1 spec — POST /chat backed by a stub

Status: approved (decisions below). Branch: `vibe/chat-stub-41f4ed`, PR to `main`.

## Goal
One thin slice: the FastAPI app accepts a badminton rules question at `POST /chat`
and returns a **correctly shaped answer** — answer text with inline `[n]` markers
plus a numbered source list — from a **stub**, with no model calls and no `data/`.
This fixes the wire contract the React UI (slice 2) will consume.

## In scope
- `POST /chat` endpoint on the existing app (`app/main.py`).
- A stub answer function at `app/stub/answer.py`, called by the route, returning a
  fixed, deterministic, correctly shaped answer for any question.
- Request validation and tests.

## Out of scope
- Any real retrieval or model call; `answer_flows/`, `evals/`, `experiments/`,
  `docs/decisions/` untouched.
- React frontend, streaming, conversation history, auth.
- Changes to settings/startup behavior (keys still validated at startup as today).

## API contract
- **Request:** `POST /chat` with JSON `{"question": "<string>"}`. Missing, empty or
  whitespace-only question → `422`.
- **Response `200`:**
  ```json
  {
    "answer": "A serve is legal only while the whole shuttle is below 1.15 m from the surface of the court [1]. The posts stand 1.55 m high [2].",
    "sources": [
      {"cite_no": 1, "chunk_id": "laws-9.1.4", "quote": "…", "source_name": "Laws of Badminton 5.0 (2), Clause 9.1.4"},
      {"cite_no": 2, "chunk_id": "laws-1.4", "quote": "…", "source_name": "Laws of Badminton 5.0 (2), Clause 1.4"}
    ]
  }
  ```
  Invariant: every `[n]` in `answer` has `1 <= n <= len(sources)`, and every source
  is referenced at least once.

## Implementation shape
- `app/chat.py` (new): request/response models (`ChatRequest`, `SourceEntry`,
  `ChatReply`) and the router. Wire models live here, not in `answer_flows/` —
  serving code stays decoupled from flow internals.
- `app/stub/answer.py` (new): `stub_answer(question: str) -> ChatReply` returning one
  canned `ChatReply`.
- The route calls one function — the swap point: the stub today, the real answer
  flow later at that single call site (mapping `RulesAnswer` → `ChatReply` happens
  there).
- `app/main.py`: mount the chat router next to `/health`.

## Tests (`tests/test_chat.py`, new)
- Stubbed `/chat` returns 200 with the contract shape; all `[n]` markers resolve into
  `sources`; `cite_no` runs 1..len(sources) and every source is cited.
- Missing / empty / whitespace question → 422.
- `/health` still answers (regression).
- Placeholder env keys, same pattern as `tests/test_settings_and_health.py`; no real
  keys, no network.

## Verification before PR
- `uv run pytest -q` — real output pasted into the PR description.
- `uv run python -m scripts.check_golden_questions` cannot run here (needs `data/`,
  not in git) — stated in the PR description.

## Decisions (made by the project owner)
1. Source field is `cite_no`, not `n`.
2. Stub lives at `app/stub/answer.py`.
3. Swap point: the route calls one `answer(question) -> ChatReply` function.
4. This spec is saved to `docs/specs/slice-1-chat-stub.md`.
5. Scope as listed above — approved.
