// Playwright settings: the end-to-end tests in e2e/ start their own FastAPI (port 8001, always the stub bot) and their
// own Vite (port 5174), then use the page in Chromium. They never reuse the dev servers on 8000 and 5173, which may
// run the real bot, so no test can call the paid API (record 0035)

import { defineConfig, devices } from "@playwright/test";


// Constants
const TEST_FASTAPI_PORT = 8001;
const TEST_VITE_PORT = 5174;


export default defineConfig({
  testDir: "./e2e",
  // The app's stub holds each of its 4 steps 1.5 s, so an answer takes about 6 s; checks wait up to 15 s
  expect: { timeout: 15_000 },
  use: {
    baseURL: `http://localhost:${TEST_VITE_PORT}`,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  // Start both test servers fresh; RULES_BOT=stub wins over whatever .env says
  webServer: [
    {
      command: `uv run uvicorn app.main:app --port ${TEST_FASTAPI_PORT}`,
      cwd: "..",
      env: { RULES_BOT: "stub" },
      url: `http://localhost:${TEST_FASTAPI_PORT}/health`,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --port ${TEST_VITE_PORT} --strictPort`,
      env: { FASTAPI_ADDRESS: `http://localhost:${TEST_FASTAPI_PORT}` },
      url: `http://localhost:${TEST_VITE_PORT}`,
      reuseExistingServer: false,
    },
  ],
});
