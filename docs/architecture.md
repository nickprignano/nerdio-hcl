# Architecture

```
                         Entra ID
                  nerdio-nmw-app (+ REST client)
                              │
┌─────────────── rg-nerdio ───┴────────────────────┐
│ App Service + plan   Azure SQL (S1)   Key Vault  │   Marketplace template
│ Automation account   App Insights     Storage    │   (modules/nerdio-manager)
└──────┬─────────────────────┬─────────────────────┘
       │ VNet integration     │ private endpoints (second apply)
┌──────┴─────── rg-avd-network ┴───────────────────────────────┐
│ vnet-<prefix>-avd                                            │
│   snet-session-hosts ── NAT gateway (or hub firewall)        │
│   snet-private-endpoints ── SQL, Key Vault, Azure Files, web │
│   snet-nerdio-app (delegated Microsoft.Web/serverFarms)      │
│ privatelink zones: database, vaultcore, file, blob, websites │
│ optional peering to hub (AD DS / Entra DS, on-prem)          │
└──────────────────────────────────────────────────────────────┘
rg-avd-storage     Premium Azure Files (FSLogix), private only
rg-avd-hostpools   Compute Gallery + host pools that Nerdio creates
rg-avd-monitoring  Log Analytics for AVD Insights
```

## Design decisions

- **Nerdio owns AVD objects.** Host pools, app groups, scaling and FSLogix profiles are created
  in Nerdio. Managing them in Terraform too would fight Nerdio's auto-scale and image rollout.
- **Marketplace template, not a rebuild.** Nerdio only supports its Marketplace deployment, so the
  kit deploys the exported template rather than recreating App Service/SQL by hand. The module
  ignores template changes after install because Nerdio updates the app itself.
- **Hardening as additive resources.** Private endpoints and VNet integration are new resources
  pointing at Nerdio's; Terraform doesn't take over the Marketplace resources. Disabling public
  access on them is an opt-in `az` call.
- **Entra app in Terraform is optional.** It follows Nerdio's documented "create Entra ID
  application" path, so tenants with strict app-registration policies can review it as code.
  The trade-off Nerdio notes: without its own automation app, Nerdio updates run from Cloud Shell
  or PowerShell.
- **Packer for images.** Images publish to a Compute Gallery as Gen2 + Trusted Launch, which
  Nerdio imports directly.

## Open items to verify against Nerdio

- The REST API client tag format (`NMW_REST_API_CLIENT:<app id>`) uses the Nerdio app's client ID.
  Nerdio's article is ambiguous; confirm in **Settings > Integrations** after enabling.
- Marketplace parameter names change between Nerdio releases; always take them from your export.
