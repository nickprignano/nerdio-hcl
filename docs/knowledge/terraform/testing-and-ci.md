---
title: "Testing and CI"
summary: "terraform test, tflint, the CI workflow and planned post-deploy checks"
topic: terraform
status: verified
last_reviewed: 2026-11-10
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
- **Child-module `check` blocks (`check "nerdio_health"`), module splats (`module.foo[*]`), and `terraform test` teardown cycles:**
  In Terraform's graph, `(execute checks)` runs after every managed resource, and a `check` block
  inside a child module (`module.nerdio_core.check.nerdio_health`) is enclosed by
  `module.nerdio_core (close)`. Two distinct graph cycles can arise:
  1. **Plan-time splat/key cycle:** If a downstream managed resource or module depends on a local
     that uses a module splat (`module.nerdio_core[*].<output>`) or uses `for_each` map keys
     computed from data sources inside `module.nerdio_core`, Terraform creates a plan-time cycle
     (`managed_resource -> (execute checks) -> check -> module.nerdio_core (close) -> managed_resource`).
     Always index conditional modules directly (`var.nerdio_install == "terraform" ? module.nerdio_core[0].<output> : module.nerdio_manager[0].<output>`)
     and use static plan-time `for_each` keys (`"rg-nerdio"`, `"kv-nme-secrets"`, `"kv-cmk"`, `"fslogix-${k}"`).
  2. **Teardown (`command = apply`) cycle in `terraform test`:** When a `terraform test` `run` block
     executes `command = apply` (such as `run "marketplace_discovers_existing"` in `01-platform`),
     Terraform constructs a destroy graph after the run finishes to clean up state. In the destroy
     graph, resource dependency edges are reversed (so any resource inside `module.nerdio_core`
     waits on a root resource `azurerm_management_lock.stateful (destroy)` that depended on
     `module.nerdio_core` outputs), while `(execute checks) -> module.nerdio_core.check.nerdio_health (expand) -> module.nerdio_core (close)`
     remains forward. Never make a root-module managed resource depend on outputs of a child module
     that contains a `check` block; instead, lock the parent `nerdio` resource group
     (`module.foundation.resource_group_ids["nerdio"]`) directly, as Azure `CanNotDelete` locks on a
     resource group automatically inherit down to every child resource inside it.
- **Container Apps VNet subnet sizing (`/23` legacy vs `/27` Consumption workload profile):**
  `azurerm_container_app_environment` with `infrastructure_subnet_id` defaults to the legacy
  Consumption architecture when no `workload_profile` block is declared, requiring at least a `/23`
  subnet (512 IPs). Declaring `workload_profile { name = "Consumption", workload_profile_type = "Consumption" }`
  on the environment and `workload_profile_name = "Consumption"` on `azurerm_container_app_job`
  switches to Workload Profiles, which requires only a `/27` subnet (32 IPs) delegated to
  `Microsoft.App/environments`.
- **KEDA `github-runner` scaler and `actions-runner` container environment variables:**
  In `modules/vnet-runner`, KEDA's `github-runner` rule uses `trigger_parameter = "personalAccessToken"`
  for PATs and `trigger_parameter = "appKey"` (plus `applicationID` and `installationID` in `metadata`)
  for GitHub Apps. Inside the `ghcr.io/actions/actions-runner` container, environment variable names
  are case-sensitive: PAT mode requires `ACCESS_TOKEN` (all caps — `ACCESS_token` is silently ignored
  and fails runner registration), while GitHub App mode requires `APP_ID`, `APP_INSTALLATION_ID`, and
  `APP_PRIVATE_KEY`.

## tflint

`.tflint.hcl` uses the `terraform` plugin with the `recommended` preset and the azurerm ruleset
(0.30.0 at last review). Run `tflint --init` then `tflint --recursive --minimum-failure-severity=error`.

## CI workflow

`.github/workflows/terraform.yml` and `.github/workflows/validate.yml` run on pull requests and pushes to `main`:

