---
title: "Known errors"
summary: "Known errors: symptom, cause, fix and source"
topic: troubleshooting
status: verified
last_reviewed: 2026-10-16
---

# Known errors

A catalog of errors hit while deploying or running the kit, so the next person (or the chat
assistant's `troubleshoot` skill, see [../chat-assistant.md](../chat-assistant.md#8-deployment-troubleshooting))
can match a symptom to a fix without re-diagnosing it.

Each entry has four parts: the **symptom** (the exact error text where there is one), the
**cause**, the **fix**, and the **source** (a KB page, doc or issue). Strip any tenant, subscription,
resource or user names from pasted errors before adding them (see
[../README.md](../README.md#keep-it-public-safe)).

<!-- BEGIN GENERATED: known-errors (edit the YAML, then run scripts/kb/build.py) -->
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| `An argument named "service_endpoints" is not expected here.` on `azurerm_subnet` | azurerm 5.x replaced the list argument with blocks | Use repeatable `service_endpoint { service = "..." }` blocks | [azurerm-5.md](../terraform/azurerm-5.md#breaking-changes-and-fixes) |
| `The argument "private_dns_zone_id" is required` on a private DNS zone VNet link | azurerm 5.x changed how the zone is referenced | Set `private_dns_zone_id`; drop `resource_group_name` and `private_dns_zone_name` | [azurerm-5.md](../terraform/azurerm-5.md#breaking-changes-and-fixes) |
| `public_network_access_enabled` deprecation warning on `azurerm_storage_account` | Renamed in azurerm 5.x, removed in 6.0 | Use `public_network_access = "Disabled"` | [azurerm-5.md](../terraform/azurerm-5.md#breaking-changes-and-fixes) |
| `terraform init` can't download providers or Packer plugins | Registry blocked by the network | Use a `filesystem_mirror` or a local plugin path | [restricted-networks.md](../terraform/restricted-networks.md) |
| Nerdio Azure runbook scripted actions fail after hardening | The scripted-actions storage account was made private | Use a Hybrid Runbook Worker, or leave that account public | [platform.md](../nerdio/platform.md#hardening-private-endpoints) |
| `terraform init` in 02-nerdio-config fails with "Could not retrieve the list of available versions for provider nerdio/nme", or plan says "Inconsistent dependency lock file" | `~/.terraformrc` still has the old `dev_overrides` entry for nerdio/nme; stage 2 now also needs Registry providers, so it uses `terraform init` | Run `scripts/install-nme-provider.sh` again; it replaces the old block with a local plugin directory (a backup is kept as `.terraformrc.bak`) | [link](https://developer.hashicorp.com/terraform/cli/config/config-file#development-overrides-for-provider-developers) |
| Cloud Shell shows "Requesting a Cloud Shell" mid-apply or mid-destroy, and a rerun stops with `Error acquiring the state lock` | Cloud Shell closes after about 20 minutes without a keypress, or when a tablet sleeps the tab. A run that was waiting at its "yes" prompt can survive and keep holding the lock | Check `pgrep -a terraform` first. If a run is still there, stop it with `kill -INT <pid>`; if none is, `terraform force-unlock -force "$(jq -r .ID .terraform.tfstate.lock.info)"`. For long runs, review a saved plan (`terraform plan -destroy -out=destroy.tfplan`) and apply it with `nohup terraform apply destroy.tfplan > ~/destroy.log 2>&1 &`. The lasting fix is the deploy pipeline *(unverified)* | [chatbot-first.md](../chatbot-first.md) |
| A destroy fails on the Nerdio resource group with `the Resource Group still contains Resources`, naming `microsoft.insights/actiongroups/Application Insights Smart Detection` | Azure creates that action group by itself when Application Insights is created, so it was never in Terraform's state. The azurerm provider refuses to delete a resource group that still holds resources it doesn't manage | Check that it is the only resource listed, then `az monitor action-group delete -g <group> -n "Application Insights Smart Detection"`, plan the destroy again and apply it. Don't turn off `prevent_deletion_if_contains_resources` to get past it; that check is what caught it | [chatbot-first.md](../chatbot-first.md) |
| `Operation cannot be completed without additional quota` on the App Service plan; readiness check `sub.app_service` fails | The subscription's App Service quota for the plan's tier (B3 by default; more with Insights) is 0 or used up in that region, common on trial and sandbox subscriptions | `./nerdio fix quota --sku B3 --location <region> --limit <n>`, or pick a region where `./nerdio preflight --regions` passes *(unverified)* | [readiness.md](../nerdio/readiness.md) |
| `RegionDoesNotAllowProvisioning` creating the SQL server; readiness check `sub.sql` fails | The region doesn't accept new SQL servers for this subscription | Pick another region, or ask Azure Support for region access (Service and subscription limits) *(unverified)* | [readiness.md](../nerdio/readiness.md) |
| App Service VNet integration fails on an existing subnet; readiness check `net.subnets` fails | The integration subnet isn't delegated to Microsoft.Web/serverFarms | `az network vnet subnet update --ids <subnet id> --delegations Microsoft.Web/serverFarms` *(unverified)* | [readiness.md](../nerdio/readiness.md) |
| Session hosts never register with AVD; readiness check `net.outbound` fails | The subnet has no NAT gateway, firewall route or default outbound access (VNets created after 31 March 2026 get none) | Attach a NAT gateway, or route 0.0.0.0/0 to your firewall *(unverified)* | [readiness.md](../nerdio/readiness.md) |
<!-- END GENERATED: known-errors -->

## Adding an entry

Add an entry when an error took real time to diagnose. Either open a **Known error** issue (a
workflow turns it into a pull request once a maintainer accepts it), or add it to
[known-errors.yaml](known-errors.yaml) and run `python3 scripts/kb/build.py` to regenerate the
table above. Set `status: unverified` if the fix worked once but the cause is a guess.
