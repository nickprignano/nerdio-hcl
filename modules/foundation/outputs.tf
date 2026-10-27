output "resource_group_names" {
  description = "Resource group names keyed by role."
  value       = { for k, rg in local.all_resource_groups : k => rg.name }
}

output "resource_group_ids" {
  description = "Resource group IDs keyed by role."
  value       = { for k, rg in local.all_resource_groups : k => rg.id }
}

output "log_analytics_workspace_id" {
  description = "AVD Log Analytics workspace ID, or null when not created."
  value       = try(azurerm_log_analytics_workspace.avd[0].id, null)
}
