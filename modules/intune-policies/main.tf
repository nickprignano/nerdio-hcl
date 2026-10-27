# Intune Policy-as-Code for AVD multi-session and personal session hosts via Microsoft Graph:
# - Windows Update for Business ring (deviceManagement/deviceConfigurations)
# - Defender AV exclusions for FSLogix (.vhd, .vhdx) and App Attach (.cim) (deviceManagement/ConfigurationPolicies)

resource "msgraph_resource" "wufb_ring" {
  url = "deviceManagement/deviceConfigurations"
  body = {
    "@odata.type"                      = "#microsoft.graph.windowsUpdateForBusinessConfiguration"
    displayName                        = "avd-${var.name_prefix}-wufb-ring"
    description                        = "AVD session host Windows Update ring managed by Terraform (nerdio-hcl)"
    microsoftUpdateServiceAllowed      = true
    driversExcluded                    = true
    qualityUpdatesDeferralPeriodInDays = var.wufb_quality_deferral_days
    featureUpdatesDeferralPeriodInDays = var.wufb_feature_deferral_days
    automaticUpdateMode                = "autoInstallAndRebootAtScheduledTime"
    scheduledInstallDay                = "everySunday"
    scheduledInstallTime               = "03:00:00.0000000"
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

resource "msgraph_resource" "avd_conditional_access" {
  count = try(var.conditional_access.enabled, false) ? 1 : 0
  url   = "identity/conditionalAccess/policies"
  body = {
    displayName = "ca-${var.name_prefix}-avd-w365-mfa"
    state       = coalesce(var.conditional_access.state, "enabledForReportingButNotEnforced")
    conditions = {
      applications = {
        includeApplications = [
          "9cdead84-a844-4324-93f2-b2e6bb768d07", # Azure Virtual Desktop
          "270efc09-cd0d-444b-a71f-39af4910ec45", # Windows Cloud Login
        ]
      }
      users = {
        includeGroups = var.conditional_access.include_group_ids
        excludeGroups = var.conditional_access.exclude_group_ids
      }
    }
    grantControls = {
      operator        = "AND"
      builtInControls = var.conditional_access.built_in_controls
    }
    sessionControls = {
      signInFrequency = {
        value              = var.conditional_access.sign_in_max_hours
        type               = "hours"
        isEnabled          = true
        authenticationType = "primaryAndSecondaryAuthentication"
      }
    }
  }
}
