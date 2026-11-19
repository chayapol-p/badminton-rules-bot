// Tests for the chat page: steps show while waiting, then fold away (spec criterion 2, record 0033).
// Each test controls the stream by hand, so it can check the page between events.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { SAMPLE_CHAT_ANSWER } from "./sampleChatAnswer";
import { ChatPage } from "./ChatPage";


// ===== Test helpers =====

// A /chat response whose events the test sends one at a time
function startControlledChat() {
  const encoder = new TextEncoder();
  let streamController!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start: (controller) => { streamController = controller; } });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body)));

  // Sends one event with its data as JSON
  function sendEvent(name: string, data: object) {
    streamController.enqueue(encoder.encode(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`));
  }
  // Sends one progress update, shaped like ProgressUpdate
  function sendProgress(step: string, message: string) {
    sendEvent("progress", { step, message, source_names: [], sources: [] });
  }
  // Sends the sample answer and ends the stream
  function sendAnswer() {
    sendEvent("answer", SAMPLE_CHAT_ANSWER);
    streamController.close();
  }
  return { sendProgress, sendAnswer };
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


// ===== While waiting =====

test("each step shows as it arrives, and the answer area stays empty", async () => {
  const chat = startControlledChat();
  await askQuestion();

  chat.sendProgress("finding_rules", "Searching the rule books");
  chat.sendProgress("found_rules", "Found 5 rules to check");

  const steps = await screen.findByRole("status");
  expect(await within(steps).findByText("Found 5 rules to check")).toBeInTheDocument();
  expect(within(steps).getByText("Searching the rule books")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Answer" })).not.toBeInTheDocument();
});

test("still writing updates replace each other instead of adding lines", async () => {
  const chat = startControlledChat();
  await askQuestion();

  chat.sendProgress("writing", "Writing the answer");
  chat.sendProgress("still_writing", "Still writing the answer · 5 s");
  chat.sendProgress("still_writing", "Still writing the answer · 10 s");

  const steps = await screen.findByRole("status");
  expect(await within(steps).findByText("Still writing the answer · 10 s")).toBeInTheDocument();
  expect(within(steps).queryByText("Still writing the answer · 5 s")).not.toBeInTheDocument();
  expect(within(steps).getAllByRole("listitem")).toHaveLength(2);
});


// ===== After the answer =====

test("when the answer arrives, the steps fold into one closed summary line", async () => {
  const chat = startControlledChat();
  await askQuestion();

  chat.sendProgress("finding_rules", "Searching the rule books");
  chat.sendProgress("found_rules", "Found 5 rules to check");
  chat.sendProgress("writing", "Writing the answer");
  chat.sendAnswer();

  expect(await screen.findByRole("region", { name: "Answer" })).toBeInTheDocument();
  const summary = screen.getByText(/^Checked 3 steps in \d+ s$/);
  expect(summary.closest("details")).not.toHaveAttribute("open");
});

test("opening the summary shows the steps again", async () => {
  const chat = startControlledChat();
  await askQuestion();

  chat.sendProgress("finding_rules", "Searching the rule books");
  chat.sendAnswer();

  await userEvent.click(await screen.findByText(/^Checked 1 step in \d+ s$/));
  expect(screen.getByText("Searching the rule books")).toBeVisible();
});

test("while waiting, the newest step is marked as the step in progress and the earlier ones as done", async () => {
  const chat = startControlledChat();
  await askQuestion();

  chat.sendProgress("finding_rules", "Searching the rule books");
  chat.sendProgress("found_rules", "Found 5 rules to check");

  const steps = await screen.findByRole("status");
  const newestStep = await within(steps).findByText("Found 5 rules to check");
  expect(newestStep.closest("li")).toHaveAttribute("aria-current", "step");
  expect(within(steps).getByText("Searching the rule books").closest("li")).not.toHaveAttribute("aria-current");
});

test("after the answer, no step is marked as in progress", async () => {
  const chat = startControlledChat();
  await askQuestion();

  chat.sendProgress("finding_rules", "Searching the rule books");
  chat.sendProgress("writing", "Writing the answer");
  chat.sendAnswer();

  await screen.findByRole("region", { name: "Answer" });
  for (const step of screen.getAllByRole("listitem", { hidden: true })) {
    expect(step).not.toHaveAttribute("aria-current");
  }
});


// ===== A long wait (record 0036) =====

// Sends six steps, as a real question with several searches does
function sendSixSteps(chat: ReturnType<typeof startControlledChat>) {
  chat.sendProgress("finding_rules", "Searching the rule books");
  chat.sendProgress("found_rules", "Found 5 rules to check");
  chat.sendProgress("checking_rules", "Checking which rules answer your question");
  chat.sendProgress("searching", "Searching the rules: \"shuttle definition\"");
  chat.sendProgress("checking_rules", "Checking what the search found");
  chat.sendProgress("searching", "Searching the rules: \"Law 8 start of play rally shuttle shall be in play service\"");
}

test("with six steps, only the newest four show, and the first two fold into one line", async () => {
  const chat = startControlledChat();
  await askQuestion();

  sendSixSteps(chat);

  const steps = await screen.findByRole("status");
  expect(await within(steps).findByText("2 earlier steps")).toBeVisible();
  expect(within(steps).getByText("Searching the rule books")).not.toBeVisible();
  expect(within(steps).getByText("Found 5 rules to check")).not.toBeVisible();
  expect(within(steps).getByText("Checking which rules answer your question")).toBeVisible();
  expect(within(steps).getByText("Searching the rules: \"Law 8 start of play rally shuttle shall be in play service\"")).toBeVisible();
});

test("clicking the earlier-steps line shows all six steps", async () => {
  const chat = startControlledChat();
  await askQuestion();
  sendSixSteps(chat);

  await userEvent.click(await screen.findByText("2 earlier steps"));

  expect(screen.getByText("Searching the rule books")).toBeVisible();
  expect(screen.getByText("Found 5 rules to check")).toBeVisible();
});

test("with four steps or fewer, there is no earlier-steps line", async () => {
  const chat = startControlledChat();
  await askQuestion();

  chat.sendProgress("finding_rules", "Searching the rule books");
  chat.sendProgress("found_rules", "Found 5 rules to check");
  chat.sendProgress("checking_rules", "Checking which rules answer your question");
  chat.sendProgress("writing", "Writing the answer");

  const steps = await screen.findByRole("status");
  await within(steps).findByText("Writing the answer");
  expect(within(steps).queryByText(/earlier step/)).not.toBeInTheDocument();
});

test("still-writing ticks still replace each other, so they never push steps into the fold", async () => {
  const chat = startControlledChat();
  await askQuestion();

  chat.sendProgress("finding_rules", "Searching the rule books");
  chat.sendProgress("found_rules", "Found 5 rules to check");
  chat.sendProgress("writing", "Writing the answer");
  chat.sendProgress("still_writing", "Still writing the answer · 5 s");
  chat.sendProgress("still_writing", "Still writing the answer · 10 s");
  chat.sendProgress("still_writing", "Still writing the answer · 15 s");

  const steps = await screen.findByRole("status");
  expect(await within(steps).findByText("Still writing the answer · 15 s")).toBeVisible();
  expect(within(steps).queryByText(/earlier step/)).not.toBeInTheDocument();
});

test("the step in progress is always visible, as the last of the four", async () => {
  const chat = startControlledChat();
  await askQuestion();

  sendSixSteps(chat);

  const steps = await screen.findByRole("status");
  const runningMessage = await within(steps).findByText("Searching the rules: \"Law 8 start of play rally shuttle shall be in play service\"");
  expect(runningMessage).toBeVisible();
  expect(runningMessage.closest("li")).toHaveAttribute("aria-current", "step");
});

test("each step line keeps its full words in a hover title, for when the row cuts it short", async () => {
  const chat = startControlledChat();
  await askQuestion();

  sendSixSteps(chat);

  const steps = await screen.findByRole("status");
  const longMessage = "Searching the rules: \"Law 8 start of play rally shuttle shall be in play service\"";
  expect(await within(steps).findByText(longMessage)).toHaveAttribute("title", longMessage);
});
