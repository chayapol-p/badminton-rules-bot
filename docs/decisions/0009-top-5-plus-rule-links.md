# 0009 · Keep top_k at 5, and add the clauses the hits link to

- **Status:** Accepted (by experiment rule 5; Job delegated the runs on 8 Nov)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
Run 1 and the new baseline lost every cross-reference question (0 of 4): a clause in the top 5
named another clause ("Law 16.2.1", "Law 16.7") that never reached the model. Stage 1 left
`top_k` open: recall@5 was 0.840, against 0.979 at about 1,550 words.

## Options considered
1. **Top 5 alone.** The baseline: 12 and 12 of 22 on two runs.
2. **Top 5 plus rule links** (`retrieval/expand_with_rule_links.py`, one hop, no neighbours): adds
   cited clauses, alternatives and para exceptions. On run 1's saved sources it found the missing
   clause for 5 of 7 questions, for 61 more words per question.
3. **More of the search's own results: top 15 or top 55,** with rule links.

## Decision
Option 2: top 5 plus rule links. It beats top 5 alone by 2 questions, and more results add cost
without passes.

## Evidence
All dev questions plus 9 probes, quote rule on (record 0010), answer pass rate of 22:

| Run | Passed | Words | Cost/question |
|---|---|---|---|
| `20261108T0921-top5-quote-clause-only` | 14 | 157 | $0.0101 |
| `20261108T0931-top5-links-quote-clause-only` | 16 | 217 | $0.0112 |
| `20261108T1000-top15-links-quote-clause-only` | 16 | 583 | $0.0150 |
| `20261108T1010-top55-links-quote-clause-only` | 15 | 1,827 | $0.0279 |

Rule links also took cross references from 1 to 2 of 4 and false premises from 2 to 3 of 3.
The noise floor: the baseline and its repeat both passed 12, with 4 questions changing places.

## Consequences
- Every run now adds the rule links; `--top-k` sets the search hits before they are added.
- 4 of the 6 text fails left in the winning run had their answer clauses in the sources (post-height,
  red-card, umpire-overrule, leaving-court): the next gains are mostly in the answer, not retrieval.
- Experiment rule 7 (matched word budgets) was not applied: links are a retrieve step on top of one
  search type, not a new search type.
