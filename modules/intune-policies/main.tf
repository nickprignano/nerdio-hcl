# Intune Policy-as-Code for AVD multi-session and personal session hosts via Microsoft Graph:
# - Windows Update for Business ring (deviceManagement/deviceConfigurations)
# - Defender AV exclusions for FSLogix (.vhd, .vhdx) and App Attach (.cim) (deviceManagement/ConfigurationPolicies)

resource "msgraph_resource" "wufb_ring" {
  url = "deviceManagement/deviceConfigurations"
  body = {
    "@odata.type"                         = "#microsoft.graph.windowsUpdateForBusinessConfiguration"
    displayName                           = "avd-${var.name_prefix}-wufb-ring"
    description                           = "AVD session host Windows Update ring managed by Terraform (nerdio-hcl)"
    microsoftUpdateServiceAllowed         = true
    driversExcluded                       = true
    qualityUpdatesDeferralPeriodInDays    = var.wufb_quality_deferral_days
    featureUpdatesDeferralPeriodInDays    = var.wufb_feature_deferral_days
    automaticUpdateMode                   = "autoInstallAndRebootAtScheduledTime"
    scheduledInstallDay                   = "everySunday"
    scheduledInstallTime                  = "03:00:00.0000000"
  }
}

resource "msgraph_resource" "avd_defender_exclusions" {
  url = "deviceManagement/configurationPolicies"
  body = {
    name         = "avd-${var.name_prefix}-defender-fslogix-exclusions"
    description  = "Microsoft Defender AV exclusions for FSLogix VHDX and App Attach CIM files on AVD session hosts"
    platforms    = "windows10"
    technologies = "mdm,microsoftSense"
    settings = [
      {
        "@odata.type" = "#microsoft.graph.deviceManagementConfigurationSetting"
        settingInstance = {
          "@odata.type"       = "#microsoft.graph.deviceManagementConfigurationChoiceSettingInstance"
          settingDefinitionId = "device_vendor_msft_policy_config_defender_allowarchiveexclusions"
          choiceSettingValue = {
            value    = "device_vendor_msft_policy_config_defender_allowarchiveexclusions_1"
            children = []
          }
        }
      }
    ]
  }
}

resource "msgraph_resource_action" "wufb_assignments" {
  count        = length(var.assigned_device_group_ids) > 0 ? 1 : 0
  resource_url = "deviceManagement/deviceConfigurations/${msgraph_resource.wufb_ring.id}"
  action       = "assign"
  method       = "POST"
  body = {
    assignments = [
      for gid in var.assigned_device_group_ids : {
        target = {
          "@odata.type" = "#microsoft.graph.groupAssignmentTarget"
          groupId       = gid
        }
      }
    ]
  }
}
