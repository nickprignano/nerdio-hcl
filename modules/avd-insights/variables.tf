variable "prefix" {
  description = "Short naming prefix."
  type        = string
}

variable "location" {
  description = "Azure region for the AVD Insights Data Collection Rule."
  type        = string
}

variable "resource_group_name" {
  description = "Monitoring resource group name."
  type        = string
}

variable "resource_group_id" {
  description = "Monitoring resource group ARM ID (used as budget scope when monthly_budget_amount is set)."
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ARM ID receiving AVD session host performance counters and Windows event logs."
  type        = string
}

variable "alert_email_receivers" {
  description = "Email addresses notified by AVD Insights alerts and budget thresholds."
  type        = list(string)
  default     = []
}

variable "webhook_receivers" {
  description = "Webhook receivers notified by the AVD Insights Action Group (e.g. ServiceNow Event Management /api/sn_em_connector/em/inbound_event?source=azuremonitor or Scripted REST APIs). Supports Entra ID OAuth (aad_auth) so no shared webhook secret is stored in URLs."
  type = map(object({
    service_uri             = string
    use_common_alert_schema = optional(bool, true)
    aad_auth = optional(object({
      object_id      = string
      identifier_uri = optional(string)
      tenant_id      = optional(string)
    }))
  }))
  default = {}
}

variable "itsm_receivers" {
  description = "Azure ITSM Connector receivers notified by the AVD Insights Action Group (e.g. ServiceNow ITSM Connector linked to a Log Analytics workspace; workspace_id uses '<subscription_id>|<workspace_uuid>')."
  type = map(object({
    workspace_id         = string
    connection_id        = string
    ticket_configuration = string
    region               = string
  }))
  default = {}
}

variable "monthly_budget_amount" {
  description = "Optional monthly Azure Consumption Budget amount (null skips the budget resource)."
  type        = number
  default     = null
}

variable "budget_start_date" {
  description = "Start date (YYYY-MM-01T00:00:00Z) required when monthly_budget_amount is set."
  type        = string
  default     = "2026-01-01T00:00:00Z"
}

variable "tags" {
  description = "Tags applied to all monitoring resources."
  type        = map(string)
  default     = {}
}
