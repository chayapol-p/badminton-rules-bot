// Slice 6 browser test: pressing Ask with a blank box shows the message and makes no /chat request (spec criterion 6).

import { expect, test } from "@playwright/test";


test("a blank question shows the message and sends no request", async ({ page }) => {
  const chatRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/chat")) {
      chatRequests.push(request.url());
    }
  });

  await page.goto("/");
  await page.getByLabel("Your question").fill("   ");
  await page.getByRole("button", { name: "Ask" }).click();

  await expect(page.getByText("Please type a question")).toBeVisible();
  expect(chatRequests).toEqual([]);
});
