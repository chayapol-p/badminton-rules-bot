// Playwright settings: the end-to-end tests in e2e/ start FastAPI and the Vite dev server, then use the page in Chromium

import { defineConfig, devices } from "@playwright/test";


export default defineConfig({
  testDir: "./e2e",
  // The app's stub holds each of its 4 steps 1.5 s, so an answer takes about 6 s; checks wait up to 15 s
  expect: { timeout: 15_000 },
  use: {
    baseURL: "http://localhost:5173",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  // Start both servers, or reuse ones already running on your Mac
  webServer: [
    {
      command: "uv run uvicorn app.main:app --port 8000",
      cwd: "..",
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
    },
  ],
});
