variable "display_name" {
  description = "App registration name. Change it when running more than one Nerdio Manager in a tenant."
  type        = string
  default     = "nerdio-nmw-app"
}

variable "app_service_hostname" {
  description = "Default hostname of the Nerdio Manager App Service, e.g. nmw-app-abc123.azurewebsites.net."
  type        = string
}

variable "owner_object_ids" {
  description = "Object IDs added as owners of the app and service principal. Nerdio expects the subscription Owner who runs the install to be one. The identity running Terraform is always added."
  type        = list(string)
  default     = []
}

variable "wvd_admin_object_ids" {
  description = "Users granted the WVD Admin app role (full Nerdio admin). Include whoever finishes the setup wizard."
  type        = list(string)
  default     = []
}

variable "grant_admin_consent" {
  description = "Grant tenant-wide admin consent from Terraform. Needs Global Administrator or Privileged Role Administrator on the identity running Terraform; otherwise consent in the portal."
  type        = bool
  default     = false
}

variable "enable_mail_send" {
  description = "Request Graph Mail.Send so Nerdio can send email notifications."
  type        = bool
  default     = false
}

variable "secret_rotation_days" {
  description = "Client secret lifetime. Terraform replaces the secret once it passes this age; push the new value to Nerdio afterwards."
  type        = number
  default     = 365
}

variable "create_rest_api_client" {
  description = "Also create the REST API client app used by the Nerdio REST API and NerdioManagerPowerShell."
  type        = bool
  default     = false
}

variable "create_rest_api_client_secret" {
  description = "Create a long-lived secret on the REST API client app. False when a secrets broker (the optional OpenBao module) mints short-lived ones per run."
  type        = bool
  default     = true
}

variable "rest_api_client_extra_owner_object_ids" {
  description = "Extra owners of the REST API client app, such as the OpenBao module's managed identity, so it can manage the app's passwords with Application.ReadWrite.OwnedBy."
  type        = list(string)
  default     = []
}

variable "create_client_secret" {
  description = "Create a client secret on the Nerdio app. Needed for Nerdio's \"Use existing AD app\" install path; modules/nerdio-core signs in with Key Vault certificates instead."
  type        = bool
  default     = true
}

variable "deployer_object_id" {
  description = "Object ID of the identity that applies this configuration. Null means whoever runs Terraform. The deploy pipeline sets it, because it plans as a read-only identity and applies as another."
  type        = string
  default     = null
}
