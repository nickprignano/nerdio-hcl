---
title: "azurerm 5.x and azuread 3.x"
summary: "azurerm 5.x and azuread 3.x changes we hit, with fixes"
topic: terraform
status: verified
last_reviewed: 2026-10-28
---

# azurerm 5.x and azuread 3.x

Changes hit while moving the kit from azurerm 4.x to 5.x. Versions at the time:
[azurerm 5.10.0](https://github.com/hashicorp/terraform-provider-azurerm/releases/tag/v5.10.0) and
[azurerm 5.11.0](https://github.com/hashicorp/terraform-provider-azurerm/releases/tag/v5.11.0)
(last 4.x was 4.81.0), azuread 3.10.0, Terraform 1.16.6.

## Breaking changes and fixes

| Resource | Error / warning | Fix |
|---|---|---|
| `azurerm_subnet` | `An argument named "service_endpoints" is not expected here.` | Use repeatable `service_endpoint { service = "..." }` blocks, e.g. `dynamic "service_endpoint"` over a list. The block also takes an optional `network_identifier`. |
| `azurerm_private_dns_zone_virtual_network_link` | `The argument "private_dns_zone_id" is required` | Set `private_dns_zone_id`. `resource_group_name` and `private_dns_zone_name` are no longer accepted (including when linking existing hub or cross-region Private DNS zones). A new `resolution_policy` argument exists. |
| `azurerm_storage_account` | `public_network_access_enabled` deprecated, removed in 6.0 | Use `public_network_access = "Disabled"` (or `"Enabled"`). |
| `azurerm_windows_virtual_machine_scale_set` | `An argument named "enable_accelerated_networking" is not expected here.` | Inside `network_interface {}`, use `accelerated_networking_enabled = true`. |
| `azurerm_netapp_volume` | `This object has no argument, nested block, or exported attribute named "mount_ip_addresses".` | For SMB (`CIFS`) volumes, build the UNC path from `\\${azurerm_netapp_account.this.name}\${azurerm_netapp_volume.profiles.volume_path}`. |

## Other 5.x schema notes

- `azurerm_subnet` exposes both `network_security_group_id` and `route_table_id` as `Computed: true`
  (verified in `internal/services/network/subnet_resource.go`), alongside write-only
  `network_security_group_id_wo` and `route_table_id_wo` arguments; keep using
  `azurerm_subnet_network_security_group_association` and `azurerm_subnet_route_table_association`.
- `azurerm_subnet` adds `default_outbound_access_enabled` and `sharing_scope`.
- Several resources gained write-only `*_wo` / `*_wo_version` arguments for secrets, which keep
  values out of state.

## azuread 3.x

No breaking changes hit. Patterns that validated are listed in
[../nerdio/entra-app.md](../nerdio/entra-app.md#azuread-3x-patterns-that-worked).

## Finding schema changes fast

```bash
terraform providers schema -json | jq '.provider_schemas[].resource_schemas["azurerm_subnet"]'
```

Pin modules with a floor (`>= 5.0`) and root modules with a pessimistic constraint (`~> 5.0`).
