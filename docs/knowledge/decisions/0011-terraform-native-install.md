---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0011. Install Nerdio Manager in Terraform; HCL first

## Context and Problem Statement

The Marketplace path ([0003](0003-marketplace-template.md)) needed a template exported from the
portal by hand and Nerdio's install script, whose "existing AD app" variant runs only in local
PowerShell. Neither works from Cloud Shell on a tablet ([0012](0012-cloud-shell-baseline.md)), and
the template uses a SQL admin login and password and a client secret. Nerdio has no supported
unattended install. How should the kit install Nerdio Manager?

## Considered Options

- Keep the exported Marketplace template plus Nerdio's install script
- Build Nerdio Manager's resources in Terraform and deploy the app code with an Automation job
- Wait for Nerdio to ship a supported unattended install

## Decision Outcome

Chosen option: "Build it in Terraform", because one `terraform apply` can then install Nerdio
from Cloud Shell or a pipeline, with safer defaults than the template.

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

### Consequences

- Good, because one `terraform apply` installs Nerdio from Cloud Shell or a pipeline, with no
  portal export.
- Good, because there is no SQL password or client secret.
- Bad, because the package API is undocumented. If Nerdio changes it, the install job fails until
  the runbook is updated. A documented package API is on the
  [Nerdio asks](../nerdio/upstream-contributions.md#nerdio-api-asks-need-a-nerdio-change-not-a-provider-pr).
- Bad, because the setup wizard (directory profile, first run) stays manual; no API exists.
- Neutral, because the Marketplace path stays available as `nerdio_install = "marketplace"`.

## More Information

Supersedes [0003](0003-marketplace-template.md) as the default.

*Unverified* until the first sandbox run: the job deploys cleanly, SQL group-admin auth works,
and Nerdio's own updater works with our runbook.
