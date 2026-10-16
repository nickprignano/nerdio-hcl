---
title: "Nerdio Terraform provider (`nerdio/nme`)"
summary: "Nerdio's own nerdio/nme provider: auth, resources, coverage gaps, how to build it"
topic: nerdio
status: verified
last_reviewed: 2026-10-16
---

# Nerdio Terraform provider (`nerdio/nme`)

Nerdio's own provider configures Nerdio Manager through its REST API: host pools, profiles,
scripted actions and linked Azure resources. It does **not** deploy Nerdio Manager itself;
that still comes from the Marketplace (see [platform.md](platform.md)).

- Source: https://github.com/Get-Nerdio/NME-Terraform-Provider
- Status at last review: README says "under heavy development". The only published release is
  the GitHub pre-release `v0.0.1-preview.1`, although the README's snippets use `0.1.0` and the
  examples use `0.0.1`. Pin the release you actually installed.
- Not on the public Terraform Registry at last review. Releases are zips (Linux and Windows amd64
  only) on the repo's GitHub Releases page, installed with a `dev_overrides` CLI config. With
  `dev_overrides`, `terraform init` may fail; a `filesystem_mirror` avoids that
  ([restricted-networks.md](../terraform/restricted-networks.md#workaround-filesystem-mirror)).
- Nerdio keeps its own coverage matrix in
  [AVD-COVERAGE.md](https://github.com/Get-Nerdio/NME-Terraform-Provider/blob/main/AVD-COVERAGE.md).
- The repo has no license file at last review. See [upstream-contributions.md](upstream-contributions.md).

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
and monitoring. Those stay in the Nerdio console. Nerdio treats imperative actions (power,
reimage, drain, run script) as out of scope for the provider by design. Gaps worth contributing
are tracked in [upstream-contributions.md](upstream-contributions.md).

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
