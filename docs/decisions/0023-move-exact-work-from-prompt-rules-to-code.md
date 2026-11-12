# 0023 · Move the exact work from prompt rules to code, one change at a time

- **Status:** Proposed (Job, 11 Nov): adopted, each change to be tested on its own
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
To come: one line per change in `workshop/notes.md`. This record moves to Accepted or Rejected per
change once its run is read.

## Consequences
- The earlier Phase 2 item "check quotes, then one fix-up turn listing the bad quotes" is replaced
  by change 3, where a misquote can't happen.
- Each run costs more once the question set grows (about 3 times the dev questions).
