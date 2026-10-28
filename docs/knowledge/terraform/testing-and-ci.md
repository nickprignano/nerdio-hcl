---
title: "Testing and CI"
summary: "terraform test, tflint, the CI workflow and planned post-deploy checks"
topic: terraform
status: verified
last_reviewed: 2026-10-27
---

# Testing and CI

## terraform test

- Module tests with a mocked provider work without Azure credentials:

  ```hcl
  mock_provider "azurerm" {}

  run "plan" {
    command = plan
    # assertions...
  }
  ```

- Only plan-time values are checkable this way; anything computed by Azure is unknown.
- **`mock_provider "azapi" {}` vs `terraform validate`:** `mock_provider "azapi" {}` in
  `terraform test` bypasses `Azure/azapi` v2's embedded ARM schema validator on
  `azapi_resource.body`. Only `terraform validate` (with the real `azapi` provider binary
  initialized in the root module) checks `body` against the embedded API version schema.
  For example, in `Microsoft.AzureStackHCI@2024-01-01`:
  - `Microsoft.AzureStackHCI/logicalNetworks@2024-01-01` requires static routes under
    `properties.subnets[].properties.routeTable.properties.routes` (passing
    `properties.subnets[].properties.routes` directly fails `terraform validate`).
  - `Microsoft.AzureStackHCI/galleryImages@2024-01-01` removed
    `properties.vmImageRepositoryCredentials` in GA `2024-01-01` and fails schema validation
    even when set to `null`.
- **Opt-in child modules (`count = 0`) and provider constraints:** Even when a child module is
  disabled (`default = null`, `count = 0`), `terraform init` intersects its `required_providers`
  constraints with the root module's constraints. A child module pinning `~> 4.0` breaks
  `terraform init` for a root module on `~> 5.0`. Always use floor constraints (`>= 5.0` for
  `azurerm`, `>= 2.0` for `azapi`) in `modules/*/versions.tf`.
- **`terraform fmt` alignment around multi-line `optional(object({...}))`:** Inside an outer
  `object({...})` type definition, a multi-line `attr = optional(object({ ... }))` block splits
  `terraform fmt`'s `=` column alignment into separate vertical groups above and below the nested
  block. Single-line attributes immediately following `}))` align only with their own contiguous
  group.

## tflint

`.tflint.hcl` uses the `terraform` plugin with the `recommended` preset and the azurerm ruleset
(0.30.0 at last review). Run `tflint --init` then `tflint --recursive --minimum-failure-severity=error`.

## CI workflow

`.github/workflows/terraform.yml` and `.github/workflows/validate.yml` run on pull requests and pushes to `main`:

- `hashicorp/setup-terraform@v3` with an exact `terraform_version` (1.16.6), then
  `terraform fmt -recursive -check`, `terraform validate` on each stage and module, and `terraform test`
  on modules that have tests.
- `terraform-linters/setup-tflint@v4` for tflint.
- `shellcheck scripts/pipeline/*.sh github/settings.sh` at default severity (`info` and above).
- `hashicorp/setup-packer@v3` with an exact version (1.16.1), then `packer init`,
  `packer fmt -check` and `packer validate`.

Tips:

- Pin tool versions exactly in CI and pin actions to a release tag, not `@main`.
- If a local environment can't reach the registry, CI is a fine place to validate against
  providers you can't download locally.
- **ShellCheck `SC2015` (`A && B || C`):** Because CI runs `shellcheck` without `-S warning`,
  chained `[ cond1 ] && [ cond2 ] || { ... }` triggers `SC2015 (info)` and fails the job. Always
  write `if [ ... ] || [ ... ]; then ...; fi` in `scripts/pipeline/*.sh` and `github/settings.sh`.
- **Pipeline ABAC `apply_assignable_roles`:** `modules/deploy-pipeline` constrains the `apply`
  identity's `Role Based Access Control Administrator` assignment with an Azure ABAC condition
  limiting `RoleDefinitionId` to `apply_assignable_roles`. Whenever a stage or module adds an
  `azurerm_role_assignment` (for example `00-assistant` assigning `Cognitive Services User`,
  `Storage Blob Data Contributor`, and `Storage Blob Data Reader`), add the role name to
  `apply_assignable_roles` in `modules/deploy-pipeline/variables.tf` or `terraform apply` in the
  pipeline will fail with `RoleAssignmentUpdateNotPermitted`.
- **Microsoft Graph `/me` vs `/users/{id}` in OIDC pipelines:** `GET https://graph.microsoft.com/v1.0/me`
  works only for delegated user tokens (interactive Cloud Shell) and fails under app-only OIDC
  service principals. Shared CLI/pipeline code (`./nerdio fix quota`) must catch errors on `/me`
  and fall back to `GET /v1.0/users/{object-id}` using the admin's Entra object ID from
  `answers/<env>.json` (readable via `Directory.Read.All`) or an explicit contact override.
- **Anthropic tool schemas with optional parameters:** In the Anthropic Messages API, setting
  `"strict": true` on a tool definition requires every property in `input_schema.properties` to
  appear in `required`. Omit `"strict": true` on tools that accept optional inputs (such as
  `pipeline_start`, `pipeline_plan`, and `set_answers`).

## Post-deployment checks

Stage `verify` in `.github/workflows/deploy.yml` runs `./nerdio preflight --stage post-wizard`
as the read-only plan identity, evaluating post-install and post-wizard readiness checks (`nme.*`,
`avd.*`, `id.*`, and Terraform `check` blocks from `01-platform` state). For end-user session
launch and wizard automation, `scripts/playwright/` provides opt-in Playwright specs
(`session-launch.spec.ts` and `wizard-complete.spec.ts`). Details and rules are in
[../stack-options.md](../stack-options.md#post-deployment-checks-with-playwright).
