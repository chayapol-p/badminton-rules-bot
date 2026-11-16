# 0023 · Move the exact work from prompt rules to code, one change at a time

- **Status:** Accepted (Job, 16 Nov) for changes 1–4 and 6; change 5 is not built yet
- **Date:** 2026-11-11
- **Stage:** Phase 2 (productise)

## Context
Four rounds of prompt rules in Stage 3 moved totals by no more than the noise of about 2 questions
(record 0022). The failures left are of a kind code can settle exactly: misquotes (about 1 answer in
30), refusals that flip between runs on the same evidence, duplicate citations, and clauses the
retrieve step never brings. Setup C makes one model call do five jobs: find the parts, search,
decide to refuse, write, and copy quotes.

## Options considered
1. **More prompt rules.** Cheapest, but four rounds showed no gain beyond noise, and a rewrite
   (prompt version 2) moved failures around rather than removing them.
2. **A stronger model.** Not tested. Fails at random edges, not the same way every run, which a
   stronger model narrows but doesn't remove.
3. **Move each exact job to code, in six changes** (published practice in brackets):
   1. A bigger question set, so a change can be seen above the noise (Anthropic: volume over hand-grading).
   2. Split the one call into a gather call and a write call (Anthropic: prompt chaining with gates).
   3. Cite a sentence by number and let code fill in the quote (Anthropic Citations API).
   4. Code decides a refusal from the gather call's list of parts and chunks (Corrective RAG).
   5. Run the code checks on every answer, with one fix-up turn (Anthropic: evaluator-optimizer).
   6. The rule map brings a list item's own items (grandchildren).

## Decision
Option 3, all six changes. Each is tested on its own (experiment rule 1).

## Evidence
From `workshop/notes.md` and the 9 Phase 2 runs in `evals/runs.jsonl` (stage "phase2", 14 Nov).
Changes 2–4 were built before the first Phase 2 run, so they were measured together, not one by one.

1. **Bigger question set:** `evals/phase2_questions.json`, 41 questions (27 answerable, 14 should refuse).
   With it, two identical runs differ by 1 overall once related sentences have their own list (record 0025).
2. **Gather call and write call (slice 5):** 37, 38 and 37 of 41, against slice 4's 36, 37 and 36. The
   ranges touch at 37, so no win under record 0026; slice 5 costs 6% more. Chosen as the product flow
   (Job, 14 Nov) on its design: it refused every should-refuse question in all 3 runs, and its related
   text is quoted by code.
3. **Code fills in each quote:** 0 citation problems in all 9 runs (369 answers). Before, about 1 answer in
   30 misquoted.
4. **Code decides the refusal:** 0 false refusals in all 9 runs; 1 missed refusal in 126 should-refuse
   answers (slice 4, service-time-limit), none in slice 5.
5. **Code checks with one fix-up turn:** not built.
6. **A list item's own items:** setup A's retrieve on the unseen questions misses 9 → 6 needed clauses
   (offline check, 12–13 Nov); no clause added to any dev question.

## Consequences
- The earlier Phase 2 item "check quotes, then one fix-up turn listing the bad quotes" is replaced
  by change 3, where a misquote can't happen.
- Each run costs more once the question set grows (about 3 times the dev questions).

## Change 2 (slice 5): Job's design picks, 13 Nov
- The write call's input is clean: the question and every part, an unanswered part marked NO SOURCE, an
  answered part with its picked sentences under their label and Under: line. No handoff note in this
  change; a structured handoff note is its own experiment after it.
- The gate is code only: refuse when no part has a valid sentence. A per-part support check is added
  only if missed refusals remain.
- A bad pick (a clause not shown in full, or no such sentence) counts as no sentence, and is recorded
  by name in the run file, so bad picks are counted apart from false refusals.
- A refusal's related text is a sentence quoted by code, not a model-written note.
- Built before slice 2's bigger question set; its paid run waits for that set and the branch review.
