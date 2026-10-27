# Custom least-privilege Azure RBAC role definition for Nerdio Manager, replacing broad
# Contributor assignments on managed resource groups with explicit Compute, DesktopVirtualization,
# Network, Storage, RecoveryServices, Insights, and ManagedIdentity permissions (and blocking
# Microsoft.Authorization/*/Write and Delete so Nerdio cannot widen its own RBAC).

locals {
  subscription_scope = "/subscriptions/${var.subscription_id}"
  assignable_scopes = distinct(concat(
    [local.subscription_scope],
    values(var.managed_resource_group_ids)
  ))
}

resource "azurerm_role_definition" "nerdio_operator" {
  name        = "Nerdio Manager Least-Privilege Operator (${var.prefix})"
  scope       = local.subscription_scope
  description = "Least-privilege custom role for Nerdio Manager for Enterprise on managed AVD spoke resource groups (managed by nerdio-hcl)."

  permissions {
    actions = distinct(concat([
      "Microsoft.Compute/virtualMachines/*",
      "Microsoft.Compute/disks/*",
      "Microsoft.Compute/snapshots/*",
      "Microsoft.Compute/images/*",
      "Microsoft.Compute/galleries/*",
      "Microsoft.Compute/diskEncryptionSets/read",
      "Microsoft.Compute/availabilitySets/*",
      "Microsoft.Compute/proximityPlacementGroups/*",
      "Microsoft.Compute/restorePointCollections/*",
      "Microsoft.DesktopVirtualization/*",
      "Microsoft.Network/virtualNetworks/read",
      "Microsoft.Network/virtualNetworks/subnets/read",
      "Microsoft.Network/virtualNetworks/subnets/join/action",
      "Microsoft.Network/networkInterfaces/*",
      "Microsoft.Network/networkSecurityGroups/read",
      "Microsoft.Network/networkSecurityGroups/join/action",
      "Microsoft.Network/applicationSecurityGroups/read",
      "Microsoft.Network/applicationSecurityGroups/joinIpConfiguration/action",
      "Microsoft.Storage/storageAccounts/read",
      "Microsoft.Storage/storageAccounts/listKeys/action",
      "Microsoft.Storage/storageAccounts/fileServices/*",
      "Microsoft.Storage/storageAccounts/blobServices/*",
      "Microsoft.NetApp/netAppAccounts/read",
      "Microsoft.NetApp/netAppAccounts/capacityPools/*",
      "Microsoft.RecoveryServices/vaults/*",
      "Microsoft.Insights/metricAlerts/*",
      "Microsoft.Insights/diagnosticSettings/*",
      "Microsoft.OperationalInsights/workspaces/read",
      "Microsoft.OperationalInsights/workspaces/sharedKeys/action",
      "Microsoft.ManagedIdentity/userAssignedIdentities/read",
      "Microsoft.ManagedIdentity/userAssignedIdentities/assign/action",
      "Microsoft.Resources/deployments/*",
      "Microsoft.Resources/subscriptions/resourceGroups/read",
      "Microsoft.Resources/tags/*",
    ], var.extra_actions))

    not_actions = [
      "Microsoft.Authorization/*/Write",
      "Microsoft.Authorization/*/Delete",
      "Microsoft.Authorization/elevateAccess/Action",
      "Microsoft.Blueprint/blueprintAssignments/write",
      "Microsoft.Blueprint/blueprintAssignments/delete",
    ]
  }

  assignable_scopes = local.assignable_scopes
}

resource "azurerm_role_assignment" "managed_rgs" {
  for_each           = var.managed_resource_group_ids
  scope              = each.value
  role_definition_id = azurerm_role_definition.nerdio_operator.role_definition_resource_id
  principal_id       = var.nerdio_service_principal_object_id
}

resource "azurerm_role_assignment" "subscription_reader" {
  scope                = local.subscription_scope
  role_definition_name = "Reader"
  principal_id         = var.nerdio_service_principal_object_id
}

resource "azurerm_role_assignment" "subscription_backup_reader" {
  scope                = local.subscription_scope
  role_definition_name = "Backup Reader"
  principal_id         = var.nerdio_service_principal_object_id
}
