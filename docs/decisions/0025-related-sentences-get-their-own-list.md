# 0025 · Related sentences get their own list, and the judge sees them as context

- **Status:** Accepted (Job, 14 Nov)
- **Date:** 2026-11-14
- **Stage:** Phase 2 (productise)

## Context
In the first Phase 2 baseline (14 Nov, hybrid, Phase 2 questions), all 3 refusals the judge failed in slice 4
failed on the related text, not the refusal. Two were service-time-limit: the reply refused correctly, but the
related laws sat in the one citation list, and the judge wrote that they "appear to be used as part of the
answer rather than only as related sentences". RulesAnswer had one list, so neither the judge nor the code
checks could tell an answer's sources from related sentences.

## Options considered
1. **Keep one list.** The judge keeps failing correct refusals whose pass rule allows related sentences.
2. **A separate list, shown to the judge under its own heading.** RulesAnswer gets `related_citations`; the
   judge reads "Citations (the answer's sources)" and "Related sentences (context only, not part of the answer)".

## Decision
Option 2. Both flows put related sentences in `related_citations`; the citation check checks their quotes
too; "an answer cites nothing" counts only the answer's own citations; the judge and the grading kit show
them apart. Run files from before still load (the list is empty by default).

## Consequences
- The judge's input changed, so runs before this change are not compared with runs after it; the 14 Nov
  baseline is rerun (record 0026).
