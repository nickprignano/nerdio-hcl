# 0011. Install Nerdio Manager in Terraform; HCL first

- **Status:** Accepted
- **Date:** 2026-10-16
- **Supersedes:** [0003](0003-marketplace-template.md) as the default (the Marketplace path stays
  as `nerdio_install = "marketplace"`)

## Context

The Marketplace path needed a template exported from the portal by hand and Nerdio's install
script, whose "existing AD app" variant runs only in local PowerShell. Neither works from Cloud
Shell on a tablet ([0012](0012-cloud-shell-baseline.md)), and the template uses a SQL admin login
and password and a client secret. Nerdio has no supported unattended install.

## Decision

- **HCL first** as a standing rule: if Terraform can do it, Terraform does it. Scripts are only a
  minimal bootstrap or a stopgap until Terraform can take over.
- `modules/nerdio-core` builds the resources and app settings Nerdio's template and install
  script would create, with safer defaults: Entra-only SQL with an Entra group as admin, Key Vault
  certificates instead of a client secret, Key Vault RBAC, basic publishing auth off.
- The app code is deployed by an Automation job that Terraform starts (`azapi_resource_action`).
  The job runs our own runbook, `nmwUpdateRunAs`, signed in as the account's managed identity. It
  downloads the package from Nerdio's package service (`/api/package`, `/{ver}/link`) and publishes
  `app.zip` to Kudu with an Entra token. Nerdio's in-app updater calls the same runbook by name.
- Names follow Nerdio's template (`nmw-app-<suffix>`, `nmw-app-kv-<suffix>`), because the updater
  derives the web app name from the Key Vault name.

## Consequences

- One `terraform apply` installs Nerdio from Cloud Shell or a pipeline; no portal export.
- The package API is undocumented. If Nerdio changes it, the install job fails until the runbook
  is updated. A documented package API is on the
  [Nerdio asks](../nerdio/upstream-contributions.md#nerdio-api-asks-need-a-nerdio-change-not-a-provider-pr).
- Unverified until the first sandbox run: the job deploys cleanly, SQL group-admin auth works,
  and Nerdio's own updater works with our runbook.
- The setup wizard (directory profile, first run) stays manual; no API exists.
