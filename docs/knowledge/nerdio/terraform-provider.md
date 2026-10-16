# Nerdio Terraform provider (`nerdio/nme`)

Nerdio's own provider configures Nerdio Manager through its REST API: host pools, profiles,
scripted actions and linked Azure resources. It does **not** deploy Nerdio Manager itself;
that still comes from the Marketplace (see [platform.md](platform.md)).

- Source: https://github.com/Get-Nerdio/NME-Terraform-Provider
- Status at last review: README says "under heavy development". Examples pin `0.1.0`
  (one older example uses `0.0.1`).
- *Unverified:* whether it is published on the public Terraform Registry. Check before relying on
  `terraform init` pulling it; otherwise build it locally (below).

## Authentication

Provider arguments, or the matching environment variables:

| Argument | Env var | Value |
|---|---|---|
| `base_url` | `NME_BASE_URL` | `https://<app>.azurewebsites.net` |
| `tenant_id` | `NME_TENANT_ID` | `<tenant-id>` |
| `client_id` | `NME_CLIENT_ID` | the REST API client app |
| `client_secret` | `NME_CLIENT_SECRET` | its secret; prefer the env var over tfvars |
| `scope` | `NME_SCOPE` | `api://<nerdio-app-id>/.default` |

The REST API has to be enabled first ([entra-app.md](entra-app.md#rest-api-client)).

## What it covers

15 resources:

- Full CRUD: `static_host_pool`, `dynamic_host_pool` (needs an auto-scale profile),
  `auto_scale_profile`, `fslogix_profile`, `fslogix_default_profile`, `rdp_profile`,
  `rdp_default_profile`, `vm_deployment_profile`, `scripted_action`, `scripted_action_group`,
  `scripted_action_profile`, `user_assignment`.
- Any change forces replacement: `workspace`, `linked_resource_group`, `linked_network`.
  Plan carefully; replacing a linked network or workspace under live host pools is disruptive.

15 data sources, including `linked_subscription` and `ad_config`. There are no data sources for
host pools.

Host pool notes: `SecurityType` is `None`, `TrustedLaunch` or `Confidential`; `image` and
`storage_type` are required.

## Gaps

Not covered at last review: session hosts, app groups, RemoteApps, MSIX app attach, schedules
and monitoring. Those stay in the Nerdio console.

## Building it locally

- Needs Go 1.25+ and `go generate ./...`, which generates the client from the OpenAPI spec at
  `internal/client/api.json`. Generated code is not committed, so a plain `go build` fails.
- Install the binary through a `dev_overrides` or filesystem mirror CLI config
  ([../terraform/restricted-networks.md](../terraform/restricted-networks.md)).

## How the kit uses it

Two stages with separate state: a platform stage (azurerm/azuread) builds Azure and the Entra
apps, then a Nerdio configuration stage (`nerdio/nme`) configures Nerdio against it. The platform
stage exports its outputs as JSON (`terraform output -json ... > platform.auto.tfvars.json`) for
the second stage. See [decision 0001](../decisions/0001-build-on-nerdio-provider.md).

_Last reviewed: 2026-10-16_
