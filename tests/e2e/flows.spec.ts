import { test, expect, type Page } from "@playwright/test";

async function ready(page: Page, path = "/discover") {
  await page.goto(path);
  await expect(page.getByRole("button", { name: "Reset demo" })).toBeVisible();
  await expect(page.getByText("Getting your campus ready…")).toHaveCount(0);
}

test("home welcomes users and discovery has its own focused route", async ({ page }) => {
  await ready(page, "/");
  await expect(page.getByRole("heading", { name: "Less scrolling. More belonging." })).toBeVisible();
  await expect(page.getByText("left to discover", { exact: true })).toBeVisible();
  await expect(page.getByText("sparks of interest", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "A little curiosity goes a long way." })).toBeVisible();
  await expect(page.getByTestId("swipe-card")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Groups", exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Home", exact: true })).toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "Start discovering", exact: true }).click();
  await expect(page).toHaveURL(/\/discover$/);
  await expect(page.getByTestId("swipe-card")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Less scrolling. More belonging." })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Discover", exact: true })).toHaveAttribute("aria-current", "page");
  await page.getByRole("button", { name: "Interested", exact: true }).click();
  await expect(page.getByRole("heading", { name: "One more round?" })).toBeVisible();
  await page.getByRole("link", { name: "Home", exact: true }).click();
  await expect(page.locator(".discovery-stats strong")).toHaveText(["07", "01"]);
  await page.getByRole("link", { name: "See your saved finds", exact: true }).click();
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
});

