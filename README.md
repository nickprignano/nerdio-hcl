# nerdio-hcl

A HashiCorp-stack deployment kit for **Nerdio Manager for Enterprise** on Azure Virtual Desktop,
built around Nerdio's official Terraform provider, [`nerdio/nme`](https://github.com/Get-Nerdio/NME-Terraform-Provider).

- **Stage 1, platform** (`azurerm`, `azuread`): the Azure landing zone, Nerdio Manager itself, and the
  Entra apps Nerdio and its REST API need.
- **Stage 2, Nerdio config** (`nerdio/nme`): workspaces, linked resource groups and networks,
  FSLogix and auto-scale profiles and dynamic host pools, all managed through Nerdio's REST API.
- **Images** (Packer): a Windows 11 multi-session golden image published to a Compute Gallery.

| Layer | Tool | What it covers |
|---|---|---|
| Foundation | Terraform | Resource groups, resource provider registration, Log Analytics |
| Network | Terraform | AVD spoke VNet, session host / private endpoint / App Service subnets, NSGs, NAT gateway, privatelink DNS zones, optional hub peering |
| Profiles | Terraform | Premium Azure Files for FSLogix with a private endpoint, Entra Kerberos / Entra DS / AD DS auth and SMB RBAC |
| Nerdio Manager | Terraform (+ azapi) | App Service, Entra-only SQL, Key Vault, Automation, App Insights and storage with Nerdio's settings, plus an Automation job that deploys the app code. The Marketplace template stays as an alternative. |
| Identity | Terraform (azuread) | The `nerdio-nmw-app` registration, app roles, Graph permissions, optional admin consent and REST API client |
| Hardening | Terraform | Private endpoints for SQL and Key Vault, App Service VNet integration, optional private console |
| Images | Terraform + Packer | Compute Gallery and a Windows 11 multi-session + M365 image (Trusted Launch, updates, WDOT optimizations) |
| Nerdio config | Terraform (`nerdio/nme`) | Linked subscription, resource groups and network, workspace, FSLogix profile, auto-scale profile, dynamic host pools |

