# 0026 · Call a win with 3 runs per flow and a gap bigger than the noise

- **Status:** Accepted (Job, 14 Nov)
- **Date:** 2026-11-14
- **Stage:** Phase 2 (productise)

## Context
Two identical slice 4 runs on the Phase 2 questions (14 Nov) differed on 10 of 41 questions and by 4 overall
(31/41 and 35/41). Slice 5 scored 37/41, inside that noise. Experiment rule 5 (a win at 2 or more questions
apart) was set on the golden dev set in Stage 1 and is too tight for this set.

## Options considered
1. **Keep rule 5.** Slice 5 would count as a win on a gap the same flow shows between two of its own runs.
2. **More runs per flow, and a gap bigger than the noise.**
3. **A bigger question set.** More questions to write and review before any comparison.

## Decision
Option 2: every flow under comparison runs 3 times on the same questions, and a win is called only when the
gap between flows is bigger than the noise. Noise is the spread between runs of the same flow, so a win
needs the flows' ranges of overall scores not to overlap (Job confirmed this reading, 15 Nov). Example: 31, 33, 35
against 36, 37, 38 is a win; 34, 37, 38 against 31, 33, 35 is not.

## Evidence
14 Nov repeat runs (hybrid, Phase 2 questions): slice 4 scored 36, 37, 36 and slice 5 scored 37, 38, 37. The
ranges touch at 37, so no win.

## Consequences
- A comparison of two flows costs about 6 runs (about $10.50 and 2 hours on hybrid with the Phase 2 questions).
- Experiment rule 5 in CLAUDE.md points here for the Phase 2 runs.
