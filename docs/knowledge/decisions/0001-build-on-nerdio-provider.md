---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0001. Build the kit on Nerdio's own Terraform provider

## Context and Problem Statement

The first draft of the kit used only azurerm/azuread: it built the landing zone, deployed Nerdio
from the Marketplace and stopped at Nerdio's setup wizard. Everything inside Nerdio (host pools,
profiles, scripted actions) was left as console work. How should the kit manage what lives inside
Nerdio?

## Considered Options

- Use Nerdio's own provider, `nerdio/nme`, which manages Nerdio objects through its REST API
- Call Nerdio's REST API directly from scripts or workflows
- Leave Nerdio configuration as console work

## Decision Outcome

Chosen option: "Use `nerdio/nme`", because showing a Nerdio deployment done the HashiCorp way,
including Nerdio's own configuration, is the point of the project.

Layout: a platform stage (azurerm/azuread) and a Nerdio configuration stage (`nerdio/nme`), each
with its own state. The platform stage's outputs feed the second stage as a tfvars JSON file.

### Consequences

- Good, because host pools, auto-scale, FSLogix/RDP profiles, scripted actions and user
  assignments become code.
- Bad, because the provider is early (0.x, "under heavy development"), so expect schema changes
  and pin it exactly.
- Bad, because the REST API client app must exist before the second stage can run.
- Bad, because coverage gaps (session hosts, app groups, RemoteApps, MSIX, schedules) stay manual.
  See [../nerdio/terraform-provider.md](../nerdio/terraform-provider.md#gaps).
