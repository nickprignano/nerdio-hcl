---
title: "Nerdio readiness checks"
summary: "The read-only readiness engine behind ./nerdio preflight: stages, statuses, rights, and how it sits beside Nerdio's own readiness script"
topic: nerdio
status: partial
last_reviewed: 2026-10-19
sources:
  - https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps
  - https://nmehelp.getnerdio.com/hc/en-us/articles/26124379482381-How-to-Check-the-Health-of-Nerdio-Manager
---

# Nerdio readiness checks

One read-only engine answers "will this Nerdio Manager deployment, and each feature I plan to
turn on, work in this tenant?" before the install, after it and after Nerdio's wizard
([decision 0026](../decisions/0026-read-only-readiness-engine.md)). It lives in
`scripts/nerdio/readiness/` and runs behind `./nerdio preflight`, the deploy pipeline's
`preflight` stage and, through the pipeline, the setup chat. For a manual Marketplace install it
also runs on its own, without the kit ([standalone](#standalone)).

## Running it

```bash
./nerdio preflight                     # pre-install, the kit's answers, console report
./nerdio preflight --format md         # a short report to paste into a ticket or the chat
./nerdio preflight --json              # readiness.json (schema/readiness.schema.json)
./nerdio preflight --save out/         # readiness.json and readiness.md, mode 600
./nerdio preflight --list              # the catalogue below
./nerdio preflight --only sub.region,avd.vcpu
```

`--stage pre-install|post-install|post-wizard` picks when you are. `--features` adds feature
domains (`app-mgmt`, `app-attach`, `insights`, `rbac`, `self-service`, `hardening`,
`scripted-actions`, `automation`, `ai`, or `all`); without it only core checks run. The
post-install and post-wizard checks and the feature checks arrive in later build phases.

## Standalone

`nerdio-preflight.pyz` is a single-file Python zipapp attached to this repository's releases.
It needs only what Cloud Shell has (Python 3.9 or later, `az`), installs nothing and has no
`curl | bash` step: download a pinned version, check its SHA-256 against the
[README](../../../README.md#readiness-check-without-the-kit), and run it.

```bash
python3 nerdio-preflight.pyz                         # asks a few questions, then checks
python3 nerdio-preflight.pyz --location eastus2 --users 200 --identity-model entra --no-input
python3 nerdio-preflight.pyz --answers answers.json --format md
```

Inputs come from flags (`--location`, `--identity-model entra|entra_ds|ad_ds`, `--users`,
`--vm-size`, `--set name=value`), then `--answers` (the kit's answer keys), then a short
interview using the kit's own questions. `--no-input` never asks; checks whose inputs are missing
report `skipped`. It resolves only the parameters tagged `readiness` in
`schema/parameters.json`, bundles a copy of that file, and records its version in
`readiness.json` as `parameters_version`. It assumes the Marketplace install, and it never
invents a network to check: the address range and hub are checked only when you give them.
Choices the kit can't build yet (AD DS, for example) are still checked, because Nerdio supports
them.

### Releasing the standalone check

1. Bump `__version__` in `scripts/nerdio/readiness/__init__.py` in a PR and merge it.
2. Tag the merge commit `preflight-v<version>` and push the tag. The `preflight-release`
   workflow runs the tests on Python 3.9, builds the zipapp, signs a build provenance
   attestation and publishes the release with its SHA-256.
3. Rebuild locally (`python3 scripts/build-preflight-pyz.py`) from the tag: the build is
   reproducible, so the checksum must match the release's. Then add the version and checksum to
   the README's table in a PR.

## Statuses and the verdict

| Status | Means |
|---|---|
| `pass` | Checked and fine |
| `warn` | Couldn't be checked fully, or likely to cause trouble; look at it |
| `fail` | Will break the deployment; the `fix` line says what to do |
| `manual` | Only a person can confirm it (licenses, on-premises reachability) |
| `no-access` | The signed-in identity can't read it; the result names the right it needs |
| `skipped` | Out of scope, or an input is missing |

The verdict is `NO-GO` when anything fails, `INCOMPLETE` when nothing ran or every identity or
subscription check came back `no-access`, `GO WITH WARNINGS` when anything is `warn`, `manual` or
`no-access`, and `GO` otherwise, so a run that couldn't see everything is never plain green.
Exit codes: 0 for `GO` and `GO WITH WARNINGS`, 1 for `NO-GO`, 2 for bad usage, 3 for
`INCOMPLETE`. `--strict` also exits 1 on a `warn`; the pipeline uses it.

Output is masked by default: IDs, emails, public IPs, tenant domains, the account's names, and
resource, group and network names (`--names` shows those). `--no-redact` writes everything, only
to a mode-600 file.

## Rights

Every default check only reads: a guard in the engine refuses any `az` command that isn't a
`show` or `list`, and any `az rest` call that isn't a GET, and CI runs every check against
recorded answers to prove it. **Reader** on the subscription (and on the hub network and private
DNS zones where they live elsewhere) plus your own directory read rights cover every default
check. The installer roles Nerdio needs (Global Administrator, or Privileged Role Administrator
plus Cloud Application Administrator; subscription Owner) are checked *for*, not needed *to run*
the check. See [docs/access.md](../../access.md).

## Operator

The `op.*` checks: tools, the Azure cloud (endpoints come from `az cloud show`, never
hard-coded), the sign-in and Cloud Shell's persistent storage.

## Identity

The `id.*` checks: subscription Owner, the Entra roles for admin consent, app registration and,
for AD DS or Entra Domain Services, domain reachability (always `manual`).

## Network

The `net.*` checks: the AVD range against existing networks, the hub network and peering rights,
and existing `privatelink` zones you may want to link instead of creating new ones.

## AVD

The `avd.*` checks: the session host size and its vCPU quota at full scale, and user licenses.

## Nerdio's own readiness script

Nerdio's Solutions Engineering team publishes `Test-NmeDeploymentReadiness.ps1` in the
[Get-Nerdio/NME-SE](https://github.com/Get-Nerdio/NME-SE) repository, linked from Nerdio's
installation preparation article. Facts, from its README:

- It checks the installer's Entra roles, subscription Owner and resource providers, then tests
  **deployability**: it creates throwaway copies of the resources the installer makes, reports a
  blocking Azure Policy by name, tests private endpoints, private DNS, App Service VNet
  integration and outbound reach, and deletes everything.
- It needs **Owner** and **creates resources**, so in a strict tenant running it is itself a change.
- It runs in PowerShell 7 with the Az modules (Cloud Shell's PowerShell mode works), interactively.
- It has no license, so this kit uses it for facts only and never copies, wraps or re-hosts it.

Use ours first (read-only, any time, in the pipeline) and Nerdio's when you need to know whether
Azure Policy will deny the install; our `sub.policy_list` result links it. Read-only policy
evaluation (`sub.policy_eval`) stays Nerdio's job until a spike proves ours.

Nerdio's health page, `<nerdio_url>/public/health/status`, answers unauthenticated and allows
one request per five minutes; the post-install checks will read it.

## Catalogue

Generated from the registry. Stage letters: P pre-install, I post-install, W post-wizard.

<!-- BEGIN GENERATED: readiness-catalogue (./nerdio preflight --list --write) -->
| ID | Stage | Check | Feature | Right needed | Reads with |
|---|---|---|---|---|---|
| `avd.licenses` | P | [AVD user licenses](https://learn.microsoft.com/azure/virtual-desktop/prerequisites) | core | none | - |
| `avd.vcpu` | P | [vCPU quota](https://learn.microsoft.com/azure/quotas/per-vm-quota-requests) | core, automation | Reader on the subscription | az vm list-skus, az vm list-usage |
| `avd.vm_size` | P | [VM size](https://learn.microsoft.com/azure/azure-resource-manager/troubleshooting/error-sku-not-available) | core | Reader on the subscription | az vm list-skus |
| `id.app_registration` | P | [App registration](https://learn.microsoft.com/graph/api/resources/authorizationpolicy) | core | your own default directory read rights | Graph /me/transitiveMemberOf, Graph /policies/authorizationPolicy |
| `id.domain_join_account` | P | [Domain reachability](https://learn.microsoft.com/azure/virtual-desktop/prerequisites) | core | nothing in Azure; a person confirms it | - |
| `id.entra_roles` | P | [Entra admin role](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | your own default directory read rights | Graph /me/transitiveMemberOf |
| `id.sub_owner` | P | [Subscription Owner](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on the subscription | az ad signed-in-user show, az role assignment list |
| `net.hub` | P | [Hub network](https://learn.microsoft.com/azure/virtual-network/virtual-network-peering-overview) | core | Reader on the hub VNet | az network vnet show, az role assignment list |
| `net.overlap` | P | [Address range](https://learn.microsoft.com/azure/virtual-network/virtual-network-peering-overview) | core | Reader on the subscription | az network vnet list, az group list |
| `net.private_dns` | P | [Private DNS](https://learn.microsoft.com/azure/private-link/private-endpoint-dns) | core | Reader on the private DNS zones' subscription | az network private-dns zone list |
| `op.cloud` | P, I, W | [Azure cloud](https://learn.microsoft.com/cli/azure/manage-clouds-azure-cli) | core | none | az cloud show |
| `op.cloudshell_storage` | P | [Cloud Shell storage](https://learn.microsoft.com/azure/cloud-shell/persisting-shell-storage) (kit only) | core | none | environment, ~/clouddrive |
| `op.signin` | P, I, W | [Azure sign-in](https://learn.microsoft.com/cli/azure/authenticate-azure-cli) | core | none | az account show |
| `op.tools` | P | [Tools](https://learn.microsoft.com/azure/cloud-shell/features) | core | none | PATH |
| `sub.app_service` | P | [App Service quota](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on the subscription | az appservice list-locations, ARM Microsoft.Web/locations/usages |
| `sub.nerdio_license` | P | [Nerdio license](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | none | - |
| `sub.policy_list` | P | [Azure Policy](https://learn.microsoft.com/azure/governance/policy/overview) | core | Reader on the subscription | az policy assignment list |
| `sub.providers` | P | [Resource providers](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on the subscription | az provider list |
| `sub.region` | P | [Region](https://learn.microsoft.com/cli/azure/account#az-account-list-locations) | core | Reader on the subscription | az account list-locations |
| `sub.sql` | P | [Azure SQL region](https://learn.microsoft.com/rest/api/sql/capabilities/list-by-location) | core | Reader on the subscription | ARM Microsoft.Sql/locations/capabilities |
<!-- END GENERATED: readiness-catalogue -->
