# Bicep variant

The same landing zone as [environments/example/01-platform](../environments/example/01-platform),
written in Bicep for teams that standardise on it. It reads the **same answers**: the chat,
`./nerdio init` and the Actions form render one `setup.auto.tfvars.json`, and
[platform.bicepparam](environments/example/platform.bicepparam) loads it. Terraform stays the
reference implementation and the default; why and how the two fit is in
[decision 0032](../docs/knowledge/decisions/0032-bicep-variant.md).

Stage 2 (Nerdio workspaces, host pools, auto-scale, FSLogix profiles) stays the Terraform root on
Nerdio's `nerdio/nme` provider, because Bicep can't call it. A Nerdio Bicep extension is the
upstream ask.

## Run it from Cloud Shell (Bash)

Cloud Shell's `az` already includes Bicep, so nothing to install. The Entra app has its own step
(next section). Sign in to the right tenant and
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

## Entra app (identity.bicep)

Nerdio's app registration, its six app roles, WVD Admin assignments, admin consent and the REST API
client app are in [identity.bicep](identity.bicep). Microsoft Graph resources can't go in a
deployment stack and have no what-if, so this is a plain deployment with **no preview**: read the
template and the parameters before you run it. Run it before the platform stack.

```bash
az deployment sub create --name nerdio-identity --location "$LOCATION" \
  --parameters bicep/environments/example/identity.bicepparam
```

Rights: Application Administrator (or Cloud Application Administrator) to create the apps, plus
Privileged Role Administrator for admin consent when `grant_admin_consent` is on, the same as the
Terraform root ([docs/access.md](../docs/access.md)). After Nerdio Manager is installed, deploy it
again with `--parameters app_service_hostname=<hostname>` to add the redirect URIs.

Deleting the deployment doesn't delete the apps. To tear them down, delete the two app
registrations (`nerdio-nmw-app` and `nerdio-nmw-app-rest-client`, or your `display_name`) in Entra.

### REST API client secret

The Graph extension can't create passwords, only certificates and federated credentials. Stage 2
(the `nerdio/nme` provider) still signs in with a client secret, so in the Bicep variant that one
step is a script. The platform stack builds the Key Vault and its access (decision 0015, same as
Terraform's `nerdio-secrets`); then the tenant owner runs, from the repo root in Cloud Shell:

```bash
bicep/rest-client-secret.sh
```

It creates the secret on the REST API client app and pipes it straight into Key Vault. The value is
never printed, never in a shell variable, file or argument, and no deployment holds it (the
Terraform root keeps it in stage 1 state). Stage 2 reads it from Key Vault on the fly. Run it again
to rotate; it replaces every password on that app, so only the new one works afterwards. Lifetime
is 365 days (`SECRET_DAYS` changes it), and the Key Vault secret gets the same expiry.

Rights: owner of the REST API client app (whoever deployed `identity.bicep` is) and Key Vault
Secrets Officer on the vault. The stack grants that role to whoever deploys it; when a pipeline
deploys the stack, set `deployer_object_id` to the person who runs the script.

Readers (you, `nme_secret.reader_object_ids` and the optional `nme_secret.github_oidc` identity)
get Key Vault Secrets User on the vault, not on the secret as in Terraform, because the secret
doesn't exist yet when the stack deploys. The vault holds only this secret, so the reach is the
same; don't store anything else in it. OpenBao (`nme_secret_store = "openbao"`) isn't in the Bicep
variant yet. With `output`, there's no vault and you supply `NME_CLIENT_SECRET` yourself.

The default vault name follows Terraform's pattern (`kvnme` + prefix + a 6-character suffix), but
the suffix is computed differently, so the two engines pick different names.

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
| nerdio-identity | ported | `identity.bicep` (Microsoft Graph Bicep extension): app, app roles, admin consent, REST client app, federated credentials. Its own deployment; the client secret comes from `rest-client-secret.sh` |
| nerdio-secrets | ported | `modules/nerdio-secrets.bicep` in the platform stack: Key Vault, RBAC, optional GitHub OIDC identity; readers scoped to the single-purpose vault; OpenBao not yet |
| nerdio-core | next | App Service, SQL, Key Vault, Automation; the code deploy job is an ARM resource |
| nerdio-hardening, nerdio-rbac, cmk-encryption | not yet | |
| openbao, automation-workers, vnet-runner, avd-insights, azure-local, windows-365, intune-policies | not yet | optional modules |
| nerdio-manager (Marketplace) | not planned | the Terraform-native install is the default |
| nerdio-config (stage 2) | stays Terraform | needs `nerdio/nme`; see decision 0032 |

`main.bicep` also outputs `nerdio_config_inputs` in the same shape as the Terraform output, so a
pipeline can run the Terraform config stage after the stack. `nme_secret_source` and `nme_key_vault`
are filled; `nme_client_id` and `nme_scope` are outputs of the `nerdio-identity` deployment, to merge
in; `nme_base_url` stays null until the Nerdio install slice is ported.

Per-region `subscription_id` isn't used yet: every region deploys into the signed-in subscription.

## Checks

CI runs `az bicep build` and `az bicep build-params` on every PR (the `bicep` job in
[validate.yml](../.github/workflows/validate.yml)) against answers rendered from
`schema/examples/`. Nothing here has run against a real tenant yet.
