# 0008 · The judge counts facts stated in the question as given

- **Status:** Proposed (re-judge of run 1 still to run)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
The judge matched 8 of 10 hand grades on run 1 (old rubric), below the 9-of-10 bar. One miss:
coaches-at-interval failed `only_from_sources` for "the 11-point interval". The source (ITTO 5.4.13)
says only "in all these intervals (Law 16.2.1)"; the "11-point" came from the user's question. The
code check for numbers already counts the question as shown, so the judge and the code disagreed.

## Options considered
1. **Keep the rule: sources only.** Strict, but fails a reply for repeating the user's own words.
2. **Facts stated in the question count as given.** Matches the code check. Risk: a false premise
   ("at the 15-point break…") can be repeated without being caught.
3. **Option 2, plus checking the premise.** Benchmarks such as FreshQA (Vu et al., 2023) give credit
   on a false-premise question only when the reply points the false premise out. Needs false-premise
   questions in the set first; none exist yet.

## Decision
Option 2. A false premise is a separate behaviour, tested later with its own questions (option 3).

## Evidence
To run: `rescore_answer_run --run 20261107T1639-top5 --rejudge`, then
`compare_judge_with_my_grades --run 20261107T1639-top5 --rejudged`. Accept when coaches-at-interval
agrees with the hand grade and no other grade moves away from it.

## Consequences
- The judge and the number check now treat the question the same way.
- Until false-premise questions are added, a reply that repeats a false premise isn't caught.
