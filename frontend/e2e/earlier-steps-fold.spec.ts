// Browser test for the step list's fold while waiting (record 0036): opening "N earlier steps" slides open, every
// step row sits the same distance from the next, across the fold too, and each row stays one row inside the list. Layout needs a real browser, so this is a
// Playwright test; /chat is answered here with twelve steps and no answer, so the page stays in its waiting view.

import { expect, test } from "@playwright/test";


// Constants
// Twelve steps, like the real question in Job's live check: long search lines between short ones
const TWELVE_STEPS = [
  "Searching the rule books",
  "Found 5 rules to check",
  "Checking which rules answer your question",
  "Searching the rules: \"game of badminton is played with a shuttle shuttlecock\"",
  "Searching the rules: \"shuttle definition feathers cork base specifications Law 2\"",
  "Checking what the search found",
  "Searching the rules: \"badminton game played with shuttle racket rally definition of play\"",
  "Searching the rules: \"shuttle only object used in play tennis ball not permitted equipment used to play\"",
  "Checking what the search found",
  "Searching the rules: \"ball not allowed shuttle is the only object hit during play Law 2 shuttle specifications apply\"",
  "Searching the rules: \"service shuttle shall be hit below waist struck shuttle definition of service Law 9\"",
  "Checking what the search found",
];


test("the earlier steps slide open, and all step rows are evenly spaced", async ({ page }) => {
  // Answer /chat with twelve progress events and keep the stream open, as a slow real answer does. The browser's fetch
  // is swapped before the page loads, because a routed response always ends its stream
  const progressEvents = TWELVE_STEPS.map((message) =>
    `event: progress\ndata: ${JSON.stringify({ step: "searching", message, source_names: [], sources: [] })}\n\n`);
  await page.addInitScript((progressEventsText: string) => {
    window.fetch = async () => new Response(new ReadableStream({
      start(controller) { controller.enqueue(new TextEncoder().encode(progressEventsText)); },
    }));
  }, progressEvents.join(""));

  await page.goto("/");
  await page.getByLabel("Your question").fill("Can i use tennis ball to play in badminton court");
  await page.getByRole("button", { name: "Ask" }).click();
  const earlierStepsLine = page.getByText("8 earlier steps");
  await earlierStepsLine.click();
  await expect(page.getByText("Searching the rule books")).toBeVisible();

  // The fold's content animates its height, so it slides open instead of jumping
  const transitionedProperty = await page.locator(".earlier-steps").evaluate(
    (fold) => getComputedStyle(fold, "::details-content").transitionProperty);
  expect(transitionedProperty).toContain("block-size");

  // Wait for the slide to end, then measure the space from each row's top to the next row's top
  await page.waitForTimeout(400);
  const rowTops = await page.locator(".progress .step").evaluateAll(
    (rows) => rows.map((row) => row.getBoundingClientRect().top));
  const spacesBetweenRows = rowTops.slice(1).map((top, i) => Math.round(top - rowTops[i]));
  expect(new Set(spacesBetweenRows).size).toBe(1);

  // Every row stays inside the step list: long search words are cut with "…" instead of running past the page
  const listRight = await page.locator(".waiting-steps").evaluate((list) => list.getBoundingClientRect().right);
  const rowRights = await page.locator(".progress .step").evaluateAll(
    (rows) => rows.map((row) => row.getBoundingClientRect().right));
  for (const rowRight of rowRights) {
    expect(rowRight).toBeLessThanOrEqual(listRight + 1);
  }
});
