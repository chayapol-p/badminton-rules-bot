// Browser test: the first step shows within 1 s of pressing Ask (spec criterion 2).
// Runs against the stub bot, which sends its steps 0.3 s apart before the answer.

import { expect, test } from "@playwright/test";


test("the first step shows within 1 s, and the answer follows", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your question").fill("How tall are the posts?");
  await page.getByRole("button", { name: "Ask" }).click();

  await expect(page.getByRole("status").getByText("Searching the rule books")).toBeVisible({ timeout: 1_000 });
  await expect(page.getByRole("region", { name: "Answer" })).toContainText("1.55 metres");
  await expect(page.getByText(/^Checked \d+ steps? in \d+ s$/)).toBeVisible();
});
