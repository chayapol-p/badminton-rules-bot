# 0014 · The judge grades what the user sees, by a majority of 3 votes

- **Status:** Accepted (Job, 8 Nov)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
Two runs of one setup moved by 2 of 22, as much as any single fix gained. Part of that was the judge:
- It read the bot's reasoning field. leaving-court failed both combined runs because the reasoning
  named the para clause the answer rightly left out. Users see only the answer and citations.
- One judge call per answer: a borderline answer (attack-be-the-referee) flipped between runs.

## Options considered
1. **One judge call, whole reply.** The setup so far.
2. **Several votes, majority per rubric line:** self-consistency (Wang et al.); resampling over lower
   temperature (Anthropic, "Adding Error Bars to Evals", 2024).
3. **A panel of judges from several model families** (Verga et al., 2024). A second family here would
   be Mistral judging Mistral's own answers, so no.

## Decision
The judge sees refused, the answer and its citations; the reasoning stays in the run log. Each answer
is graded 3 times, and each rubric line goes with the majority.

## Evidence
Seven saved runs re-judged with the new judge (`<run>-rejudged-grades.jsonl`): no question regressed
against the two baseline runs in any of them, where the old judge flagged attack-be-the-referee and
best-of-five-change-ends as regressions.

## Consequences
- Judge cost is 3 times one call: about $0.25 more per run.
- Scores before and after this record aren't comparable; re-judge a saved run to compare.
- Still open: the judge fails racket-max-size for "stringed area", because clause 4.2.2's text has no
  subject (it is in the heading above it). The bot inferred it rightly; the source block doesn't show it.
