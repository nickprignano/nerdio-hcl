# 0001. Build the kit on Nerdio's own Terraform provider

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

The first draft of the kit used only azurerm/azuread: it built the landing zone, deployed Nerdio
from the Marketplace and stopped at Nerdio's setup wizard. Everything inside Nerdio (host pools,
profiles, scripted actions) was left as console work. Nerdio publishes its own provider,
`nerdio/nme`, which manages those objects through Nerdio's REST API.

## Decision

The kit is built around `nerdio/nme`. Showing a Nerdio deployment done the HashiCorp way,
including Nerdio's own configuration, is the point of the project.

Layout: a platform stage (azurerm/azuread) and a Nerdio configuration stage (`nerdio/nme`), each
with its own state. The platform stage's outputs feed the second stage as a tfvars JSON file.

## Consequences

- Host pools, auto-scale, FSLogix/RDP profiles, scripted actions and user assignments become code.
- The provider is early (0.x, "under heavy development"), so expect schema changes and pin it exactly.
- The REST API client app must exist before the second stage can run.
- Coverage gaps (session hosts, app groups, RemoteApps, MSIX, schedules) stay manual.
  See [../nerdio/terraform-provider.md](../nerdio/terraform-provider.md#gaps).
