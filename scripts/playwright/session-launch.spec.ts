import { test, expect } from "@playwright/test";

/**
 * Opt-in E2E synthetic verification that an AVD test user can enumerate their workspace feed
 * in the Windows App web client (https://windows.cloud.microsoft).
 *
 * Preconditions:
 *   - PLAYWRIGHT_AVD_STORAGE_STATE points to an authenticated session for the test user
 *   - AVD_EXPECTED_RESOURCE_NAME names the Desktop or RemoteApp expected in the feed
 */
test.describe("AVD Windows App web client feed verification", () => {
  test.use({
    storageState: process.env.PLAYWRIGHT_AVD_STORAGE_STATE || undefined,
  });

  test("enumerates assigned desktop or application in Windows App web client", async ({ page }) => {
    const expectedName = process.env.AVD_EXPECTED_RESOURCE_NAME;
    test.skip(!expectedName, "AVD_EXPECTED_RESOURCE_NAME is required for E2E feed verification");

    await page.goto("https://windows.cloud.microsoft");
    await expect(page.getByText(expectedName!, { exact: false }).first()).toBeVisible();
  });
});
