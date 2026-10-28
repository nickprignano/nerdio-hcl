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

`.github/workflows/validate.yml` runs on pull requests and pushes to `main`:

- `hashicorp/setup-terraform@v3` with an exact `terraform_version` (1.16.6), then
  `terraform fmt -recursive -check`, `terraform validate` on the example root, `terraform test`
  on modules that have tests.
- `terraform-linters/setup-tflint@v4` for tflint.
- `hashicorp/setup-packer@v3` with an exact version (1.16.1), then `packer init`,
  `packer fmt -check` and `packer validate -var-file=example.pkrvars.hcl`.

Tips:

- Pin tool versions exactly in CI and pin actions to a release tag, not `@main`.
- If a local environment can't reach the registry, CI is a fine place to validate against
  providers you can't download locally.

## Post-deployment checks (planned)

Not built yet. Most checks can run through APIs with no browser: Azure resource assertions,
Nerdio's `/host`, `/session`, `/auto-scale`, `/job/{id}` and `/deployment/current` endpoints, and
AVD session host status and health checks through ARM. Only the end-user launch test needs
Playwright (Windows App web client), because no API starts a user session; `WVDConnections` and
`WVDErrors` queries confirm it afterwards. Details and rules are in
[../stack-options.md](../stack-options.md#post-deployment-checks-with-playwright).
