---
title: "azurerm 5.x and azuread 3.x"
summary: "azurerm 5.x and azuread 3.x changes we hit, with fixes"
topic: terraform
status: partial
last_reviewed: 2026-10-16
---

# azurerm 5.x and azuread 3.x

Changes hit while moving the kit from azurerm 4.x to 5.x. Versions at the time: azurerm 5.10.0
(last 4.x was 4.81.0), azuread 3.10.0, Terraform 1.16.6.

## Breaking changes and fixes

| Resource | Error / warning | Fix |
|---|---|---|
| `azurerm_subnet` | `An argument named "service_endpoints" is not expected here.` | Use repeatable `service_endpoint { service = "..." }` blocks, e.g. `dynamic "service_endpoint"` over a list. The block also takes an optional `network_identifier`. |
| `azurerm_private_dns_zone_virtual_network_link` | `The argument "private_dns_zone_id" is required` | Set `private_dns_zone_id`. `resource_group_name` and `private_dns_zone_name` are no longer accepted. A new `resolution_policy` argument exists. |
| `azurerm_storage_account` | `public_network_access_enabled` deprecated, removed in 6.0 | Use `public_network_access = "Disabled"` (or `"Enabled"`). |

## Other 5.x schema notes

- `azurerm_subnet` exposes `network_security_group_id` as computed-only; keep using
  `azurerm_subnet_network_security_group_association`. *Unverified:* the same for `route_table_id`.
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
