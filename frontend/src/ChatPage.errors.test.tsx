// Slice 4 tests for the chat page: a failed answer shows an error instead of waiting for good (spec criterion 5,
// record 0035).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { ChatPage } from "./ChatPage";


// Constants
const FAILED_ANSWER_MESSAGE = "Couldn't write a checked answer. Please try again.";


// ===== Test helpers =====

// Answer every fetch with a /chat stream that holds these events, then ends
function stubChatWithEvents(eventsText: string) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(eventsText, { headers: { "Content-Type": "text/event-stream" } })));
}

// Opens the page and asks the posts question
async function askQuestion() {
  render(<ChatPage />);
  await userEvent.type(screen.getByLabelText("Your question"), "How tall are the posts?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});


// ===== The server says the answer failed =====

test("an error event shows its message, with no answer and no steps still running", async () => {
  const progressEvent = `event: progress\ndata: {"step":"finding_rules","message":"Searching the rule books","source_names":[],"sources":[]}\n\n`;
  const errorEvent = `event: error\ndata: {"message":"${FAILED_ANSWER_MESSAGE}"}\n\n`;
  stubChatWithEvents(progressEvent + errorEvent);
  await askQuestion();

  expect(await screen.findByRole("alert")).toHaveTextContent(FAILED_ANSWER_MESSAGE);
  expect(screen.queryByRole("region", { name: "Answer" })).not.toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});


// ===== The answer never comes =====

test("a stream that ends without an answer shows the same error", async () => {
  stubChatWithEvents("");
  await askQuestion();

  expect(await screen.findByRole("alert")).toHaveTextContent(FAILED_ANSWER_MESSAGE);
});

test("a request that can't reach the server shows the same error", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
  await askQuestion();

  expect(await screen.findByRole("alert")).toHaveTextContent(FAILED_ANSWER_MESSAGE);
});
