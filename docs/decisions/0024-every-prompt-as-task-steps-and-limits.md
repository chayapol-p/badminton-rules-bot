# 0024 · Every answer prompt as a task, numbered steps and limits with reasons

- **Status:** Accepted (Job, 13 Nov); its effect is measured in the first Phase 2 runs
- **Date:** 2026-11-13
- **Stage:** Phase 2 (productise)

## Context
Every answer prompt was one numbered list of rules that mixed the order of work (list the parts, pick
sentences) with limits (use only the sources, para rules only for para questions). Rules 4 to 10 each
came from one failed question. One contradiction needed a patch: the agent rule search-before-gaps
existed only to say that answer rule 3 ("leave a part empty") changes when the model can search
(workshop/notes.md, 10 Nov).

## Options considered
1. **Keep the rule list.** No change; the patch and the growing edge-case list stay.
2. **Rewrite every answer prompt as sections** (published practice):
   - numbered steps when the order matters (Anthropic, Prompting best practices);
   - no "laundry list of edge cases"; the "right altitude" between hard-coded rules and vague advice
     (Anthropic, Effective context engineering for AI agents);
   - a reason with each limit, so the model generalizes from it (Anthropic, Prompting best practices);
   - clear sections (Mistral, Prompting capabilities: sections and subsections).
3. **Test the gather prompt alone first, after slice 5's baseline run.** Claude's suggestion; not picked.

## Decision
Option 2, now, for every prompt that produces an answer: the single-call and loop-call-with-tools
answer prompt, slice 5's gather and write prompts, and the tools section. The judge's prompt is not
changed, so runs stay comparable with earlier grading.

- Sections: `<task>`, `<steps>` (numbered), `<limits>` (each with its reason), and `<tools>` for flows with
  tools (answer_flows/shared/prompt_sections.py, answer_flows/shared/tool_loop.py).
- The two default agent rules of record 0022 become the search steps, placed after finding sentences
  and before replying, so searching comes before giving up on a part. EXTRA_AGENT_RULES is empty and
  `--no-agent-rules` is gone.
- Extra rules under test (`--rule`) are one more limit; extra agent rules (`--agent-rule`) one more tools note.
- One new tools note: a preview line shows only a clause's opening words, so read it before picking
  its sentences (only clauses shown in full can be cited).
- runs.jsonl records `prompt_layout: "task, steps, limits"`.

## Evidence
No paid run had used the Phase 2 code yet, so no baseline is lost. Prompt version 2 (a full rewrite,
9-10 Nov) moved failures around rather than removing them (record 0023, option 1): read the first
runs against the Stage 3 numbers with that in mind.

## Consequences
- Supersedes record 0022's two default agent rules; prompt version 1's content is kept as steps and limits.
- The known rule 4 clash (give the standard rule first) stays, in the answer and write prompts' limits,
  until its own fix and run.
