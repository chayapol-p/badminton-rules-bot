// Slice 3 tests for the chat page: each [n] marker opens a popover with its source and a PDF link (spec criterion 3,
// record 0034). The server adds pdf_link to each citation, so these tests send the sample answer with its link.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { ChatPage } from "./ChatPage";
import { POSTS_PDF_LINK, SAMPLE_CHAT_ANSWER } from "./sampleChatAnswer";


// Constants
const POSTS_SOURCE_NAME = "Laws of Badminton 5.0 (2), Clause 1.4";


// ===== Test helpers =====

// Answer every fetch with a /chat stream that holds the sample answer, each citation carrying the server's PDF link
function stubChatWithLinkedAnswer() {
  const body = `event: answer\ndata: ${JSON.stringify(SAMPLE_CHAT_ANSWER)}\n\n`;
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { headers: { "Content-Type": "text/event-stream" } })));
}

// Opens the page, asks the posts question and returns the [1] marker once the answer shows
async function askAndFindMarker() {
  stubChatWithLinkedAnswer();
  render(<ChatPage />);
  await userEvent.type(screen.getByLabelText("Your question"), "How tall are the posts?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  return await screen.findByRole("button", { name: "Source 1" });
}

afterEach(() => {
  vi.unstubAllGlobals();
});


// ===== Opening a marker =====

test("clicking [1] shows the quote, the source name and a link to the PDF page", async () => {
  const marker = await askAndFindMarker();
  expect(marker).toHaveTextContent("[1]");

  await userEvent.click(marker);

  const popover = await screen.findByRole("dialog");
  expect(popover).toHaveTextContent("The posts shall be 1.55 metres in height");
  expect(popover).toHaveTextContent(POSTS_SOURCE_NAME);
  expect(within(popover).getByRole("link")).toHaveAttribute("href", POSTS_PDF_LINK);
});


// ===== Closing it =====

test("Escape closes the popover and puts focus back on the marker", async () => {
  const marker = await askAndFindMarker();
  await userEvent.click(marker);
  await screen.findByRole("dialog");

  await userEvent.keyboard("{Escape}");

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(marker).toHaveFocus();
});

test("a click outside closes the popover", async () => {
  const marker = await askAndFindMarker();
  await userEvent.click(marker);
  await screen.findByRole("dialog");

  await userEvent.click(screen.getByRole("heading", { name: "Badminton rules" }));

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});


// ===== The source list =====

test("the source list links each source to the same PDF page", async () => {
  await askAndFindMarker();

  const sources = within(screen.getByRole("list", { name: "Sources" })).getAllByRole("listitem");
  expect(within(sources[0]).getByRole("link")).toHaveAttribute("href", POSTS_PDF_LINK);
});
