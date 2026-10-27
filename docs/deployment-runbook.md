# Deployment runbook

Terraform installs Nerdio Manager itself (`nerdio_install = "terraform"`, the default). It builds
the resources and settings Nerdio's Marketplace template and install script would create, and an
Automation job inside Azure deploys the app code. Nerdio's setup wizard is still interactive,
because Nerdio has no API for the directory profile or first-run steps.

The Azure Marketplace path, `nerdio_install = "marketplace"`, works with a normal Azure portal
Marketplace deployment (no ARM template export needed) or an exported Marketplace template, and
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

Set `nerdio_install = "marketplace"` (`./nerdio init --set nerdio_install=marketplace`). Two ways
to deploy the Marketplace resources:

- **Azure portal Marketplace (recommended for Marketplace installs, no template export):**
  1. Run `01-platform` (`create_entra_app = false` is the default for Marketplace). Terraform
     creates the empty `nerdio` resource group, the AVD network, FSLogix storage and Compute Gallery.
     (If you already deployed Nerdio Manager in the portal first, set
     `existing_resource_groups = ["nerdio"]` so Terraform reads that existing group.)
  2. In the Azure portal, open **Nerdio Manager for Enterprise** from the Marketplace and deploy it
     into the `nerdio` resource group from `resource_group_names`.
  3. Open the Nerdio web app URL, copy Nerdio's one-line install script into Azure Cloud Shell, and
     let Nerdio create `nerdio-nmw-app`.
  4. Set `entra_app.existing_client_id` (or `./nerdio init --set existing_entra_app_client_id=<id>`)
     to the `nerdio-nmw-app` Application (client) ID and apply `01-platform` again. Terraform
     discovers the Marketplace web app, SQL server and Key Vault, creates the `<app>-rest-client`
     app and Key Vault secret hand-off (`nerdio-secrets`), and populates `nerdio_config_inputs` for
     stage 2 (`02-nerdio-config`).
- **Exported Marketplace ARM template (`nerdio_template_file` set):**
  1. Export the template as described in
     [templates/nerdio-manager/README.md](../templates/nerdio-manager/README.md) and set
     `nerdio_template_file = "../../../templates/nerdio-manager/template.json"`.
  2. After the first apply, open the `nerdio_url` output and run Nerdio's install script in Cloud
     Shell (`create_entra_app = false`) or use **Show advanced > Use existing AD app** in local
     PowerShell (`create_entra_app = true`).
