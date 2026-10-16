output "address" {
  description = "OpenBao URL for the vault provider in stage 2."
  value       = local.address
}

output "ca_cert_pem" {
  description = "OpenBao's self-signed TLS certificate, which clients trust as the CA. Public; it changes when Key Vault renews it."
  value       = <<-EOT
    -----BEGIN CERTIFICATE-----
    ${join("\n", regexall(".{1,64}", azurerm_key_vault_certificate.tls.certificate_data_base64))}
    -----END CERTIFICATE-----
  EOT
}

output "login_scope" {
  description = "Scope for `az account get-access-token --scope`, to sign in to OpenBao from Cloud Shell."
  value       = "api://${azuread_application.login.client_id}/login"
}

output "auth_mounts" {
  description = "JWT auth mounts: entra for Cloud Shell users, github for Actions jobs (when configured)."
  value       = { entra = "entra", github = var.github_oidc == null ? null : "github" }
}

output "secret_role" {
  description = "Azure secrets role (and login role) that mints the Nerdio REST secret."
  value       = local.names.secret_role
}

