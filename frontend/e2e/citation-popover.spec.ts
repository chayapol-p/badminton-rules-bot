// Browser test: clicking [1] shows the PDF link, and the link opens the real rule book (spec criterion 3).
// Runs against the stub bot. The PDFs in data/bwf/ are never committed, so the test skips where they are missing.

import { existsSync } from "node:fs";

import { expect, test } from "@playwright/test";


// Constants
const LAWS_PDF_FILE = new URL("../../data/bwf/bwf-laws-of-badminton-2025-v5.0.pdf", import.meta.url);


test("clicking [1] shows the PDF link, and the link serves the rule book", async ({ page, request }) => {
  test.skip(!existsSync(LAWS_PDF_FILE), "the rule-book PDFs in data/bwf/ are downloaded by hand and never committed");

  await page.goto("/");
  await page.getByLabel("Your question").fill("How tall are the posts?");
  await page.getByRole("button", { name: "Ask" }).click();
  await page.getByRole("button", { name: "Source 1" }).click();

  const pdfLink = page.getByRole("dialog").getByRole("link");
  await expect(pdfLink).toHaveAttribute("href", /^\/rule-books\/bwf-laws-of-badminton-2025-v5\.0\.pdf#page=\d+$/);

  // Follow the link without its #page part, which only the browser's PDF viewer reads
  const href = await pdfLink.getAttribute("href");
  const response = await request.get(href!.split("#")[0]);
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("application/pdf");
});
