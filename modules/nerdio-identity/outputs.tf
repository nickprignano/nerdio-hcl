output "application_id" {
  description = "Application object path (/applications/<object id>), for credentials added outside this module. Null when create_nerdio_app is false."
  value       = try(azuread_application.nerdio[0].id, null)
}

output "client_id" {
  description = "Application (client) ID. Enter as App ID under \"Use existing AD app\" on the Nerdio install page."
  value       = local.nerdio_client_id
}

output "service_principal_object_id" {
  description = "Enterprise application object ID. Enter as Service Principal ID on the Nerdio install page."
  value       = local.nerdio_service_principal_object_id
}

output "client_secret" {
  description = "Client secret value. Enter as App Secret on the Nerdio install page."
  value       = try(azuread_application_password.nerdio[0].value, null)
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

output "rest_api_client_object_id" {
  description = "REST API client app object ID (for a secrets broker that adds passwords to it), or null."
  value       = try(azuread_application.rest_client[0].object_id, null)
}

output "rest_api_client_secret_version" {
  description = "Number that changes whenever the REST API client secret is replaced (its start time), for write-only secret versions. Null when there is no secret."
  value       = try(parseint(formatdate("YYYYMMDDhhmmss", azuread_application_password.rest_client[0].start_date), 10), null)
}

output "rest_api_client_secret_end_date" {
  description = "When the REST API client secret expires (RFC 3339), or null."
  value       = try(azuread_application_password.rest_client[0].end_date, null)
}
