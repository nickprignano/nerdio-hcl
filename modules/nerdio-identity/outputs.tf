output "client_id" {
  description = "Application (client) ID. Enter as App ID under \"Use existing AD app\" on the Nerdio install page."
  value       = azuread_application.nerdio.client_id
}

output "service_principal_object_id" {
  description = "Enterprise application object ID. Enter as Service Principal ID on the Nerdio install page."
  value       = azuread_service_principal.nerdio.object_id
}

output "client_secret" {
  description = "Client secret value. Enter as App Secret on the Nerdio install page."
  value       = azuread_application_password.nerdio.value
  sensitive   = true
}

output "rest_api_client_id" {
  description = "REST API client app ID, or null."
  value       = try(azuread_application.rest_client[0].client_id, null)
}

output "rest_api_client_secret" {
  description = "REST API client secret, or null."
  value       = try(azuread_application_password.rest_client[0].value, null)
  sensitive   = true
}
