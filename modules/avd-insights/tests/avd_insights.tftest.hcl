mock_provider "azurerm" {}

variables {
  prefix                     = "contoso-nme"
  location                   = "eastus2"
  resource_group_name        = "rg-contoso-avd-monitoring"
  resource_group_id          = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-contoso-avd-monitoring"
  log_analytics_workspace_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-contoso-avd-monitoring/providers/Microsoft.OperationalInsights/workspaces/law-contoso"
}

run "servicenow_webhook_with_aad_auth_and_budget" {
  command = plan

  variables {
    monthly_budget_amount = 3000
    webhook_receivers = {
      servicenow-events = {
        service_uri             = "https://contoso.service-now.com/api/sn_em_connector/em/inbound_event?source=azuremonitor"
        use_common_alert_schema = true
        aad_auth = {
          object_id      = "00000000-0000-0000-0000-000000000000"
          identifier_uri = "api://contoso-servicenow-azuremonitor"
          tenant_id      = "00000000-0000-0000-0000-000000000000"
        }
      }
    }
    itsm_receivers = {
      servicenow-itsm = {
        workspace_id         = "00000000-0000-0000-0000-000000000000|00000000-0000-0000-0000-000000000000"
        connection_id        = "00000000-0000-0000-0000-000000000000"
        ticket_configuration = "{\"PayloadRevision\":0,\"WorkItemType\":\"Incident\"}"
        region               = "eastus2"
      }
    }
  }

  assert {
    condition     = length(azurerm_monitor_action_group.avd.webhook_receiver) == 1
    error_message = "Expected one ServiceNow webhook_receiver on the AVD Insights Action Group."
  }

  assert {
    condition     = length(azurerm_monitor_action_group.avd.itsm_receiver) == 1
    error_message = "Expected one ServiceNow itsm_receiver on the AVD Insights Action Group."
  }

  assert {
    condition     = length(azurerm_consumption_budget_resource_group.avd) == 1
    error_message = "Expected the monthly budget resource to be created when webhook/ITSM receivers are configured even without email receivers."
  }
}
