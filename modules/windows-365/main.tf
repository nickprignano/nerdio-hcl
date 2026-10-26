# Windows 365 Enterprise Cloud PC infrastructure-as-code alongside Nerdio Manager:
# - Azure Network Connection (deviceManagement/virtualEndpoint/onPremisesConnections)
# - Provisioning Policy (deviceManagement/virtualEndpoint/provisioningPolicies)
# - User Settings Policy (deviceManagement/virtualEndpoint/userSettings)

resource "msgraph_resource" "azure_network_connection" {
  url = "deviceManagement/virtualEndpoint/onPremisesConnections"
  body = {
    displayName      = "anc-${var.name_prefix}-w365"
    connectionType   = var.join_type
    subscriptionId   = var.subscription_id
    resourceGroupId  = var.resource_group_id
    virtualNetworkId = var.virtual_network_id
    subnetId         = var.subnet_id
  }
}

resource "msgraph_resource" "provisioning_policy" {
  url = "deviceManagement/virtualEndpoint/provisioningPolicies"
  body = {
    displayName            = "w365-${var.name_prefix}-policy"
    description            = "Managed by Terraform (nerdio-hcl)"
    provisioningType       = "dedicated"
    managedBy              = "windows365"
    enableSingleSignOn     = var.enable_single_sign_on
    imageId                = var.image_id
    imageType              = var.image_type
    onPremisesConnectionId = msgraph_resource.azure_network_connection.id
    domainJoinConfigurations = [
      {
        domainJoinType         = var.join_type
        onPremisesConnectionId = msgraph_resource.azure_network_connection.id
      }
    ]
    microsoftManagedDesktop = {
      managedType = "notManaged"
      profile     = ""
    }
  }
}

resource "msgraph_resource" "user_settings" {
  url = "deviceManagement/virtualEndpoint/userSettings"
  body = {
    displayName       = "w365-${var.name_prefix}-usersettings"
    localAdminEnabled = var.local_admin_enabled
    resetEnabled      = true
    restorePointSetting = {
      frequencyType      = "twelveHours"
      frequencyInHours   = var.restore_point_frequency_hours
      userRestoreEnabled = true
    }
  }
}

resource "msgraph_resource_action" "policy_assignments" {
  count        = length(var.assigned_group_object_ids) > 0 ? 1 : 0
  resource_url = "deviceManagement/virtualEndpoint/provisioningPolicies/${msgraph_resource.provisioning_policy.id}"
  action       = "assign"
  method       = "POST"
  body = {
    assignments = [
      for gid in var.assigned_group_object_ids : {
        id = gid
        target = {
          "@odata.type" = "#microsoft.graph.cloudPcManagementGroupAssignmentTarget"
          groupId       = gid
        }
      }
    ]
  }
}
