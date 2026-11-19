# Refuse off-topic questions fast

**Story:** As a workshop attendee, I want a question that isn't about badminton rules ("test", "hi", "who won the worlds?") to get a refusal in a few seconds, so that a slip of the keyboard doesn't cost me a minute of waiting.
**Why now:** in Job's live test (17 Nov) the bot took 77 s to refuse "test". The vision asks for clear rules answers; a minute-long wait for "not covered" makes the app feel broken.

## Where the time goes (measured, 17 Nov)
- A refusal never runs the write call. All its time is the gather call's search loop (`answer_flows/gather_then_write/gather_then_write.py`).
- The last 3 Phase 2 runs (`evals/answer_runs/20261117T07*`) hold 42 refusals: median 23 s, slowest 70 s. Each model call takes about 6.4 s, and time grows with tool rounds: 2 rounds ≈ 21 s, 4 ≈ 37 s, 7 ≈ 70 s.
- Why it searches: `SEARCH_STEPS` tells the gather call to search for every part with no sentence before giving up (records 0022, 0024). An off-topic question has a part with no sentence by definition, so it searches. 77 s would fit about 11 model calls, close to the 10-round limit (`MAX_TOOL_ROUNDS`).
- **Live check, one run (Job's go-ahead, 17 Nov, run straight from the bot, not through the app):** "test" refused in 14.8 s, with 1 model call (14.2 s) and no tool round. So the 77 s did not repeat: a single gather call alone can take 14 s, and a search loop can stretch it, but one run can't say which happened in Job's test. Its reply also shows why off-topic needs its own words: it read "test" as the shuttle test and quoted Law 3.1 ("To test a shuttle…") as related.
- The eval sets hold no off-topic questions apart from `world-champion` in `evals/refusal_probes.json`. Every other "should refuse" question is on topic but not covered (string tension, grip size).

## What the industry does (checked 17 Nov)
- **A cheap screen before the main call.** NVIDIA NeMo Guardrails runs a small topic-control model as an input rail; an off-topic question is blocked and no answer is generated ([NeMo topic control](https://docs.nvidia.com/nemo/guardrails/latest/get-started/tutorials/nemoguard-topiccontrol-deployment)). Anthropic's docs suggest a lightweight model with a structured one-word classification to pre-screen input before the main conversation ([Mitigate jailbreaks](https://platform.claude.com/docs/en/docs/mitigating-jailbreaks-prompt-injections)).
- **An embedding router.** The question's vector is compared with example questions; below a similarity floor it takes a "none of the above" route with a canned reply and no model call ([semantic routing overview](https://futureagi.com/blog/semantic-routing-llm/), [RAG routing tutorial](https://medium.com/@shriyansnaik/enhancing-your-rag-pipeline-adding-semantic-routing-for-intent-handling-d95272123460)). Known weakness: it fails when off-topic text shares words with real topics.
- **Route by question type in research.** Adaptive-RAG trains a small classifier to send each query to no retrieval, one search or many ([Jeong et al., NAACL 2024](https://arxiv.org/abs/2403.14403)). Corrective RAG scores the retrieved documents with a small evaluator and acts on its confidence ([Yan et al., 2024](https://arxiv.org/abs/2401.15884)).

## Options
1. **Similarity floor (no model call, about 0 s).** Refuse when the best clause's cosine similarity is under a floor. Measured on saved vectors: the lowest answerable question scores 0.730 (Phase 2), and `world-champion` scores 0.734, so no floor separates them. Only a floor near 0.6 is safe, which catches gibberish but not real off-topic questions.
2. **Topic screen call (recommended).** One small, fast Mistral call with a yes/no structured reply ("is this a question about the rules of badminton?") before the search. An off-topic question gets a fixed refusal in a few seconds; every other question runs the flow unchanged. It adds about 1–2 s to every question (to measure), and its risk is false refusals, which the criteria below gate.
3. **Change the gather prompt.** Add a step: "When the question isn't about the rules of badminton, call no tool." Cheapest code change, but it still costs one large-model call (about 6 s), it touches the prompt behind every scored answer, and record 0026 needs 3 runs per flow to call it.
4. **Screen in parallel.** Option 2, but run the screen alongside the search and stop the search when it says off topic. Adds no time to good questions; more moving parts (cancelling a running loop). Worth it only if option 2's added seconds matter.

On-topic questions the rules don't cover (median 23 s) are a separate problem: the screen passes them on by design. A lower round limit for them would be its own spec.

## Two kinds of refusal (Job, 17 Nov)
- **Off topic** ("test", "hi", the weather): a short, polite reply that points the user to rules questions, with no search, so no tokens go on searching. Words (Job, 19 Nov): "I can only help with questions about badminton, from the official BWF rule books. If your question is about badminton, can you be more specific? For example: "I'm bleeding, can I stop playing?"".
- ~~**Badminton but not the rules** (history, rankings, results, players) counts as off topic (Job's pick 1a, 17 Nov).~~ **Superseded 18 Nov 2026 (Job):** the check is badminton-wide. Any question about badminton goes on to the flow, which answers it or says the rules don't cover it; only a question not about badminton at all is off topic.
- **Not covered** (string tension, grip size): unchanged. The flow searches, then says what the rules don't cover and quotes the related rules.

## What happens to the eval sets
Measured against every "should refuse" item and its pass rule (18 Nov):
- **Golden, unseen and Phase 2: no change.** All 20 of their no-answer items are about the rules (dates, wording, run-off, equipment limits), so the screen must pass them on and the flow refuses them as now. No golden answer or pass rule changes, and the PDF hashes stay the same.
- **Two golden attacks must pass the screen:** `attack-ignore-rules` and `attack-be-the-referee` look like misuse, but their pass rules want cited rules (the 1.15 m service rule; the Law 9.1 service rules). If the screen calls them off topic, they fail.
- **Probes:** since the badminton-wide change (18 Nov), `smash-training`, `world-champion` and `scoring-change-year` go on to the flow like every other badminton question, and the flow refuses them as before.
- **New set (17 Nov):** `evals/off_topic_questions.json`, 24 questions (Job kept all 23 first ones; the 24th added 18 Nov) that score the screen only, like the probes: 6 that must get the off-topic reply ("test", "hi", the weather, wifi, sums, a translation) and 18 that must go on to the flow: 7 badminton questions that aren't rules (coaching, rankings, buying, records, fitness, history, grip care; relabelled 18 Nov) and 11 near misses (casual or two-word rules questions, two that name tennis, one with no badminton word at all). Near misses come in pairs where possible, such as warm-up stretches against the warm-up rule. Adding a set is not a re-split (experiment rule 4).

## Criteria (draft for Job)
1. Given the question "test", when the bot answers, then `refused` is true, `citations` is empty, the answer is the off-topic reply, and it arrives within 5 s with no gather call.
2. Given each question not about badminton (the 6 `off_topic` items in `evals/off_topic_questions.json`), then every one gets the off-topic reply within 5 s.
3. Given every badminton question (the golden, unseen and Phase 2 sets, the probes, and the 18 `on_topic` items in `evals/off_topic_questions.json`), when screened in 3 runs, then the screen passes all of them on: 0 badminton questions blocked.
4. Given every badminton "should refuse" question (golden 3, unseen 1, Phase 2 14, the 6 refusal probes, and the 7 badminton questions that aren't rules), then the screen passes them on, and the flow refuses them with the not-covered refusal.
5. Given the screen call fails or times out after 5 s, then the question goes on to the full flow (no false refusal from an outage).

## Contract
`RulesBot.answer(question, report_progress)` is unchanged. An off-topic reply is a `RulesAnswer` with `refused: true`, empty `citations` and `related_citations`, and the fixed off-topic words. It sends one progress update first ("Checking the question").

## Out of scope
- Faster refusals for on-topic questions the rules don't cover.
- Any change to the gather or write prompts, the app or the front end (slice 5's refusal view shows this answer as it is).

## Decisions (Job, 17 Nov)
1. One paid live check with "test" (done, above).
2. Option 2: a topic screen call before the search.
3. Target: the off-topic reply within 5 s.
4. Screen model: `mistral-small-2603`, already pinned in `settings.py` as `mistral_draft_model`.
5. `RulesAnswer` says which kind of refusal it is (`off_topic` or `not_covered`), so the app drops the "Not covered by the rules" label on off-topic replies.

## Decisions (Job, 18 Nov 2026)
1. The check is badminton-wide: "if it's about badminton, pass, not strictly about the rules". This supersedes pick 1a (history and rankings off topic).
2. The prompt adds a court and equipment line: questions about courts, nets, posts, shuttles, rackets, line judges, umpires or other match officials are about badminton even when they do not name the sport. It fixes `net-cord-tension` ("What force, in newtons, should the net cord be stretched to?"), blocked in 2 of 3 check runs without it.
3. The prompt adds a scoring line: short questions about play, scoring, points, games, intervals, breaks, service or faults are about badminton even when they do not name the sport. It fixes "How long is the break at 11?" (Law 16.2, the interval), blocked in 3 of 3 runs of a red-team check without it; the question joins `evals/off_topic_questions.json` as a near miss.
4. The two word lists of decisions 2 and 3 give way to one framing sentence: "Every question comes from someone using a badminton rules app. Read any word that has a badminton meaning in that sense, and answer false only when the question is plainly about another subject." Each word list fixed only one family of words; the framing covers any word with a badminton meaning. Measured on `evals/casual_rules_questions.json` (173 short rules questions that name no sport, one per rule heading), before and after.
5. The framing sentence was reverted, because it re-blocked break-at-11 and did no better on the casual set (runs casual-rules-framing). The word lists of decisions 2 and 3 are back.
6. (19 Nov 2026) The search rescue was rejected, and the nearest-clauses idea with it: no cut-off splits the misses from the tricks (cosine rescues 0 of 18, BM25 2 of 18, with every trick kept out; run search-rescue-measure). About 8% of very casual rules questions are accepted as blocked, because the off-topic reply asks for a rules question and the user can rephrase, e.g. "i'm bleeding, can i stop" → "i'm bleeding, can i stop playing?" (Job's example).
7. (19 Nov 2026) The off-topic reply now asks for a more specific question: "I can only help with questions about badminton, from the official BWF rule books. If your question is about badminton, can you be more specific? For example: "I'm bleeding, can I stop playing?""

## Open questions
- (none)

## How we test
pytest with a stub screen for criteria 1 and 5 (no paid call). Criteria 2–4 as an eval run over the sets, 3 runs, logged to `evals/runs.jsonl`, after Job's go-ahead for the paid calls.

## Slices
1. Walking skeleton: the screen in front of the flow, with a stub that marks "test" off topic (criteria 1, 5)
2. The real screen call, measured on every eval set (criteria 2–4)

## Changes after building
- (none yet)

## Where it gets built (Job, 17 Nov)
The chat app's next slice, built in the chat app work from this spec once open questions 1–6 are answered.
