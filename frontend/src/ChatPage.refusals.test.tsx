// Slice 5 tests for the chat page: a refusal shows the bot's own words, labelled "Not covered by the rules", with no
// source list (spec criterion 4). Slice 7: an off-topic reply drops the label.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import sampleOffTopicAnswer from "../../app/sample_off_topic_answer.json";
import sampleRefusalAnswer from "../../app/sample_refusal_answer.json";
import { ChatPage } from "./ChatPage";
import { SAMPLE_CHAT_ANSWER } from "./sampleChatAnswer";


// Constants
const REFUSAL_LABEL = "Not covered by the rules";


// ===== Test helpers =====

// Answer every fetch with a /chat stream that holds this answer as its "answer" event
function stubChatWithAnswer(answer: object) {
  const body = `event: answer\ndata: ${JSON.stringify(answer)}\n\n`;
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { headers: { "Content-Type": "text/event-stream" } })));
}

// Opens the page, asks a question and returns the answer region once it shows
async function askAndFindAnswer() {
  render(<ChatPage />);
  await userEvent.type(screen.getByLabelText("Your question"), "What force, in newtons, should the net cord be stretched to?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  return await screen.findByRole("region", { name: "Answer" });
}

afterEach(() => {
  vi.unstubAllGlobals();
});


// ===== A refusal =====

test("a refusal shows its own words under the label, with no source list", async () => {
  stubChatWithAnswer(sampleRefusalAnswer);

  const answer = await askAndFindAnswer();

  expect(within(answer).getByText(REFUSAL_LABEL)).toBeInTheDocument();
  expect(answer).toHaveTextContent("The sources do not say the force in newtons to which the net cord should be stretched.");
  expect(within(answer).queryByRole("heading", { name: "Sources" })).not.toBeInTheDocument();
  expect(within(answer).queryByRole("list")).not.toBeInTheDocument();
});


// ===== A normal answer =====

test("a normal answer has no refusal label", async () => {
  stubChatWithAnswer(SAMPLE_CHAT_ANSWER);

  const answer = await askAndFindAnswer();

  expect(within(answer).queryByText(REFUSAL_LABEL)).not.toBeInTheDocument();
});


// ===== An off-topic question (slice 7) =====

test("an off-topic reply shows its words with no 'Not covered' label and no sources", async () => {
  stubChatWithAnswer(sampleOffTopicAnswer);

  const answer = await askAndFindAnswer();

  expect(answer).toHaveTextContent("I can only help with questions about badminton");
  expect(within(answer).queryByText(REFUSAL_LABEL)).not.toBeInTheDocument();
  expect(within(answer).queryByRole("list")).not.toBeInTheDocument();
});

test("a not-covered refusal still carries the label", async () => {
  stubChatWithAnswer({ ...sampleRefusalAnswer, refusal_kind: "not_covered" });

  const answer = await askAndFindAnswer();

  expect(within(answer).getByText(REFUSAL_LABEL)).toBeInTheDocument();
});
