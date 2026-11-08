# 0015 · List items, the para rule and the value-conditions rule become the default

- **Status:** Accepted (by Job's target-question rule, 8 Nov)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
With 22 scored questions a run moves by about 2 on its own, so no single fix could win by 2 questions
(experiment rule 5). Job set the rule for this stage: judge a fix on its target questions across runs,
check every other question for regressions, and integrate the fixes that win.

## Options considered
1. **List items:** when search finds a list heading ("in Wheelchair Badminton if the shuttle is:"), add
   the items under it. Target: wheelchair-shuttle-on-net.
2. **Answer rule 9:** mention a Para Badminton rule only when the question is about para play.
   Target: leaving-court. A first wording ("Answer with the standard rules…") also pushed the standard
   rule into an Alternative Laws question and was dropped.
3. **Answer rule 10:** state a condition together with its value. Targets: post-height,
   service-height-override.

## Decision
All three, as the default setup.

## Evidence
Re-judged with the judge of record 0014; baseline `20261108T0931-top5-links-quote-clause-only` and
`20261108T1129-top5-cap16k` (15 and 17 of 22):

| Fix | Target questions passed (baseline, with fix) | Regressions |
|---|---|---|
| list items | wheelchair 0 of 2, 1 of 1 | none |
| para rule | leaving-court 0 of 2, 1 of 1 | none |
| value conditions | post-height 0 of 2, 1 of 1; service-height 0 of 2, 1 of 1 | none |
| all three (2 runs) | wheelchair 2 of 2, leaving-court 2 of 2, post-height 1 of 2, service-height 0 of 2 | none |

All three together: 18 and 20 of 22, against 15 and 17.

## Consequences
- The default command, `uv run python -m experiments.compare_answer_setups --top-k 5`, now holds all three.
- service-height-override still leaves out "racket shaft and head pointing downward" in most runs.
