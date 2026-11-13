# 0022 · Setup C keeps prompt version 1, with check-each-part and search-before-gaps

- **Status:** Superseded by 0024 (the two agent rules became search steps)
- **Date:** 2026-11-11
- **Stage:** 3 (agent vs plain RAG)

## Context
Two agent rules were tested on setup C one at a time (experiment rule 1), then a reviewed rewrite of
the whole prompt, prompt version 2 (`--prompt-version 2`, commit 32cc641), was tested as one
candidate. Totals moved within the noise floor of about 2 questions every time, so the choice rests
on which failures each prompt brings.

## Options considered
1. **Version 1 with check-each-part and search-before-gaps** (the current best C): unseen 26 of 30,
   dev 19 of 22, $0.042 a question on unseen. Fixes its target: yellow-card-before-play searched 3 of 3. No refusal errors.
2. **Prompt version 2**: unseen 27 of 30, dev 18 of 22, $0.046 a question on unseen. Wins opponent-calls-fault-mid-stroke
   and string-tension, and C's misquotes fall 3 to 0. Loses refusals: 4 missed across A, B and C, each
   a partial answer where a refusal was due; service-height-override drops the Alternative Laws rule
   in A and C; duplicate citations rise (C 0 to 3 of 33).
3. **A version 3** that changes only version 2's refusal rule and special-format rule, then runs again.

## Decision
Option 1. Prompt version 2 is not adopted, so records 0010 and 0015 stay in force.

## Evidence
Run lines in `evals/runs.jsonl` and the findings in `workshop/notes.md` (Lab 3), 9–10 Nov.

## Consequences
- The remaining failures (misquotes, refusals, duplicate citations) go to code in Phase 2, not to
  more prompt rules.
- Version 2 stays in the code as a switch, so its runs can be reproduced.
- To do, in code for Job's review: make the two agent rules setup C's default.
