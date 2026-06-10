import { expect, test } from "@playwright/test";

test("mission control loads seeded project and scenario controls", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Mission Control Console" })).toBeVisible();
  await expect(page.getByText("TeamSync Platform")).toBeVisible();
  await expect(page.getByRole("button", { name: "Trigger Workflow Violation" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Swagger" })).toHaveAttribute("href", "/docs");
});

test("workflow violation scenario shows allowed transition", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Trigger Workflow Violation" }).click();
  await expect(page.getByText(/Workflow violation 422/)).toBeVisible();
  await expect(page.getByText(/allowed In Progress/)).toBeVisible();
});

test("search scenario runs through the UI", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Search Carry Work" }).click();
  await expect(page.getByText(/Search returned/)).toBeVisible();
});
