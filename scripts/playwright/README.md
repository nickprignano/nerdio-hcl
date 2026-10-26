# Optional Playwright Wizard & E2E Verification (`scripts/playwright/`)

Nerdio Manager's first-run setup wizard has two steps without a public write API
([platform.md](../../docs/knowledge/nerdio/platform.md#setup-wizard-manual)):

1. Selecting the directory profile (Entra ID, Active Directory, or Entra Domain Services)
2. Completing the first-run registration screen

Everything else (Entra app registration, admin consent grants, Key Vault secrets, linked networks,
linked resource groups, host pools, FSLogix, and RBAC) is automated in Terraform across Stages 1
and 2.

This folder provides an **opt-in** Playwright scaffold for:

- `wizard-complete.spec.ts`: Completing the remaining browser-only wizard prompt using an
  operator-supplied Playwright `storageState`.
- `session-launch.spec.ts`: Post-deployment synthetic verification that an assigned desktop or
  RemoteApp appears in the Windows App web client (`https://windows.cloud.microsoft`).

## Usage

```bash
cd scripts/playwright
npm install
npx playwright install chromium

# Run E2E feed verification with an authenticated storage state
PLAYWRIGHT_AVD_STORAGE_STATE=auth.json AVD_EXPECTED_RESOURCE_NAME="SessionDesktop" npm run test:launch
```

> **Guardrail**: Never store real URLs, tenant IDs, usernames, or `storageState` files in the
> repository. Pass `NERDIO_URL` and `PLAYWRIGHT_*` paths via environment variables at runtime.
