// Slice 7 browser test: "test" gets the short off-topic reply, with no "Not covered" label
// (docs/specs/refuse-off-topic-questions-fast.md, criterion 1). Runs against the stub bot, which answers "test" this way.

import { expect, test } from "@playwright/test";


test("'test' gets the off-topic reply with no 'Not covered' label", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your question").fill("test");
  await page.getByRole("button", { name: "Ask" }).click();

  const answer = page.getByRole("region", { name: "Answer" });
  await expect(answer).toContainText("I can only help with questions about badminton");
  await expect(answer.getByText("Not covered by the rules")).toHaveCount(0);
});
