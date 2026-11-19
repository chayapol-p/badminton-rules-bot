// End-to-end check of asking a question: the real page in a browser, through the Vite proxy, to FastAPI with the stub bot

import { expect, test } from "@playwright/test";


test("a question gets the stub answer and its source list", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("Your question").fill("How tall are the posts?");
  await page.getByRole("button", { name: "Ask" }).click();

  await expect(page.getByRole("region", { name: "Answer" })).toContainText("The posts are 1.55 metres high");
  const sources = page.getByRole("list", { name: "Sources" }).getByRole("listitem");
  await expect(sources).toHaveCount(1);
  await expect(sources.first()).toContainText("Laws of Badminton 5.0 (2), Clause 1.4");
});
