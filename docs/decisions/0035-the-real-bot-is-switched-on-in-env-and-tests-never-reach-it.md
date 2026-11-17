# 0035 · The real bot is switched on in .env, tests never reach it, and a failed answer shows an error

- **Status:** Accepted (Job, 17 Nov)
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise): the chat app

## Context
Slice 4 of `docs/specs/ask-a-rules-question.md` connects the real bot: `/chat` answers through `load_rules_bot()`
and `RulesBot.answer(...)`. A real answer takes 9-104 s and costs about $0.04 (record 0028), and the house rules
say no test calls a paid API. Until now the Playwright tests reused the dev servers on ports 8000 and 5173, so a
dev server on the real bot would have made the tests pay. And until slice 6, a failed answer left the page on
"Working" for good.

## Options considered
How the app picks the bot:
1. **A setting in .env, `RULES_BOT=stub` or `real`, stub when unset.** Nothing calls the paid API until it is
   switched on.
2. The same setting, real when unset.
3. No setting: the app always runs the real bot, and only the tests swap in the stub.

What the Playwright tests run against:
1. **Their own servers on ports 8001 and 5174, always with the stub, never reusing the dev servers.** No test can
   reach Mistral; each run takes a few seconds longer to start.
2. The running dev servers: faster, but they pay and get other text when the dev server runs the real bot.

When the real bot fails:
1. Leave it for slice 6, and do slice 6 straight after slice 4.
2. **Bring the smallest part forward into slice 4:** `/chat` sends an "error" event and the page shows
   "Couldn't write a checked answer. Please try again." (criterion 5). Slice 6 keeps the empty-question check.

## Decision
Option 1, option 1 and option 2 (Job, 17 Nov), so the live check never hangs and never costs by accident.

## Consequences
- The bot loads once, when the server starts, so a missing data file stops it with a clear message.
- The error event carries the plain message the page shows; the server logs the bot's own error, which names the
  call that failed.
