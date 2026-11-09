# 0018 · Fix two labels in the unseen set after setup A's run

- **Status:** Accepted (Job, 9 Nov)
- **Date:** 2026-11-09
- **Stage:** 3 (agent vs plain RAG)

## Context
Setup A's first run on the 11 unseen questions (`20261109T0716-top5-unseen`) showed two labels that
were wrong about the rule books, not about the bot:
- line-judge-unsighted: the bot cited ITTO 5.8.3 ("if a Line Judge is unsighted, the Umpire shall
  immediately call"), which holds part of the answer but was missing from its answer locations, so the
  "wrong clause" code check failed it.
- every-let-situation, tagged "needs map": the map brings Law 14.2.3, but only its stem ("the shuttle
  is:"). The net cases are its own items, 14.2.3.1 and 14.2.3.2, which the map never brings.

## Options considered
1. **Leave both as they are.** Keeps the set frozen, but scores a right citation as a fail and tags a
   question by what it doesn't need.
2. **Fix both labels:** add ITTO 5.8.3 as an answer location, and retag every-let-situation as "needs
   map and tool".

## Decision
Option 2. Both fixes describe the rule books more truly; neither changes a question, an answer rule or
the bot. Experiment rule 4 (never tune on a scored set) is about changing the system, not correcting
the test, and every setup is scored on the fixed labels.

## Evidence
`20261109T0716-top5-unseen`: line-judge-unsighted failed "wrong clause" citing ITTO 5.8.3;
every-let-situation's answer said Law 14.2.3's text stops at "the shuttle is:".

## Consequences
- The spread is now: search only 4, map 1, tool 3, map and tool 2, no answer 1.
- Setup A's run is re-scored with the code checks (no API calls); the judge's saved verdicts stand.