- `hashicorp/setup-terraform@v3` with an exact `terraform_version`
  ([1.16.6](https://github.com/hashicorp/terraform/releases/tag/v1.16.6);
  [1.16.7](https://github.com/hashicorp/terraform/releases/tag/v1.16.7) and
  [1.17.0](https://github.com/hashicorp/terraform/releases/tag/v1.17.0) are also available), then
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
- **ShellCheck `SC2015` (`A && B || C`) and `SC2016` (backticks in single quotes):** Because CI
  runs `shellcheck` without `-S warning`, chained `[ cond1 ] && [ cond2 ] || { ... }` triggers
  `SC2015 (info)` and single-quoted strings containing Markdown backticks (such as
  `echo 'Skipped: `01-platform`'`) trigger `SC2016 (info): Expressions don't expand in single quotes`.
  Always write `if [ ... ] || [ ... ]; then ...; fi` and use Markdown bold (`**01-platform**`) or
  HTML `<code>...</code>` tags instead of backticks in `scripts/pipeline/*.sh` and `github/settings.sh`.
- **Trivy `config` CLI target and GitHub provider rules (`AVD-GIT-0001..0003`):**
  `trivy config` accepts only a single target directory (`trivy config [flags] DIR`) and fails with
  `FATAL multiple targets cannot be specified` if multiple directories are passed; scan `.` with
  `--misconfig-scanners terraform --tf-exclude-downloaded-modules`. Trivy's `AVD-GIT-0002` flags any
  `github_actions_environment_secret` resource with `plaintext_value`, even when used to store
  non-secret Azure resource/tenant GUIDs so GitHub Actions masks them in public logs per Guardrail 4;
  document intentional architectural exceptions in `.trivyignore`.
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
- **`schema/parameters.json` `tfvars` paths into `map(object(...))` attributes:**
  `SchemaTests.test_every_tfvar_target_is_a_declared_variable` in `scripts/nerdio/test_nerdio.py`
  verifies every literal segment in `tfvars[*].path` after the top-level variable name against
  `tfcheck.attribute_declared(block, attr)` unless the segment starts with `{` (or `top == "tags"`).
  When a parameter writes into a `map(object(...))` attribute (such as `host_pools` or
  `avd_insights.webhook_receivers`), always use a `{...}` placeholder for the map key (for example
  `avd_insights.webhook_receivers.{prefix}.service_uri`).
- **Pinning legacy Python 3.9 CI jobs to `ubuntu-24.04`:** GitHub Actions rolled `ubuntu-latest` to
  Ubuntu 26.04, and `actions/python-versions` does not build EOL Python 3.9 for Ubuntu 26.04. Jobs
  that intentionally verify Python 3.9 compatibility (`preflight-zipapp` in
  `.github/workflows/validate.yml` and `release` in `.github/workflows/preflight-release.yml`) must
  pin `runs-on: ubuntu-24.04` rather than floating on `ubuntu-latest`.
- **`httpx` / `anthropic` SDK vs IPv6 brackets in `NO_PROXY`:** In environments where `NO_PROXY`
  includes `[::1]`, `httpx`'s proxy mount parser raises `InvalidURL: Invalid port: ':1]'` when
  `anthropic.Anthropic()` initializes. Override `NO_PROXY="localhost,127.0.0.1"` when running
  `python3 -m unittest discover -s assistant`.

## CI/CD pipeline lessons (decision 0033)

- **Bicep what-if needs an action Reader doesn't have.** `az deployment sub what-if` calls
  `Microsoft.Resources/deployments/whatIf/action`; Reader is `*/read` only. By default what-if
  also checks write rights on every resource. `--validation-level ProviderNoRbac` (Azure CLI 2.76+)
  checks read rights instead, so a read-only identity plus a custom role with only `whatIf/action`
  and `validate/action` can preview (`plan_bicep_whatif`; not yet verified live).
- **ARM has no stale-plan refusal.** Terraform refuses a saved plan once state moves; ARM deploys
  whatever template it gets. `stage.sh` re-runs what-if as the apply identity and refuses when the
  change list differs from the reviewed one.
- **Deployment stacks and Graph Bicep:** Microsoft Graph Bicep resources aren't supported in
  deployment stacks or what-if, so Entra objects need a separate, non-stack deployment.
- **Reusable workflows in a matrix don't return per-leg outputs.** A caller only sees one leg's
  `outputs`; `drift.yml` passes each leg's result as a small artifact instead.
- **Environment secrets in reusable workflows:** a called workflow's job that names the
  `environment` reads that environment's secrets itself; callers can't pass them, and
  `secrets: inherit` isn't needed for them. The caller job must still grant `id-token: write`.
- **Fork pull requests get no OIDC token or secrets**, so plan-on-PR skips them up front instead
  of failing at sign-in.
- **actionlint runs ShellCheck on `run:` blocks** when `shellcheck` is on `PATH` (it is on
  GitHub-hosted runners), so an intentional word split needs a `# shellcheck disable=` comment.
- **CRLF workflow files:** `configure.yml` has CRLF endings; a `sed` anchored on `$` won't match
  those lines, and a plain replacement drops the `\r` on the lines it touches.

## Post-deployment checks

Stage `verify` in `.github/workflows/deploy.yml` runs `./nerdio preflight --stage post-wizard`
as the read-only plan identity, evaluating post-install and post-wizard readiness checks (`nme.*`,
`avd.*`, `id.*`, and Terraform `check` blocks from `01-platform` state). For end-user session
launch and wizard automation, `scripts/playwright/` provides opt-in Playwright specs
(`session-launch.spec.ts` and `wizard-complete.spec.ts`). Details and rules are in
[../stack-options.md](../stack-options.md#post-deployment-checks-with-playwright).
