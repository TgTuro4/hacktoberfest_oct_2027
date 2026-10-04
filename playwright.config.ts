import { defineConfig, devices } from "@playwright/test";

const port = process.env.TERPLINK_TEST_PORT || "3100";
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
    { name: "mobile-webkit", use: { ...devices["iPhone 13"] } },
  ],
  webServer: {
    command: `npm run start -- --hostname 127.0.0.1 --port ${port}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { SNOWFLAKE_BACKEND_ENABLED:"false", SNOWFLAKE_APP_TOKEN:"", SESSION_SECRET:"", SNOWFLAKE_SEARCH_TOKEN: "", SNOWFLAKE_ACCOUNT: "", SNOWFLAKE_USERNAME: "", SNOWFLAKE_PASSWORD: "", SNOWFLAKE_PRIVATE_KEY_PATH: "" },
  },
});
