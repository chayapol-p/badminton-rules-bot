# 0008 · Facts in the question count as given; a false premise is corrected, then answered

- **Status:** Proposed (needs the new baseline run and the re-judge)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
The judge matched 8 of 10 hand grades on run 1 (old rubric), below the 9-of-10 bar. One miss:
coaches-at-interval failed `only_from_sources` for "the 11-point interval". The source (ITTO 5.4.13)
says only "in all these intervals (Law 16.2.1)"; the "11-point" came from the user's question. The
code check for numbers already counts the question as shown, so the judge and the code disagreed.

Counting the question as given opens a gap: a question with a false premise ("at the 15-point
break…") could be repeated back without being caught. The answer prompt also told the bot to refuse
anything that asks it to "confirm something the sources contradict", so an honest correction would
have scored as a false refusal.

## Options considered
1. **Keep the rule: sources only.** Strict, but fails a reply for repeating the user's own words.
2. **Facts stated in the question count as given.** Matches the code check, but leaves the gap.
3. **Option 2, plus premise checks.** FreshQA (Vu et al., 2023) gives credit on a false-premise
   question only when the reply points the false premise out, and finds models catch more false
   premises when told to check the premise first. Needs a prompt rule and false-premise questions.

## Decision
Option 3:
- Judge rule 2: a fact stated in the question counts as given, unless the sources contradict it.
- Answer rule 7: check what the question assumes; when the sources contradict it, say so, give the
  sources' version, then answer. That is an answer, not a refusal. Rule 6 still refuses attacks
  (ignore your rules, rule on an event you didn't see).
- Three false-premise probes (`evals/false_premise_probes.json`): two wrong numbers and one rule that
  doesn't exist. Scored on their own line, never in the answer pass rate.

## Evidence
To run, in order: `scripts.build_embeddings` (embeds the 3 new probes), a new top-5 baseline (the
prompt changed, so run 1 is no longer the same setup), its repeat, then `compare_judge_with_my_grades`.
Accept when the judge matches 9 of 10 hand grades or better and the false-premise probes score on
their own line.

Run 1 re-judged with the new rubric (8 Nov): the judge still failed coaches-at-interval, now for the
link "11-point interval = Law 16.2.1". Law 16.2.1 wasn't among the bot's 5 sources, so the link came
from memory. Job flipped his hand grade to fail: the judge matches 10 of 10. This case can't show the
rule change helps; the false-premise probes will.

## Consequences
- The judge and the number check now treat the question the same way.
- Run 1 is no longer comparable: the baseline for top_k (record 0009) is the new top-5 run.
- 3 probes is a smoke test, not a rate: one probe moves the score by 33 points.
