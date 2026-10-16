# Running the kit from Azure Cloud Shell

`scripts/cloudshell-bootstrap.sh` runs both stages from Cloud Shell (Bash) in a browser, tablet
included, without typing tenant or subscription IDs. It reads them from `az account show`,
writes gitignored tfvars, installs Terraform if Cloud Shell's is older than 1.11, and installs
`nerdio/nme` without `gh` sign-in. Use a Cloud Shell with storage (persistent mode), because
Terraform keeps its local state in your home directory.

## Stage 1

```bash
az account show --query name -o tsv      # the right subscription? else: az account set --subscription "<name>"
git clone https://github.com/nickprignano/nerdio-hcl.git && cd nerdio-hcl
./scripts/cloudshell-bootstrap.sh platform           # plan
./scripts/cloudshell-bootstrap.sh platform --apply   # apply; Terraform asks for yes
```

The script writes `01-platform/sandbox.auto.tfvars` with the IDs, a random `nme-sbx-xxxx` prefix,
`eastus2`, you as WVD Admin, and the terraform install. Later runs reuse it. To change the
defaults, set `NME_LOCATION`, `NME_GRANT_CONSENT=false` or `NME_INSTALL=marketplace` before the
first run.

The apply builds Nerdio Manager and starts an Automation job that deploys its code. Give it about
10 minutes, then open `terraform -chdir=environments/example/01-platform output -raw nerdio_url`.

### Marketplace install only

With `NME_INSTALL=marketplace`, export the template first: **Marketplace > Nerdio Manager for
Enterprise > Create**, fill the Basics, then on **Review + create** choose **Download a template
for automation > Download** (don't click Create). Upload the zip with **Manage files > Upload**;
the script unpacks it. Nerdio's install step then needs local PowerShell for the "Use existing
AD app" path (see the [deployment runbook](deployment-runbook.md#marketplace-install)).

## Setup wizard

Follow step 4 of the [deployment runbook](deployment-runbook.md).

## Stage 2

```bash
./scripts/cloudshell-bootstrap.sh config            # plan
./scripts/cloudshell-bootstrap.sh config --apply    # apply
```

This installs `nerdio/nme`, writes `02-nerdio-config/platform.auto.tfvars.json` from stage 1 and
copies `terraform.tfvars.example` to `terraform.tfvars` if missing. The REST client secret never
reaches the shell: Terraform reads it from Key Vault with your Cloud Shell sign-in (see
[secret hand-off](secrets.md)). With the optional OpenBao server, the script gets a short-lived
Entra token for it instead.

## Clean up

Destroy stage 2 first, then stage 1:

```bash
terraform -chdir=environments/example/02-nerdio-config destroy   # reads the secret from Key Vault
terraform -chdir=environments/example/01-platform destroy
```

If Nerdio created session hosts that Terraform doesn't know about, the resource group deletes
can fail; delete the `rg-nme-sbx-xxxx-*` groups in the portal and rerun the stage 1 destroy.
