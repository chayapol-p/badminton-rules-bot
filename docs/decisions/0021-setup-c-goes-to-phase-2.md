# 0021 · Setup C (RAG first, then tools) goes forward to Phase 2

- **Status:** Accepted (Job, 11 Nov)
- **Date:** 2026-11-11
- **Stage:** 3 (agent vs plain RAG)

## Context
Stage 3 asked whether an agent earns its cost. Three setups answered the same questions with the
same model, answer rules, code checks and judge; only where the sources come from changed.

## Options considered
1. **A · plain RAG** (`experiments/compare_answer_setups.py`): vector top 5, rule links and list
   items, one answer call. Cheapest, but it can't fetch a clause the first search missed.
2. **B · agent only** (`compare_agent_setups.py --setup agentic`): the question alone, then
   `search_rules` and `read_clause`, round limit 10 (record 0020). Most flexible, reads the most.
3. **C · RAG first, then tools** (`--setup hybrid`): A's sources plus the same tools.

## Decision
Option 3, setup C.

## Evidence
Unseen set, 11 questions, 3 runs per setup (9 Nov, before any tuning on it):
- A 17 of 30 answers ($0.030 a question); C 26 of 30 ($0.037, 0.88 tool rounds); B 22 of 30
  ($0.056, 2.88 rounds).
- By what each question needs (record 0019), A/C/B: map and tool 0/7/7 of 9, search only 11/11/8 of 12.
- Job's prediction (9 Nov) held on all three checks: C passes at least as many as B, with fewer
  rounds and a lower cost.
After the prompt rounds (unseen now a tuning set), C stayed level with or ahead of B on every set
(prompt version 2: unseen C 27, B 27 of 30; dev C 18, A 18 of 22).

## Consequences
- Phase 2's product flow runs setup C.
- The unseen set has been read and tuned on: a fair final number needs fresh or real club
  questions (Phase 5).