test("swipe buttons, filters, saved removal and persistence", async ({ page }) => {
  await ready(page);
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
  await page.getByRole("button", { name: "Interested", exact: true }).click();
  await expect(page.getByRole("heading", { name: "One more round?" })).toBeVisible();
  await page.getByRole("button", { name: "Groups", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Take the scenic route" })).toBeVisible();
  await page.getByRole("button", { name: "Pass", exact: true }).click();
  await expect(page.getByRole("heading", { name: "A little creative chaos" })).toBeVisible();
  await page.getByRole("button", { name: "Events", exact: true }).click();
  await expect(page.getByRole("heading", { name: "One more round?" })).toBeVisible();
  await page.getByRole("link", { name: "Saved", exact: true }).click();
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
  await page.getByRole("button", { name: "Remove The Debug Club from saved" }).click();
  await expect(page.getByRole("heading", { name: "A little room for possibility." })).toBeVisible();
  await page.getByRole("link", { name: "Discover", exact: true }).click();
  await expect(page.getByRole("heading", { name: "One more round?" })).toBeVisible();
});

test("manual event/group validation and publication", async ({ page }) => {
  await ready(page, "/create");
  await page.getByRole("button", { name: "Publish event", exact: true }).click();
  expect(await page.getByLabel("Event title").evaluate((input: HTMLInputElement) => input.validity.valueMissing)).toBe(true);
  await expect(page.getByRole("status").filter({ hasText: "is published" })).toHaveCount(0);
  await page.getByLabel("Event title").fill("Campus test meetup");
  await page.getByLabel("Location", { exact: false }).fill("Iribe lobby");
  await page.getByLabel("Date", { exact: false }).fill("2026-10-20");
  await page.getByLabel("Time", { exact: true }).fill("18:30");
  await page.getByRole("button", { name: "Publish event", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "is published" })).toBeVisible();
  await page.getByRole("link", { name: "Discover", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Campus test meetup" })).toBeVisible();
  await expect(page.getByText("Oct 20, 2026 · 6:30 PM")).toBeVisible();
  await page.getByRole("link", { name: "Create", exact: true }).click();
  await page.getByRole("button", { name: "Create a group", exact: true }).click();
  await page.getByLabel("Group name").fill("A new study crew");
  await page.getByRole("button", { name: "Publish group", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "is published" })).toHaveCount(0);
  await page.getByLabel("Description").fill("We study together and compare notes.");
  await page.getByRole("button", { name: "Publish group", exact: true }).click();
  await page.getByRole("link", { name: "Discover", exact: true }).click();
  await expect(page.getByRole("heading", { name: "A new study crew" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "A new study crew" })).toBeVisible();
});

test("sample multi-draft prefill stays editable and never auto-publishes", async ({ page }) => {
  await ready(page, "/create");
  await page.getByRole("button", { name: "Load sample announcement" }).click();
  await page.getByRole("button", { name: "Prefill with AI", exact: true }).click();
  await expect(page.getByText("Sample demo · Not an AI result")).toBeVisible();
  await expect(page.getByLabel("Event title")).toHaveValue("");
  const before = await page.evaluate(() => JSON.parse(localStorage.getItem("terplink.demo.v1")!).items.length);
  expect(before).toBe(8);
  await page.getByRole("button", { name: /event · draft Terp Builders Meetup/ }).click();
  await expect(page.getByLabel("Event title")).toHaveValue("Terp Builders Meetup");
  await page.getByLabel("Event title").fill("Reviewed builders meetup");
  await page.getByRole("button", { name: "Publish event", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Reviewed builders meetup" })).toBeVisible();
  await page.getByRole("button", { name: /group · draft Trail Terps/ }).click();
  await expect(page.getByLabel("Group name")).toHaveValue("Trail Terps");
  await expect(page.getByLabel("Location", { exact: false })).toHaveValue("");
  await expect(page.getByLabel("Recurring meeting details", { exact: false })).toHaveValue("");
  await page.getByRole("button", { name: "Publish group", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Trail Terps" })).toBeVisible();
  const after = await page.evaluate(() => JSON.parse(localStorage.getItem("terplink.demo.v1")!).items.length);
  expect(after).toBe(10);
  await page.getByLabel("Announcement", { exact: true }).fill("Arbitrary new announcement, tomorrow at noon");
  await page.getByRole("button", { name: "Prefill with AI", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Snowflake isn’t configured");
});

test("profile saves across reload and reset needs confirmation", async ({ page }) => {
  await ready(page, "/profile");
  await page.getByLabel("Display name").fill("Taylor Terp");
  await page.getByLabel("Major", { exact: true }).fill("Design");
  await page.getByLabel("Short bio").fill("Ready to make things.");
  await page.getByLabel("Interest tags").fill("Art, Hiking, Games");
  await page.getByLabel("Availability", { exact: false }).fill("Friday evenings");
  await page.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Profile saved");
  await page.reload();
  await expect(page.getByLabel("Display name")).toHaveValue("Taylor Terp");
  await expect(page.getByLabel("Interest tags")).toHaveValue("Art, Hiking, Games");
  await page.evaluate(() => localStorage.setItem("other-app", "untouched"));
  page.once("dialog", dialog => dialog.dismiss());
  await page.getByRole("button", { name: "Reset demo" }).click();
  await expect(page.getByLabel("Display name")).toHaveValue("Taylor Terp");
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Reset demo" }).click();
  await expect(page.getByLabel("Display name")).toHaveValue("Alex Morgan");
  expect(await page.evaluate(() => localStorage.getItem("other-app"))).toBe("untouched");
});

test("short drags reset, long drags decide, cancellation never decides", async ({ page }) => {
  await ready(page);
  const card = page.getByTestId("swipe-card");
  await card.scrollIntoViewIfNeeded();
  const box = (await card.boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + 100;
  await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.move(x + 40, y, { steps: 5 }); await page.mouse.up();
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
  await expect(card).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
  await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.move(x + 130, y, { steps: 8 });
  await card.dispatchEvent("pointercancel", { pointerId: 1, isPrimary: true, clientX: x + 130, clientY: y });
  await page.mouse.up();
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
  await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.move(x + 130, y, { steps: 8 }); await page.mouse.up();
  await expect(page.getByRole("heading", { name: "One more round?" })).toBeVisible();
  await page.getByRole("link", { name: "Saved", exact: true }).click();
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
});

test("all cards can be decided and empty state is useful", async ({ page }) => {
  await ready(page);
  for (let i = 0; i < 8; i++) {
    await page.getByRole("button", { name: "Pass", exact: true }).click();
    await expect(page.getByTestId("swipe-card")).toHaveCount(i < 7 ? 1 : 0);
    if (i < 7) await expect(page.getByRole("button", { name: "Pass", exact: true })).toBeEnabled();
  }
  await expect(page.getByRole("heading", { name: "You made the rounds." })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "You made the rounds." })).toBeVisible();
});

test("flyer validation and preview clearly disclose no image extraction", async ({ page }) => {
  await ready(page, "/create");
  await expect(page.getByText("Image AI extraction is unavailable.", { exact: true })).toBeVisible();
  const upload = page.getByLabel("Upload event flyer");
  await upload.setInputFiles({ name: "bad.txt", mimeType: "text/plain", buffer: Buffer.from("bad") });
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Choose a JPEG");
  await upload.setInputFiles({ name: "big.png", mimeType: "image/png", buffer: Buffer.alloc(3 * 1024 * 1024 + 1) });
  await expect(page.getByRole("main").getByRole("alert")).toContainText("too large");
  const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=";
  await upload.setInputFiles({ name: "preview.png", mimeType: "image/png", buffer: Buffer.from(png, "base64") });
  await expect(page.getByAltText("Your uploaded flyer preview")).toBeVisible();
  await page.getByRole("button", { name: "Remove preview" }).click();
  await expect(page.getByAltText("Your uploaded flyer preview")).toHaveCount(0);
});

test("storage failures do not advance the card or pretend to save", async ({ page }) => {
  await ready(page);
  await page.evaluate(() => { Storage.prototype.setItem = () => { throw new DOMException("full", "QuotaExceededError"); }; });
  await page.getByRole("button", { name: "Interested", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("couldn’t be saved");
  await expect(page.getByRole("heading", { name: "The Debug Club" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Interested", exact: true })).toBeEnabled();
});

test("prefill API bounds input and handles malformed requests", async ({ request }) => {
  const arbitrary = await request.post("/api/prefill", { data: { text: "Meetup tomorrow" } });
  expect(arbitrary.status()).toBe(503);
  const empty = await request.post("/api/prefill", { data: { text: " " } });
  expect(empty.status()).toBe(400);
  const oversized = await request.post("/api/prefill", { data: { text: "a".repeat(8001) } });
  expect(oversized.status()).toBe(413);
  const huge = await request.post("/api/prefill", { data: { text: "a".repeat(50_000) } });
  expect(huge.status()).toBe(413);
  const malformed = await request.post("/api/prefill", { data: "{broken", headers: { "content-type": "application/json" } });
  expect(malformed.status()).toBe(400);
  const wrongType = await request.post("/api/prefill", { data: "text", headers: { "content-type": "text/plain" } });
  expect(wrongType.status()).toBe(415);
});

test("mobile native touch swipes and vertical page scrolling", async ({ page, context, isMobile, browserName }) => {
  test.skip(!isMobile || browserName !== "chromium", "CDP native touch injection is available only in mobile Chromium.");
  await ready(page);
  const client = await context.newCDPSession(page);
  const card = page.getByTestId("swipe-card");
  await card.scrollIntoViewIfNeeded();
  let box = (await card.boundingBox())!;
  const x = box.x + box.width / 2;
  let y = box.y + 100;
  await client.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
  for (let i = 1; i <= 8; i++) {
    await client.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: x + i * 16, y }] });
    await page.waitForTimeout(20);
  }
  await client.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await expect(page.getByRole("heading", { name: "One more round?" })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  box = (await card.boundingBox())!;
  y = Math.min(box.y + 130, 650);
  await client.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
  for (let i = 1; i <= 8; i++) {
    await client.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: y - i * 24 }] });
    await page.waitForTimeout(20);
  }
  await client.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(30);
  await expect(page.getByRole("heading", { name: "One more round?" })).toBeVisible();
});

test("layout fits viewport and screenshots cover key screens", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  for (const path of ["/", "/discover", "/create", "/saved", "/profile"]) {
    await ready(page, path);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/terplink-${info.project.name}-${path === "/" ? "home" : path.slice(1)}.png`, fullPage: true });
  }
  expect(errors).toEqual([]);
});
