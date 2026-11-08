# 0007 · Grade with code checks first, and the judge only for what code can't decide

- **Status:** Accepted
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
Run 1 (`20261107T1639-top5`) sent all 33 answers to the Claude Sonnet 5.5 judge, including answers
that code had already shown to be wrong: 4 wrong refusals and 2 quotes not in their clause. A judge
call costs more than an answer call, can vary between calls (Sonnet 5.5 takes no temperature), and
a judge from any model family carries its own bias. Some checks need no judgement at all.

Two number checks were tried on run 1's saved answers:
- **Numbers not in the sources** flagged deuce-end's "22-20". The example is correct, worked out from
  Law 7.4's two-point rule, but code can't tell a worked-out number from one taken from memory.
- **Golden numbers missing from the reply** flagged 11 (best-of-three-interval), 60
  (coaches-at-interval) and 13.4 (doubles-court-size). All three are context numbers in the golden
  answer, not facts the question asks for.

## Options considered
1. **The judge grades everything.** One grader, one rubric. Misses: it pays for and adds noise to
   verdicts code can reach exactly.
2. **Code checks first; the judge grades only the answers they pass.** Anthropic's guide to
   building evals ranks code-based grading as the fastest and most reliable method, and keeps
   LLM-based grading for what needs judgement (docs.claude.com, "Create strong empirical evaluations").
3. **Option 2, with both number checks as fails.** Strict, but would fail deuce-end's correct example
   and three answers whose golden answers hold context numbers.
4. **Option 2, with both number checks as warnings passed to the judge.** The judge sees the flagged
   numbers as hints and decides whether each is worked out, context, or from memory.
5. **Pass-rule fields in the golden set** (must-have and must-not-have terms per question, checked by
   code). Rejected as too complex for now.

## Decision
Option 2 with option 4. Code fails four things: a format error, a wrong refusal (missed or false), a
citation problem, and an answered question citing none of the clauses that hold its answer. Two
number checks only warn, and their warnings go to the judge in a `<code_notes>` block. An answer
passes when the code checks pass and every judge line passes.

## Evidence
Run 1 re-scored with `experiments/rescore_answer_run.py` (code checks rerun, judge verdicts as
saved from the old rubric): 12 of 22 answers passed; 6 of 33 answers fail the code checks (4 wrong
refusals, 2 citation problems), so 27 would go to the judge. Run 2 gives the first score under the
new rubric.

## Consequences
- Fewer judge calls per run, and every code failure has an exact reason for Step 6.
- The judge's number line now leans on its judgement: watch the hand-grade comparison for answers
  where a number from memory passed.
- The wrong-clause check depends on the golden set's answer locations: a wrong location fails a good answer.
