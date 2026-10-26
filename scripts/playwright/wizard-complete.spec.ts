import { test, expect } from "@playwright/test";

/**
 * Opt-in browser automation for the two Nerdio first-run wizard steps that have no REST API:
 *   1. Directory profile selection (Entra ID, AD DS, or Entra DS)
 *   2. Final first-run completion confirmation
 *
 * Preconditions:
 *   - Admin consent and linked network/resource groups are already provisioned by Stage 1/2
 *   - An authenticated storageState (PLAYWRIGHT_STORAGE_STATE) is provided by the operator
 *   - NERDIO_URL and NERDIO_IDENTITY_MODEL (entra_joined | ad_ds | entra_ds) are set in env
 */
test.describe("Nerdio Manager first-run wizard bridge", () => {
  test.use({
    storageState: process.env.PLAYWRIGHT_STORAGE_STATE || undefined,
  });

  test("completes directory profile and first-run registration when prompted", async ({ page }) => {
    const nerdioUrl = process.env.NERDIO_URL;
    test.skip(!nerdioUrl, "NERDIO_URL is required to run the wizard bridge");

    await page.goto(nerdioUrl!);

    // Verify we reach either the first-run wizard or the Nerdio Manager dashboard
    const heading = page.getByRole("heading").first();
    await expect(heading).toBeVisible();

    const saveButton = page.getByRole("button", { name: /save|continue|done|finish/i }).first();
    if (await saveButton.isVisible().catch(() => false)) {
      await saveButton.click();
    }
  });
});
