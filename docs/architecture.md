# Architecture

```
                         Entra ID
                  nerdio-nmw-app (+ REST client)
                              │
┌─────────────── rg-nerdio ───┴────────────────────┐
│ App Service + plan   Azure SQL (S1)   Key Vault  │   Terraform core (modules/nerdio-core)
│ Automation accounts  App Insights     Storage    │   or Marketplace (modules/nerdio-manager)
└──────┬─────────────────────┬─────────────────────┘
       │ VNet integration     │ private endpoints (modules/nerdio-hardening)
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

- **AVD objects go through Nerdio's provider, not azurerm** ([decision 0001](knowledge/decisions/0001-build-on-nerdio-provider.md), [0002](knowledge/decisions/0002-nerdio-owns-avd-objects.md)).
  Host pools, workspaces, FSLogix and auto-scale profiles are created with `nerdio/nme`
  (`modules/nerdio-config`), with `modules/nerdio-rest-gaps` bridging REST API endpoints the
  provider hasn't covered yet, so Nerdio stays the system of record. The kit never creates
  `azurerm_virtual_desktop_*` resources.
- **Two stages, two states.** `nerdio/nme` needs a running Nerdio with its REST API enabled, and
  Nerdio's first-run wizard is manual, so config lives in its own root (`02-nerdio-config`) and state.
- **Terraform-native install by default, Marketplace as an alternative** ([decision 0011](knowledge/decisions/0011-terraform-native-install.md), superseding [0003](knowledge/decisions/0003-marketplace-template.md)).
  `modules/nerdio-core` (`nerdio_install = "terraform"`, the default) builds the App Service,
  Entra-only SQL, RBAC Key Vault, Application Insights, storage and Automation accounts in
  Terraform, signs the web app in with a Key Vault certificate instead of a client secret, and
  starts an Automation job that deploys the Nerdio package. `modules/nerdio-manager`
  (`nerdio_install = "marketplace"`) supports a normal Azure portal Marketplace deployment
  (discovering the Marketplace resources in the `nerdio` resource group with no template export)
  or an exported Marketplace ARM template.
- **Entra app in Terraform** (`modules/nerdio-identity`). Creates `nerdio-nmw-app`, its app roles,
  Graph permissions, optional admin consent and the REST API client app. Required for the
  Terraform install; for the Marketplace install, you can either let Nerdio's Cloud Shell install
  script create `nerdio-nmw-app` and pass `entra_app.existing_client_id` so Terraform still builds
  the REST API client + Key Vault secret hand-off, or pre-create `nerdio-nmw-app` in Terraform.
- **Secret hand-off without manual copying** ([decision 0015](knowledge/decisions/0015-secrets-key-vault-default-openbao-optional.md)).
  `modules/nerdio-secrets` stores the REST API client secret in an RBAC Key Vault using a
  write-only attribute, and stage 2 reads it with an ephemeral resource. `modules/openbao`
  optionally mints a short-lived secret per run instead.
- **Hardening as additive resources** (`modules/nerdio-hardening`). Private endpoints and VNet
  integration connect Nerdio's App Service, SQL and Key Vault into the AVD VNet. With the
  Terraform install, `disable_public_access` closes public network access in Terraform; with the
  Marketplace install, it uses an opt-in `az` call. `modules/vnet-runner` can run ephemeral
  GitHub Actions jobs inside the VNet once public access is off.
- **Packer (and targeted Ansible) for images** ([decision 0005](knowledge/decisions/0005-packer-for-images.md), [0028](knowledge/decisions/0028-targeted-ansible-for-images-and-hybrid.md)).
  Images publish to a Compute Gallery (`modules/image-gallery`) as Gen2 + Trusted Launch, which
  Nerdio imports directly.

## Open items to verify against Nerdio

- `nerdio/nme` is 0.x. Workspace, linked resource group and linked network can't update in place,
  so changing them replaces them. App groups, session hosts and schedules aren't covered by the
  provider yet (`modules/nerdio-rest-gaps` covers the REST API gaps where endpoints exist).
- Host pool `image` takes the identifier Nerdio shows for a desktop image. Marketplace paths work
  as-is; for a Packer-built gallery image, add it under Desktop Images first and use its identifier.
- The REST API client tag format (`NMW_REST_API_CLIENT:<app id>`) uses the Nerdio app's client ID.
  Nerdio's article is ambiguous; confirm in **Settings > Integrations** after enabling.
- Marketplace parameter names change between Nerdio releases; when using `nerdio_install = "marketplace"`,
  always take them from your export.
