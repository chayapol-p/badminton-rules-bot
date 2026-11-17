# 0030 · The front end is Vite, React and TypeScript in `frontend/`, tested with Vitest and Playwright

- **Status:** Accepted (Job, 17 Nov)
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise): the chat app

## Context
The stack was picked on 14 Nov (FastAPI back end, React front end). The folder, the build tool, the extra libraries
and the tests were still open.

## Options considered
1. **Vite with the React and TypeScript template, adding libraries only when a slice needs them**: react.dev's
   "build a React app from scratch" path for apps with their own back end (Vite, Parcel or Rsbuild).
2. **A full framework** (Next.js, React Router): react.dev's default for new apps, but it brings its own server,
   which FastAPI already is.
3. **TanStack AI's `useChat`**: its docs pair it with TanStack's own JavaScript server and word-by-word text events;
   this app streams progress updates and one checked answer from Python.
4. **TanStack Query and Router from the start**: the official FastAPI full-stack template uses them, but one screen
   with one streaming request has nothing to route or cache yet.

Folder: `frontend/` (the FastAPI full-stack template's name) over `web/` (no source).
Tests: Vitest for the page and one Playwright test of the full path (Job's pick; the template also uses Playwright).

## Decision
Option 1, in `frontend/`, tested with Vitest and Playwright. TanStack Query may come with chat history.

## Evidence
React docs, Vite docs and the FastAPI template's `frontend/package.json`, checked 17 Nov.

## Consequences
- Node is needed on the Mac for development only. In production `npm run build` makes `dist/`, and FastAPI serves it
  (`app.frontend()` or `StaticFiles`), so the browser reaches FastAPI directly.
