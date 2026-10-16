# Deployment runbook

Nerdio Manager can't be installed fully hands-off: its own install step runs a script from the
app's home page and the setup wizard is interactive. This runbook puts Terraform around those
steps so everything else is repeatable.

## 0. Prerequisites

- Subscription **Owner** on the target subscription.
- **Global Administrator**, or **Privileged Role Administrator + Cloud Application Administrator**, in the tenant.
- `az login --tenant <tenant-id>` and `az account set --subscription <subscription-id>`.
- For AD DS joined hosts: domain controllers reachable from the AVD VNet (peering or VPN) and a
  service account that can join computers to the target OU.

## 1. Export the Marketplace template (once per Nerdio version)

Follow [templates/nerdio-manager/README.md](../templates/nerdio-manager/README.md). Commit the
template, and put its parameters in `nerdio_template_parameters`.

## 2. First apply: landing zone, Nerdio core, Entra app

```bash
cd environments/<env>/01-platform
terraform init
terraform apply
```

This creates the resource groups, network, FSLogix storage, Compute Gallery, the Nerdio
Marketplace deployment and (with `create_entra_app = true`) the `nerdio-nmw-app` registration.

If `entra_app.grant_admin_consent` is false, a Global Administrator grants consent in
**Entra ID > App registrations > nerdio-nmw-app > API permissions**.

## 3. Install step (manual)

1. Open the `nerdio_url` output.
2. With the Terraform-created app: choose **Show advanced > Use existing AD app** and enter
   `entra_app_client_id`, `entra_app_service_principal_id` and the secret from
   `terraform output -raw entra_app_client_secret`. Download the Az script and run it in local
   PowerShell (Nerdio doesn't support this path in Cloud Shell).
3. Without it (`create_entra_app = false`): copy the one-line script into Cloud Shell and let
   Nerdio create the app itself.

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
`hardening.disable_public_access`) and apply again. The Marketplace resource names are only known
after step 2, which is why this is a separate apply.

This replaces Nerdio's **Enable Private Endpoints** runbook. Use one or the other, not both.
With `private_app_service = true`, admins need a route into the VNet (VPN, Bastion or a jump
host) to reach the console.

## 6. Nerdio configuration (nerdio/nme)

1. In Nerdio, open **Settings > Integrations** and enable the REST API. Stage 1 already created
   the REST client app (`<app name>-rest-client`). Grant it admin consent if
   `grant_admin_consent` was false.
2. Hand stage 1's values to stage 2 and export the secret:

   ```bash
   cd environments/<env>/01-platform
   terraform output -json nerdio_config_inputs > ../02-nerdio-config/platform.auto.tfvars.json
   export NME_CLIENT_SECRET="$(terraform output -raw nme_client_secret)"
   ```

3. Describe the workspace and host pools in `02-nerdio-config/terraform.tfvars` and apply:

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
