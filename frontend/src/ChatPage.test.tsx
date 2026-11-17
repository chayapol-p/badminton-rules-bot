// Tests for the chat page, slice 1 (criterion 1): ask a question, then see the answer with its [1] marker and the source list

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import samplePostsAnswer from "../../app/sample_posts_answer.json";
import { ChatPage } from "./ChatPage";


// Constants
const QUESTION = "How tall are the posts?";


// Answer every fetch with a /chat stream that holds the sample answer as one "answer" event
function stubChatWithSampleAnswer() {
  const body = `event: answer\ndata: ${JSON.stringify(samplePostsAnswer)}\n\n`;
  const fetchStub = vi.fn(async () => new Response(body, { headers: { "Content-Type": "text/event-stream" } }));
  vi.stubGlobal("fetch", fetchStub);
  return fetchStub;
}

// Answer every fetch with a /chat stream that sends the sample answer event in two pieces, cut in the middle of its data
function stubChatWithAnswerSplitMidEvent() {
  const eventText = `event: answer\ndata: ${JSON.stringify(samplePostsAnswer)}\n\n`;
  const middle = Math.floor(eventText.length / 2);
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(eventText.slice(0, middle)));
      controller.enqueue(encoder.encode(eventText.slice(middle)));
      controller.close();
    },
  });
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { headers: { "Content-Type": "text/event-stream" } })));
}

afterEach(() => {
  vi.unstubAllGlobals();
});


test("asking a question posts it to /chat as JSON", async () => {
  const fetchStub = stubChatWithSampleAnswer();
  render(<ChatPage />);

  await userEvent.type(screen.getByLabelText("Your question"), QUESTION);
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  expect(fetchStub).toHaveBeenCalledWith("/chat", expect.objectContaining({
    method: "POST",
    body: JSON.stringify({ question: QUESTION }),
  }));
});

test("the answer shows with its [1] marker, and the source list numbers the citation the same way", async () => {
  stubChatWithSampleAnswer();
  render(<ChatPage />);

  await userEvent.type(screen.getByLabelText("Your question"), QUESTION);
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  const answer = await screen.findByRole("region", { name: "Answer" });
  expect(answer).toHaveTextContent("The posts are 1.55 metres high, measured from the surface of the court [1].");
  const sources = within(screen.getByRole("list", { name: "Sources" })).getAllByRole("listitem");
  expect(sources).toHaveLength(1);
  expect(sources[0]).toHaveTextContent("[1]");
  expect(sources[0]).toHaveTextContent("The posts shall be 1.55 metres in height");
  expect(sources[0]).toHaveTextContent("Laws of Badminton 5.0 (2), Clause 1.4");
});

test("the answer still shows when its event arrives split across two network pieces", async () => {
  stubChatWithAnswerSplitMidEvent();
  render(<ChatPage />);

  await userEvent.type(screen.getByLabelText("Your question"), QUESTION);
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  const answer = await screen.findByRole("region", { name: "Answer" });
  expect(answer).toHaveTextContent("The posts are 1.55 metres high, measured from the surface of the court [1].");
});
