# 0031 · `/chat` streams server-sent events with FastAPI's built-in support, read by a hand-written reader

- **Status:** Superseded by [0032](0032-the-chat-page-reads-the-stream-with-eventsource-parser.md) for the browser reader; the server choice stands
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise): the chat app

## Context
An answer takes 9-104 s and sends progress updates while it works (record 0028). The page must show them as they
come, so `POST /chat` streams. The browser's `EventSource` can only send GET requests (MDN), and the question goes
in a POST body.

## Options considered
Server: FastAPI's built-in `fastapi.sse.EventSourceResponse` (since 0.135; the repo pins 0.162; the tutorial shows
it on a POST endpoint). The bot runs in a worker thread, and `loop.call_soon_threadsafe` carries each update into
the stream, so the "still writing" thread of record 0028 works too.

Browser:
1. **`fetch` plus a small hand-written event reader**: TanStack AI's SSE transport reads POST chat streams with
   `fetch`. About 30 lines for three event types.
2. **`eventsource-parser`** (v4.1.3, Oct 2026): maintained, but adds a package to the streaming path.
3. **`@microsoft/fetch-event-source`**: last release v2.0.1, April 2021.

## Decision
FastAPI's built-in SSE on the server, and option 1 in the browser (Job, 17 Nov), because the house rules want the
streaming endpoint written by hand so a reader can trust it.

## Consequences
- The reader must handle an event split across two network chunks, and skip the keep-alive comment FastAPI sends
  every 15 s.
- Open: does Vite's dev proxy pass the stream through piece by piece? Check in the slice 2 demo.
