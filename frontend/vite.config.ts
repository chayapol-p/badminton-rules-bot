// Vite settings: the React plugin, the dev proxy to FastAPI, and the Vitest settings

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";


// Where FastAPI runs during development (uv run uvicorn app.main:app); the Playwright tests set their own (record 0035)
const FASTAPI_ADDRESS = process.env.FASTAPI_ADDRESS ?? "http://localhost:8000";


export default defineConfig({
  plugins: [react()],

  // The browser talks only to Vite on :5173; these paths go on to FastAPI, so no cross-origin setup is needed
  server: {
    proxy: {
      "/chat": FASTAPI_ADDRESS,
      "/rule-books": FASTAPI_ADDRESS,
    },
  },

  // Vitest runs the page tests in a simulated browser (jsdom); the Playwright tests in e2e/ run separately
  test: {
    environment: "jsdom",
    setupFiles: ["./src/testSetup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
