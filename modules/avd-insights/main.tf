# Azure Monitor AVD Insights Data Collection Rule (DCR), Action Group, and optional
# Consumption Budget for AVD + Nerdio Manager cost governance.

resource "azurerm_monitor_action_group" "avd" {
  name                = "ag-${var.prefix}-avd-ops"
  resource_group_name = var.resource_group_name
  short_name          = "avdops"
  tags                = var.tags

  dynamic "email_receiver" {
    for_each = toset(var.alert_email_receivers)
    content {
      name                    = "ops-${substr(sha1(email_receiver.value), 0, 6)}"
      email_address           = email_receiver.value
      use_common_alert_schema = true
    }
  }

  dynamic "webhook_receiver" {
    for_each = var.webhook_receivers
    content {
      name                    = webhook_receiver.key
      service_uri             = webhook_receiver.value.service_uri
      use_common_alert_schema = webhook_receiver.value.use_common_alert_schema

      dynamic "aad_auth" {
        for_each = webhook_receiver.value.aad_auth == null ? [] : [webhook_receiver.value.aad_auth]
        content {
          object_id      = aad_auth.value.object_id
          identifier_uri = aad_auth.value.identifier_uri
          tenant_id      = aad_auth.value.tenant_id
        }
      }
    }
  }

  dynamic "itsm_receiver" {
    for_each = var.itsm_receivers
    content {
      name                 = itsm_receiver.key
      workspace_id         = itsm_receiver.value.workspace_id
      connection_id        = itsm_receiver.value.connection_id
      ticket_configuration = itsm_receiver.value.ticket_configuration
      region               = itsm_receiver.value.region
    }
  }
}

resource "azurerm_monitor_data_collection_rule" "avd_insights" {
  name                = "microsoft-avd-${var.prefix}-${var.location}"
  resource_group_name = var.resource_group_name
  location            = var.location
  kind                = "Windows"
  tags                = var.tags

  destinations {
    log_analytics {
      workspace_resource_id = var.log_analytics_workspace_id
      name                  = "avd-law"
    }
  }

  data_flow {
    streams      = ["Microsoft-Perf", "Microsoft-Event"]
    destinations = ["avd-law"]
  }

  data_sources {
    performance_counter {
      name                          = "avd-perf-counters"
      streams                       = ["Microsoft-Perf"]
      sampling_frequency_in_seconds = 60
      counter_specifiers = [
        "\\LogicalDisk(C:)\\% Free Space",
        "\\LogicalDisk(C:)\\Avg. Disk Queue Length",
        "\\Memory\\Available Mbytes",
        "\\Memory\\Page Faults/sec",
        "\\Processor Information(_Total)\\% Processor Time",
        "\\User Input Delay per Process(*)\\Max Input Delay",
        "\\User Input Delay per Session(*)\\Max Input Delay",
        "\\RemoteFX Network(*)\\Current TCP RTT",
        "\\RemoteFX Network(*)\\Current UDP Bandwidth",
      ]
    }

    windows_event_log {
      name    = "avd-event-logs"
      streams = ["Microsoft-Event"]
      x_path_queries = [
        "Microsoft-Windows-TerminalServices-RemoteConnectionManager/Admin!*[System[(Level=2 or Level=3 or Level=4 or Level=0)]]",
        "Microsoft-Windows-TerminalServices-LocalSessionManager/Operational!*[System[(Level=2 or Level=3 or Level=4 or Level=0)]]",
        "System!*",
        "Microsoft-FSLogix-Apps/Operational!*[System[(Level=2 or Level=3 or Level=4 or Level=0)]]",
        "Microsoft-FSLogix-Apps/Admin!*[System[(Level=2 or Level=3 or Level=4 or Level=0)]]",
      ]
    }
  }
}

locals {
  has_alert_receivers = (
    length(var.alert_email_receivers) > 0 ||
    length(var.webhook_receivers) > 0 ||
    length(var.itsm_receivers) > 0
  )
}

resource "azurerm_consumption_budget_resource_group" "avd" {
  count             = var.monthly_budget_amount != null && local.has_alert_receivers ? 1 : 0
  name              = "budget-${var.prefix}-avd"
  resource_group_id = var.resource_group_id
  amount            = var.monthly_budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = var.alert_email_receivers
    contact_groups = [azurerm_monitor_action_group.avd.id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_emails = var.alert_email_receivers
    contact_groups = [azurerm_monitor_action_group.avd.id]
  }
}