Nerdio's setup wizard is the only manual step; it sits between the two stages, because Nerdio has
no API for the directory profile or first run yet.
`nerdio/nme` is early (0.x), so check its
[coverage notes](https://github.com/Get-Nerdio/NME-Terraform-Provider/blob/main/AVD-COVERAGE.md)
before you rely on it for something; app groups and session host actions aren't covered yet, for example.

## Guided setup

One set of questions, three ways to answer them. All three read
[`schema/parameters.json`](schema/README.md), so they ask the same things and write the same tfvars:

- **Chat:** a setup chatbot you host in your own Azure tenant. Deploy it from Azure Cloud Shell with
  `./nerdio assistant --admin-group "<your admin group>"`, open the URL it prints, and it walks you
  through discover, a readiness check and configure, explaining each choice with a source
  ([docs/assistant.md](docs/assistant.md)).
- **Command line:** `./nerdio init` asks the questions in the terminal (Azure Cloud Shell works),
  then `./nerdio preflight` checks your roles, providers, region and quota.
- **Button:** the **configure** workflow in the Actions tab takes the main answers as a form and
  dry-runs them.

Details: [docs/setup.md](docs/setup.md).

### Readiness check without the kit

Installing Nerdio Manager from the Marketplace by hand? The same read-only readiness check runs on
its own in Azure Cloud Shell (Bash), with Reader on the subscription. Download a pinned release,
check it, run it:

```bash
V=preflight-v0.1.0   # pinned; never "latest"
curl -fsSLO "https://github.com/nickprignano/nerdio-hcl/releases/download/$V/nerdio-preflight.pyz"
echo "<sha256 for $V, from the table below>  nerdio-preflight.pyz" | sha256sum -c && python3 nerdio-preflight.pyz
```

| Release | SHA-256 of `nerdio-preflight.pyz` |
|---|---|
| *none yet* | The first release is published when a maintainer tags `preflight-v0.1.0` |

The checksum lives here, not only beside the download, so a swapped file can't bring its own.
With `gh` signed in, `gh attestation verify nerdio-preflight.pyz --repo nickprignano/nerdio-hcl`
also proves the file came from this repository's release workflow. What it checks and how to read
the result: [docs/knowledge/nerdio/readiness.md](docs/knowledge/nerdio/readiness.md).

To deploy without pasting commands, run the one-time pipeline bootstrap from Cloud Shell. After
that, the **deploy** workflow plans each stage and applies it only after you approve it in
GitHub, and the setup chatbot can start and explain those runs for you
([docs/pipeline.md](docs/pipeline.md)).

## Layout

<!-- BEGIN GENERATED: layout (./nerdio docs --write) -->
```
modules/
  foundation/        resource groups, providers, Log Analytics
  network/           AVD spoke network and private DNS
  fslogix-storage/   profile storage
  anf-storage/       optional Azure NetApp Files high-IOPS SMB profile volume
  nerdio-core/       Nerdio Manager built in Terraform, plus the app code deploy job (default)
  nerdio-manager/    Azure Marketplace resource discovery + optional template deployment
  nerdio-identity/   Nerdio's Entra app, app roles, consent and REST API client
  nerdio-secrets/    Key Vault hand-off of the REST API secret to stage 2 (default)
  openbao/           optional OpenBao server that mints a short-lived REST API secret per run
  nerdio-hardening/  private endpoints and VNet integration for Nerdio's core resources
  automation-workers/optional Hybrid Runbook Worker VM Scale Set inside the AVD VNet
  avd-insights/      optional AVD Insights Data Collection Rule, alerts and consumption budget
  vnet-runner/       optional ephemeral GitHub Actions runner inside the AVD VNet
  image-gallery/     Compute Gallery and image definitions for Packer
  nerdio-config/     Nerdio objects through the nerdio/nme provider
  nerdio-rest-gaps/  Nerdio REST API endpoints not yet covered by nerdio/nme
  intune-policies/   optional Intune update rings and Defender exclusions via Microsoft Graph
  windows-365/       optional Windows 365 Cloud PC provisioning alongside Nerdio Manager
  azure-local/       optional Azure Local logical network and RBAC for hybrid AVD host pools
  deploy-pipeline/   state storage, OIDC deploy identities and the GitHub approval gate
  assistant/         self-hosted setup chatbot (Container App, Entra sign-in, Claude / Foundry)
  github-settings/   repository settings, rulesets and labels declared in Terraform
environments/
  example/
    00-assistant/      optional self-hosted setup chatbot
    00-pipeline/       one-time bootstrap for the deploy pipeline
    01-platform/       stage 1 root: Azure + Entra + Nerdio install
    02-nerdio-config/  stage 2 root: Nerdio configuration via nerdio/nme
assistant/             setup chatbot app and prompt (deployed by 00-assistant)
schema/                parameters.json single source of truth + example answer sets
packer/
  avd-win11/           Windows 11 multi-session image build
ansible/               optional image and hybrid AD DS playbooks (decision 0028)
github/                this repository's own GitHub settings in Terraform
templates/
  nerdio-manager/      exported Marketplace template (marketplace install only)
docs/
  guardrails.md          non-negotiable security, browser and license rules
  setup.md               guided setup across chat, CLI and the Actions form
  assistant.md           deploying and connecting the self-hosted setup chatbot
  deployment-runbook.md  end-to-end order of operations and manual wizard steps
  pipeline.md            plan and apply from GitHub Actions behind an approval
  access.md              every Azure, Entra, GitHub and Anthropic right the kit needs
  secrets.md             how stage 2 gets the REST API secret without anyone handling it
  cloud-shell.md         running from Azure Cloud Shell in any browser
  codespaces.md          VS Code in the browser as an optional workbench
  architecture.md        diagram and design decisions across stages
  model-pilot.md         measuring and reporting the model-selection pilot
  knowledge/           the living knowledge base and decision records
```
<!-- END GENERATED: layout -->

## Quick start

Requirements: Terraform >= 1.11, Packer >= 1.11, Azure CLI, subscription **Owner**, and Global
Administrator (or Privileged Role Administrator + Cloud Application Administrator) in Entra ID.

```bash
cp -r environments/example environments/sandbox
cd environments/sandbox/01-platform
cp terraform.tfvars.example terraform.tfvars   # tenant, subscription, names, CIDRs (gitignored)
az login --tenant <tenant-id>
terraform init && terraform apply

# Terraform installs Nerdio Manager too; finish its setup wizard, enable the REST API, then:
../../../scripts/install-nme-provider.sh      # nerdio/nme ships as a GitHub release for now
terraform output -json nerdio_config_inputs > ../02-nerdio-config/platform.auto.tfvars.json
cd ../02-nerdio-config
cp terraform.tfvars.example terraform.tfvars   # workspace and host pools
terraform init && terraform apply              # reads the REST secret from Key Vault itself
```

From Azure Cloud Shell (any browser, tablets included) `scripts/cloudshell-bootstrap.sh` reads
the tenant and subscription from your sign-in instead; see [docs/cloud-shell.md](docs/cloud-shell.md).
Prefer a full editor? The repo opens in GitHub Codespaces with the tools preinstalled; see
[docs/codespaces.md](docs/codespaces.md).

The full order of operations, including the manual Nerdio steps, is in
[docs/deployment-runbook.md](docs/deployment-runbook.md).

## Provider versions

Modules require `azurerm >= 5.0` and `azuread >= 3.0`. `nerdio/nme` is installed from Nerdio's
GitHub release (`v0.0.1-preview.1`, pinned in `scripts/install-nme-provider.sh`) until it is
published to the Registry.
Validated with Terraform 1.16, azurerm 5.10, azuread 3.10 and Packer 1.16 with the Azure plugin 2.6.

## Guardrails

Every change follows [docs/guardrails.md](docs/guardrails.md). In short:

1. **Automate, never at the expense of security.** Identities and certificates over secrets,
   least privilege, and a documented workaround where automation isn't safe.
2. **HCL first.** Terraform or Packer does it if it can; scripts are thin bootstrap glue.
3. **Works from a browser.** Every step runs in Azure Cloud Shell, on an iPad included.
4. **Nothing identifies a real environment.** No real IDs, domains, IPs, emails, secrets or
   employer names in the repo. CI runs gitleaks and blocks tracked tfvars and state files.
5. **Secrets never go through chat** or into the repo.
6. **PRs only, plan first, and nothing applies without the tenant owner's yes.**
7. **Unlicensed code is reference only.** Nerdio's repos and MB-External have no license: we use
   facts from them, never their code, and download `nerdio/nme` from Nerdio's release.

## Keeping it shareable

The repo holds no tenant-specific values. Real IDs, names and CIDRs go in `terraform.tfvars`,
`*.auto.tfvars.json` and `*.pkrvars.hcl`, which are gitignored. Secrets are passed through
environment variables, never files. Examples use `contoso` names and all-zero GUIDs.

## License

The kit's own code and docs are licensed under the [Apache License 2.0](LICENSE). Components the
kit downloads or calls (Nerdio Manager and the `nerdio/nme` provider, WDOT, Terraform and Packer,
the Terraform providers, Azure itself) keep their own terms and aren't covered; see
[NOTICE](NOTICE) and [decision 0018](docs/knowledge/decisions/0018-apache-2-license.md).
