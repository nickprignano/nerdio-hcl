output "azure_network_connection_id" {
  description = "Windows 365 Azure Network Connection ID."
  value       = msgraph_resource.azure_network_connection.id
}

output "provisioning_policy_id" {
  description = "Windows 365 Cloud PC Provisioning Policy ID."
  value       = msgraph_resource.provisioning_policy.id
}

output "user_settings_id" {
  description = "Windows 365 Cloud PC User Settings ID."
  value       = msgraph_resource.user_settings.id
}
