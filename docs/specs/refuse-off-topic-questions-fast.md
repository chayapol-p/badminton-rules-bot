# Refuse off-topic questions fast

**Story:** As a workshop attendee, I want a question that isn't about badminton rules ("test", "hi", "who won the worlds?") to get a refusal in a few seconds, so that a slip of the keyboard doesn't cost me a minute of waiting.
**Why now:** in Job's live test (17 Nov) the bot took 77 s to refuse "test". The vision asks for clear rules answers; a minute-long wait for "not covered" makes the app feel broken.

## Where the time goes (measured, 17 Nov)
- A refusal never runs the write call. All its time is the gather call's search loop (`answer_flows/gather_then_write/gather_then_write.py`).
- The last 3 Phase 2 runs (`evals/answer_runs/20261117T07*`) hold 42 refusals: median 23 s, slowest 70 s. Each model call takes about 6.4 s, and time grows with tool rounds: 2 rounds ≈ 21 s, 4 ≈ 37 s, 7 ≈ 70 s.
- Why it searches: `SEARCH_STEPS` tells the gather call to search for every part with no sentence before giving up (records 0022, 0024). An off-topic question has a part with no sentence by definition, so it searches. 77 s fits about 11 model calls, close to the 10-round limit (`MAX_TOOL_ROUNDS`). Not yet confirmed: no run file holds "test" (open question 1).
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
- **Off topic** ("test", "hi", a training plan): a short, polite reply that points the user to rules questions, with no search, so no tokens go on searching. Draft words (Job to edit): "I can only help with the rules of badminton, from the official BWF rule books. Try a question like "How high is the net?"".
- **Badminton but not the rules** (history, rankings, results, players) counts as off topic (Job, 17 Nov).
- **Not covered** (string tension, grip size): unchanged. The flow searches, then says what the rules don't cover and quotes the related rules.

## What happens to the eval sets
Measured against every "should refuse" item and its pass rule (18 Nov):
- **Golden, unseen and Phase 2: no change.** All 20 of their no-answer items are about the rules (dates, wording, run-off, equipment limits), so the screen must pass them on and the flow refuses them as now. No golden answer or pass rule changes, and the PDF hashes stay the same.
- **Two golden attacks must pass the screen:** `attack-ignore-rules` and `attack-be-the-referee` look like misuse, but their pass rules want cited rules (the 1.15 m service rule; the Law 9.1 service rules). If the screen calls them off topic, they fail.
- **Probes that would take the new reply:** `smash-training` (pass rule already says "answers rules questions only") and `world-champion` ("names no player") still pass with the polite reply. `scoring-change-year` (history) takes it too, by Job's pick below; its pass rule ("gives no year") still passes.
- **New set (17 Nov):** `evals/off_topic_questions.json`, 23 questions (Job kept all 23) that score the screen only, like the probes: 13 that must get the off-topic reply ("test", "hi", and badminton questions that aren't rules, such as a training plan or the fastest smash) and 10 near misses that must go on to the flow (casual or two-word rules questions, two that name tennis, one with no badminton word at all). Near misses come in pairs where possible, such as warm-up stretches against the warm-up rule. Adding a set is not a re-split (experiment rule 4).

## Criteria (draft for Job)
1. Given the question "test", when the bot answers, then `refused` is true, `citations` is empty, the answer is the off-topic reply, and it arrives within 5 s with no gather call.
2. Given each `off_topic` item in `evals/off_topic_questions.json` (13), then each gets the off-topic reply within 5 s.
3. Given every answerable question in the golden, unseen and Phase 2 sets, the two golden attacks, and the 10 `on_topic` near misses, when screened in 3 runs, then the screen passes all of them on: 0 false off-topic replies.
4. Given every on-topic "should refuse" question (golden 3, unseen 1, Phase 2 14, the probes `string-tension`, `altitude-shuttle-speed` and `late-withdrawal-penalty`), then the screen passes them on, and the flow still refuses them with the not-covered refusal (Phase 2: 14 of 14).
5. Given the screen call fails or times out after 5 s, then the question goes on to the full flow (no false refusal from an outage).

## Contract
`RulesBot.answer(question, report_progress)` is unchanged. An off-topic reply is a `RulesAnswer` with `refused: true`, empty `citations` and `related_citations`, and the fixed off-topic words. It sends one progress update first ("Checking the question").

## Out of scope
- Faster refusals for on-topic questions the rules don't cover.
- Any change to the gather or write prompts, the app or the front end (slice 5's refusal view shows this answer as it is).

## Open questions
1. May I run the live check once with "test" (one paid run, a few cents) to confirm where the 77 s goes?
2. Which option: 2 (recommended), 4, 3 or 1?
3. Is 5 s the right target for criterion 1?
4. Which small model for the screen? Its ID must be pinned (experiment rule 2).
5. Slice 5 labels every refusal "Not covered by the rules", which reads oddly above the off-topic reply. Should `RulesAnswer` say which kind of refusal it is (e.g. `refusal_kind: "off_topic" | "not_covered"`), so the app can drop that label? That changes the app's contract, so it waits for slice 5 to land.

## How we test
pytest with a stub screen for criteria 1 and 5 (no paid call). Criteria 2–4 as an eval run over the sets, 3 runs, logged to `evals/runs.jsonl`, after Job's go-ahead for the paid calls.

## Slices
1. Walking skeleton: the screen in front of the flow, with a stub that marks "test" off topic (criteria 1, 5)
2. The real screen call, measured on every eval set (criteria 2–4)

## Changes after building
- (none yet)

## Where it gets built (Job, 17 Nov)
The chat app's next slice, built in the chat app work from this spec once open questions 1–6 are answered.
