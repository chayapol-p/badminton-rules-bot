# 0032 · The chat page reads the `/chat` stream with `eventsource-parser`

- **Status:** Accepted (Job, 17 Nov)
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise): the chat app
- **Supersedes:** the browser half of [0031](0031-chat-streams-server-sent-events-read-by-a-hand-written-reader.md).
  The server half stands: `/chat` streams with FastAPI's built-in `EventSourceResponse`.

## Context
Record 0031 chose a hand-written reader in the browser, because "the house rules want the streaming endpoint
written by hand". CLAUDE.md's hand-written list names the streaming *endpoint*, the server, and says everything
else uses installed packages. The browser's parser is not on that list, so 0031 stretched the rule.

## Options considered
1. **`eventsource-parser`** (v4.1.3, 25 Oct 2026, no dependencies of its own). Vercel's AI SDK
   (`@ai-sdk/provider-utils`) depends on it. Its `EventSourceParserStream` turns the response body into events.
2. **A hand-written reader** (what 0031 chose). The official OpenAI and Anthropic JavaScript SDKs write their own
   line decoder, with no parser dependency on npm, but they do it to keep a library free of dependencies, which an
   app doesn't need. Ours also missed one rule of the standard: a bare `\r` can end a line.
3. **`@microsoft/fetch-event-source`**: last release v2.0.1, April 2021.
4. **`eventsource`** (v5.1.5): copies the browser's `EventSource`, which reconnects by itself, so a dropped
   connection would send the POSTed question again.

## Decision
Option 1 (Job, 17 Nov): the page reads the stream with `eventsource-parser`, and `readServerSentEvents.ts` is
deleted.

## Consequences
- The parsing rules (an event split across two network chunks, keep-alive comments, line endings) are the
  package's job and its tests'. One page test still feeds an event split across two chunks.
- Still open from 0031: does Vite's dev proxy pass the stream through piece by piece? Check in the slice 2 demo.
