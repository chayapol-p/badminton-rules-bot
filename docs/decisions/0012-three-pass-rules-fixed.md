# 0012 · Fix three pass rules that asked for more than the question or the corpus

- **Status:** Accepted (Job, 8 Nov)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
Reading the failures of the best run (`20261108T0931-top5-links-quote-clause-only`) showed three dev
questions failing on their pass rule, not on the answer:
- **umpire-overrule** asks what the umpire can do. The golden answer added the Instant Review System,
  where a player's challenge replaces the call: a player's action, not the umpire's.
- **service-height-override** asked the bot to say the waist rule "needs prior arrangement". In the
  corpus, "by prior arrangement" covers only the alternative scoring systems, not the service law.
- **best-of-five-change-ends** banned any mention of the standard rule, while answer rule 4 tells the
  bot to give it. The bot answered 6 points first and gave the standard rule in brackets; the judge
  passed every line but the pass rule. best-of-three-interval already allows the standard rule as context.

## Options considered
1. **Keep the pass rules.** The judge keeps failing right answers.
2. **Rewrite each pass rule to what the question asks and the corpus holds.**

## Decision
Option 2:
- umpire-overrule: the umpire's overrule (Law 17.5.1); the review system is context.
- service-height-override: 1.15 m as the default; the waist rule labelled as the Alternative Laws
  (in force 2027-01-04), with both its parts.
- best-of-five-change-ends: 6 points in the fifth game; the standard rule may follow as labelled
  context; 11 points as the answer is a fail.

## Evidence
The best run, re-judged after the first two fixes: 16 to 17 of 22 (umpire-overrule now passes).
best-of-five-change-ends failed only on its pass rule in 3 of 4 runs with an extra answer rule.

## Consequences
- Scores before and after this record aren't comparable; re-judge a saved run to compare.
- Open: answer rule 4 always puts the standard rule first. When a question names a format, the
  format's rule should come first. A prompt change, for its own run.
