import { test, expect } from "@playwright/test";

const remoteCard = { id: "snowflake:group:123", kind: "group", title: "K-pop AI Test Club", description: "A fictional club returned by the mocked search endpoint.", tags: ["K-pop"], location: "Stamp", date: "", time: "", meetingDetails: "Fridays", demo: true, color: 1, createdAt: "2026-10-04T12:00:00Z" };

test("AI search imports ranked cards, persists interested decisions and keeps local browse available", async ({ page }) => {
  await page.route("**/api/recommendations", async route => {
    const body = route.request().postDataJSON();
    expect(body.profile.major).toBe("Computer Science");
    expect(body.profile.name).toBeUndefined();
    const items = body.excludedIds.includes(remoteCard.id) ? [] : [remoteCard];
    await route.fulfill({ json: { source: "snowflake", items } });
  });
  await page.goto("/discover");
  await page.getByRole("button", { name: "Personalize with AI" }).click();
  await expect(page.getByRole("heading", { name: remoteCard.title })).toBeVisible();
  await page.getByRole("button", { name: "Interested", exact: true }).click();
  await page.goto("/saved");
  await expect(page.getByRole("heading", { name: remoteCard.title })).toBeVisible();
  await page.goto("/discover");
  await page.getByRole("button", { name: "Personalize with AI" }).click();
  await expect(page.getByText("No matching cards in this catalog.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Browse all local cards" }).click();
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
});

test("unconfigured live API reports a clear error without breaking local cards", async ({ page, request }) => {
  const response = await request.post("/api/recommendations", { data: { profile: { major: "CS", bio: "", interests: ["AI"] }, kind: "all", excludedIds: [] } });
  expect(response.status()).toBe(503);
  await page.goto("/discover");
  await page.getByRole("button", { name: "Personalize with AI" }).click();
  await expect(page.getByText("AI discovery is not connected yet.", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
});

test("API validates input and content type", async ({ request }) => {
  expect((await request.post("/api/recommendations", { data: { profile: {}, kind: "all", excludedIds: [] } })).status()).toBe(400);
  expect((await request.post("/api/recommendations", { data: "hello", headers: { "Content-Type": "text/plain" } })).status()).toBe(415);
});
