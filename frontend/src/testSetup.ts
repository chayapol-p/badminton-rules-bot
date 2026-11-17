// Vitest setup: adds the jest-dom matchers, such as toHaveTextContent, and clears the page after each test

import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";


// Testing Library clears the page by itself only when Vitest globals are on; they are off here, so clear it by hand
afterEach(() => {
  cleanup();
});
