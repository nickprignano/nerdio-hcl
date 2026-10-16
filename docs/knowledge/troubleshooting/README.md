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
<!-- END GENERATED: known-errors -->

## Adding an entry

Add an entry when an error took real time to diagnose. Either open a **Known error** issue (a
workflow turns it into a pull request once a maintainer accepts it), or add it to
[known-errors.yaml](known-errors.yaml) and run `python3 scripts/kb/build.py` to regenerate the
table above. Set `status: unverified` if the fix worked once but the cause is a guess.
