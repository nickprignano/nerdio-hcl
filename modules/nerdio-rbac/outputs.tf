output "role_definition_id" {
  description = "Custom role definition resource ID assigned to Nerdio Manager."
  value       = azurerm_role_definition.nerdio_operator.role_definition_resource_id
}

output "role_assignment_ids" {
  description = "Role assignment IDs on each managed resource group."
  value       = { for k, ra in azurerm_role_assignment.managed_rgs : k => ra.id }
}
