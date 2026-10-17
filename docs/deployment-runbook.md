# Deployment runbook

Terraform installs Nerdio Manager itself (`nerdio_install = "terraform"`, the default). It builds
the resources and settings Nerdio's Marketplace template and install script would create, and an
Automation job inside Azure deploys the app code. Nerdio's setup wizard is still interactive,
because Nerdio has no API for the directory profile or first-run steps.

The older path, `nerdio_install = "marketplace"`, deploys an exported Marketplace template and
then runs Nerdio's install script; see [Marketplace install](#marketplace-install) at the end.

From Azure Cloud Shell, `scripts/cloudshell-bootstrap.sh` does steps 0 to 2 for you; see
[cloud-shell.md](cloud-shell.md).

## 0. Prerequisites

- **Your organization's intake or change approval** for this subscription, if it has one (a lab
  management tool, a change board). Get it before anything is deployed, including the chat and
  the pipeline bootstrap, and don't work around it to save time.
- Subscription **Owner** on the target subscription.
- **Global Administrator**, or **Privileged Role Administrator + Cloud Application Administrator**, in the tenant.
- `az login --tenant <tenant-id>` and `az account set --subscription <subscription-id>`.
- For AD DS joined hosts: domain controllers reachable from the AVD VNet (peering or VPN) and a
  service account that can join computers to the target OU.

## 1. First apply: landing zone, Entra app and Nerdio Manager

```bash
cd environments/<env>/01-platform
terraform init
terraform apply
```

This creates the resource groups, network, FSLogix storage and Compute Gallery, the
`nerdio-nmw-app` Entra app, and the Nerdio Manager core (`modules/nerdio-core`):

- App Service plan and web app with Nerdio's app settings, signing in to Entra with a Key Vault
  certificate instead of a client secret.
- Azure SQL with Entra authentication only. The SQL admin is an Entra group holding the web app's
  managed identity and the Nerdio app, which replaces the template's SQL login and password.
- Key Vault (RBAC), the data protection key and storage, Application Insights, Log Analytics,
  and the updater and scripted-actions Automation accounts.
- An Automation job that downloads the Nerdio package and deploys it to the web app. The apply
  doesn't wait for it. Allow about 10 minutes; the `nerdio_health` check warns until the app answers.

If `entra_app.grant_admin_consent` is false, a Global Administrator grants consent in
**Entra ID > App registrations > nerdio-nmw-app > API permissions**.

## 2. Check the install

- Open the `nerdio_url` output. You should see Nerdio's sign-in, then the setup wizard.
- If not, look at the job in the `nmw-app-automation-*` Automation account (**Jobs**); its output
  shows each step.

## 3. Install step

There isn't one with the terraform install. Go straight to the wizard.

## 4. Setup wizard (manual)

Keep it minimal; stage 2 creates the workspace, profiles and host pools.

In the Nerdio console:

- Grant admin consent when prompted.
- Directory profile: Entra-joined, AD DS or Entra DS.
- AVD network: the `avd_vnet_name` output, subnet `snet-session-hosts`.
- Resource group: link the `hostpools` group from `resource_group_names`.
- Finish, then grant the second consent from the dialog's link.

## 5. Second apply: hardening

Set `enable_hardening = true` (and optionally `hardening.private_app_service` /
`hardening.disable_public_access`) and apply again. With the marketplace install the resource
names are only known after the first apply, which is why this is a separate apply.

With the terraform install, `disable_public_access` closes Key Vault, SQL and storage in the same
apply. Terraform still writes Key Vault secrets and certificates, so after that it needs a route
into the VNet (a self-hosted runner, VPN or Bastion); Cloud Shell from a browser won't reach it.

This replaces Nerdio's **Enable Private Endpoints** runbook. Use one or the other, not both.
With `private_app_service = true`, admins need a route into the VNet (VPN, Bastion or a jump
host) to reach the console.

## 6. Nerdio configuration (nerdio/nme)

1. In Nerdio, open **Settings > Integrations** and enable the REST API. Stage 1 already created
   the REST client app (`<app name>-rest-client`). Grant it admin consent if
   `grant_admin_consent` was false.
2. Install the provider. `nerdio/nme` isn't on the Terraform Registry yet, so
   `scripts/install-nme-provider.sh` downloads Nerdio's pinned GitHub release, verifies it and
   installs it in a plugin directory under `~/.terraform.d`, with a `provider_installation`
   entry in `~/.terraformrc`. Stage 2 then runs a normal `terraform init`.
3. Hand stage 1's values to stage 2:

   ```bash
   cd environments/<env>/01-platform
   terraform output -json nerdio_config_inputs > ../02-nerdio-config/platform.auto.tfvars.json
   ```

   Nothing else is needed for the REST client secret: stage 1 stored it in Key Vault, and stage 2
   reads it with your `az` sign-in during plan and apply ([secret hand-off](secrets.md)). With
   `nme_secret_store = "openbao"` or `"output"`, follow that page's steps instead.

4. Describe the workspace and host pools in `02-nerdio-config/terraform.tfvars` and apply:

   ```bash
   cd ../02-nerdio-config
   terraform init
   terraform apply
   ```

This links the subscription, host pool resource group and session host subnet, then creates the
workspace, an FSLogix profile on the stage 1 share, an auto-scale profile and the dynamic host
pools. Nerdio then builds session hosts as auto-scale asks for them.

## 7. Golden image

```bash
cd packer/avd-win11
cp example.pkrvars.hcl sandbox.pkrvars.hcl   # use the packer_gallery output
packer init .
packer build -var-file=sandbox.pkrvars.hcl .
```

In Nerdio: **Desktop Images > Add from Azure Compute Gallery**, pick the new version, then set
the host pool's `image` in stage 2 to the identifier Nerdio shows and apply.

## 8. Profile storage notes

Stage 2 creates the Nerdio FSLogix profile. For Entra Kerberos, also grant admin consent to the
storage account's Entra app; the profile's `entra_id_kerberos` setting pushes the
Kerberos ticket retrieval policy to hosts.

## Marketplace install

Set `nerdio_install = "marketplace"`. Before the first apply, export the template as described in
[templates/nerdio-manager/README.md](../templates/nerdio-manager/README.md). After it:

1. Open the `nerdio_url` output.
2. With the Terraform-created app: choose **Show advanced > Use existing AD app** and enter
   `entra_app_client_id`, `entra_app_service_principal_id` and the secret from
   `terraform output -raw entra_app_client_secret`. Download the Az script and run it in local
   PowerShell (Nerdio doesn't support this path in Cloud Shell).
3. Without it (`create_entra_app = false`): copy the one-line script into Cloud Shell and let
   Nerdio create the app itself.
