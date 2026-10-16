# Running the kit from Azure Cloud Shell

`scripts/cloudshell-bootstrap.sh` runs both stages from Cloud Shell (Bash) in a browser, tablet
included, without typing tenant or subscription IDs. It reads them from `az account show`,
writes gitignored tfvars, installs Terraform if Cloud Shell's is older than 1.9, and installs
`nerdio/nme` without `gh` sign-in. Use a Cloud Shell with storage (persistent mode): local state
and Nerdio's own install script both need it.

## Stage 1

1. Export the Nerdio Manager template: **Marketplace > Nerdio Manager for Enterprise > Create**,
   fill the Basics, then on **Review + create** choose **Download a template for automation >
   Download**. Don't click Create. In Cloud Shell, **Manage files > Upload** the zip.
2. Clone and plan:

   ```bash
   az account show --query name -o tsv      # the sandbox subscription? else: az account set --subscription "<name>"
   git clone https://github.com/nickprignano/nerdio-hcl.git && cd nerdio-hcl
   ./scripts/cloudshell-bootstrap.sh platform
   ```

3. Review the plan, then apply (Terraform asks for `yes`):

   ```bash
   ./scripts/cloudshell-bootstrap.sh platform --apply
   ```

The script writes `01-platform/sandbox.auto.tfvars` (IDs, a random `nme-sbx-xxxx` prefix,
`eastus2`, you as WVD Admin) and `01-platform/nerdio.auto.tfvars.json` (the exported
parameters). Later runs reuse them. Set `NME_LOCATION` or `NME_GRANT_CONSENT=false` before the
first run to change those defaults.

## Install step and wizard

Follow steps 3 and 4 of the [deployment runbook](deployment-runbook.md). The **Use existing AD
app** path downloads `deploy-az.ps1`, which Nerdio documents for local PowerShell; from a tablet,
try it in Cloud Shell PowerShell (`pwsh`) and note whether it works.

## Stage 2

```bash
./scripts/cloudshell-bootstrap.sh config            # plan
./scripts/cloudshell-bootstrap.sh config --apply    # apply
```

This installs `nerdio/nme`, writes `02-nerdio-config/platform.auto.tfvars.json` from stage 1,
copies `terraform.tfvars.example` to `terraform.tfvars` if missing, and passes the REST client
secret through `NME_CLIENT_SECRET` only.

## Clean up

Destroy stage 2 first, then stage 1:

```bash
export NME_CLIENT_SECRET="$(terraform -chdir=environments/example/01-platform output -raw nme_client_secret)"
terraform -chdir=environments/example/02-nerdio-config destroy
terraform -chdir=environments/example/01-platform destroy
```

If Nerdio created session hosts that Terraform doesn't know about, the resource group deletes
can fail; delete the `rg-nme-sbx-xxxx-*` groups in the portal and rerun the stage 1 destroy.
