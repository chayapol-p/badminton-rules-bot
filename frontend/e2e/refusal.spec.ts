// Browser test: a question the rule books don't answer shows the refusal, labelled, with no sources
// (spec criterion 4). The stub refuses exactly this question, with a real refusal from an earlier run.

import { expect, test } from "@playwright/test";


test("a question the rules don't cover shows the refusal with its label and no sources", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your question").fill("What force, in newtons, should the net cord be stretched to?");
  await page.getByRole("button", { name: "Ask" }).click();

  const answer = page.getByRole("region", { name: "Answer" });
  await expect(answer).toContainText("Not covered by the rules");
  await expect(answer).toContainText("The sources do not say the force in newtons");
  await expect(answer.getByRole("heading", { name: "Sources" })).toHaveCount(0);
});
