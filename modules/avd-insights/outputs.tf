output "data_collection_rule_id" {
  description = "AVD Insights Data Collection Rule ARM ID."
  value       = azurerm_monitor_data_collection_rule.avd_insights.id
}

output "action_group_id" {
  description = "Azure Monitor Action Group ARM ID."
  value       = azurerm_monitor_action_group.avd.id
}

output "budget_id" {
  description = "Consumption Budget ID when monthly_budget_amount is set, else null."
  value       = try(azurerm_consumption_budget_resource_group.avd[0].id, null)
}
