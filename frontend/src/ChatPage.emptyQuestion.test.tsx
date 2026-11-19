// Tests for the chat page: an empty or blank question shows "Please type a question" and sends nothing
// (spec criterion 6).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { ChatPage } from "./ChatPage";
import { SAMPLE_CHAT_ANSWER } from "./sampleChatAnswer";


// Constants
const EMPTY_QUESTION_MESSAGE = "Please type a question";


// ===== Test helpers =====

// Answer every fetch with the sample answer, and return the stub so a test can count the requests
function stubChatWithSampleAnswer() {
  const body = `event: answer\ndata: ${JSON.stringify(SAMPLE_CHAT_ANSWER)}\n\n`;
  const fetchStub = vi.fn(async () => new Response(body, { headers: { "Content-Type": "text/event-stream" } }));
  vi.stubGlobal("fetch", fetchStub);
  return fetchStub;
}

afterEach(() => {
  vi.unstubAllGlobals();
});


// ===== An empty or blank box =====

test("pressing Ask with an empty box shows the message and sends nothing", async () => {
  const fetchStub = stubChatWithSampleAnswer();
  render(<ChatPage />);

  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  expect(await screen.findByText(EMPTY_QUESTION_MESSAGE)).toBeInTheDocument();
  expect(fetchStub).not.toHaveBeenCalled();
});

test("a box with only spaces counts as empty", async () => {
  const fetchStub = stubChatWithSampleAnswer();
  render(<ChatPage />);

  await userEvent.type(screen.getByLabelText("Your question"), "   ");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  expect(await screen.findByText(EMPTY_QUESTION_MESSAGE)).toBeInTheDocument();
  expect(fetchStub).not.toHaveBeenCalled();
});


// ===== After the message =====

test("typing again clears the message", async () => {
  stubChatWithSampleAnswer();
  render(<ChatPage />);
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText(EMPTY_QUESTION_MESSAGE);

  await userEvent.type(screen.getByLabelText("Your question"), "H");

  expect(screen.queryByText(EMPTY_QUESTION_MESSAGE)).not.toBeInTheDocument();
});

test("a real question after the message still sends and gets its answer", async () => {
  const fetchStub = stubChatWithSampleAnswer();
  render(<ChatPage />);
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText(EMPTY_QUESTION_MESSAGE);

  await userEvent.type(screen.getByLabelText("Your question"), "How tall are the posts?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  expect(await screen.findByRole("region", { name: "Answer" })).toBeInTheDocument();
  expect(fetchStub).toHaveBeenCalledTimes(1);
});
