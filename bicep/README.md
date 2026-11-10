# Bicep variant (proposed)

The same landing zone as [environments/example/01-platform](../environments/example/01-platform),
written in Bicep for teams that standardise on it. It reads the **same answers**: the chat,
`./nerdio init` and the Actions form render one `setup.auto.tfvars.json`, and
[platform.bicepparam](environments/example/platform.bicepparam) loads it. Terraform stays the
reference implementation and the default; why and how the two fit is in
[decision 0032](../docs/knowledge/decisions/0032-bicep-variant.md) (proposed).

Stage 2 (Nerdio workspaces, host pools, auto-scale, FSLogix profiles) stays the Terraform root on
Nerdio's `nerdio/nme` provider, because Bicep can't call it. A Nerdio Bicep extension is the
upstream ask.

## Run it from Cloud Shell (Bash)

Cloud Shell's `az` already includes Bicep, so nothing to install. Sign in to the right tenant and
subscription first (`./nerdio use <env>`), then:

```bash
./nerdio init                       # same interview as Terraform; writes the answers file
az bicep build-params --file bicep/environments/example/platform.bicepparam --stdout >/dev/null  # compile check

LOCATION=$(jq -r '.control_plane_location // "eastus2"' environments/example/01-platform/setup.auto.tfvars.json)
PREFIX=$(jq -r .prefix environments/example/01-platform/setup.auto.tfvars.json)

# Plan: shows what would change, changes nothing.
az deployment sub what-if --location "$LOCATION" \
  --parameters bicep/environments/example/platform.bicepparam

# Apply, as a deployment stack so removed resources are tracked like Terraform state.
# Review the what-if first; the tenant owner runs this, never an assistant.
az stack sub create --name "nerdio-$PREFIX-platform" --location "$LOCATION" \
  --parameters bicep/environments/example/platform.bicepparam \
  --action-on-unmanage detachAll --deny-settings-mode none
```

`detachAll` means a resource dropped from the template is left in Azure, not deleted, which is the
safe default while the variant is new. Teardown is `az stack sub delete --name ... --action-on-unmanage deleteAll`
after you've checked what it holds.

GitHub Codespaces works too, but it isn't free (it bills compute and storage per hour beyond the
free monthly allowance), so it stays optional; see [docs/codespaces.md](../docs/codespaces.md).

## Don't mix engines in one environment

Both engines create the same resource groups and names. Pick one per environment. Moving an
environment from Terraform to Bicep (or back) isn't supported yet.

## Parity with the Terraform root

| Terraform module | Bicep | Notes |
|---|---|---|
| foundation | ported | resource groups in `main.bicep`, Log Analytics in `modules/log-analytics.bicep` |
| network | ported | NSGs, NAT gateway, hub peering, firewall route table, privatelink zones; `dns-zone-link` and `vwan-connection` handle cross-resource-group pieces |
| fslogix-storage | ported | includes the `CanNotDelete` lock when `enable_resource_locks` is on |
| image-gallery | ported | gallery, Gen2 Trusted Launch definitions, build resource group, Packer roles |
| anf-storage | not yet | |
| nerdio-identity | next | Microsoft Graph Bicep extension; must be its own deployment (Graph isn't supported in stacks or what-if) |
| nerdio-core | next | App Service, SQL, Key Vault, Automation; the code deploy job is an ARM resource |
| nerdio-hardening, nerdio-secrets, nerdio-rbac, cmk-encryption | not yet | |
| openbao, automation-workers, vnet-runner, avd-insights, azure-local, windows-365, intune-policies | not yet | optional modules |
| nerdio-manager (Marketplace) | not planned | the Terraform-native install is the default |
| nerdio-config (stage 2) | stays Terraform | needs `nerdio/nme`; see decision 0032 |

Per-region `subscription_id` isn't used yet: every region deploys into the signed-in subscription.

## Checks

CI runs `az bicep build` and `az bicep build-params` on every PR (the `bicep` job in
[validate.yml](../.github/workflows/validate.yml)) against answers rendered from
`schema/examples/`. Nothing here has run against a real tenant yet.
