variable "prefix" {
  description = "Short naming prefix."
  type        = string
}

variable "control_plane_location" {
  description = "Azure region for the CMK Key Vault (or the default region when creating a new Key Vault)."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name for the CMK Key Vault (when creating one) and control-plane encryption resources."
  type        = string
}

variable "existing_key_vault_id" {
  description = "Optional existing RBAC Key Vault ARM ID to host the CMK RSA key. When null, the module creates a dedicated Key Vault with purge protection enabled."
  type        = string
  default     = null
}

variable "key_vault_name" {
  description = "Optional custom name for the CMK Key Vault when existing_key_vault_id is null (3-24 alphanumeric/hyphens)."
  type        = string
  default     = null
}

variable "key_name" {
  description = "Name of the RSA Customer-Managed Key in Key Vault."
  type        = string
  default     = "cmk-avd-disk-encryption"
}

variable "key_size" {
  description = "RSA key size in bits (2048, 3072, or 4096)."
  type        = number
  default     = 3072
}

variable "rotation_period" {
  description = "ISO-8601 duration before automatic Key Vault key rotation (for example, P1Y for 1 year)."
  type        = string
  default     = "P1Y"
}

variable "regions" {
  description = "Workload regions keyed by region key, each getting a regional Disk Encryption Set (DES) in its hostpools resource group."
  type = map(object({
    location            = string
    resource_group_name = string
  }))
}

variable "deployer_object_id" {
  description = "Object ID of the identity running Terraform (granted Key Vault Crypto Officer when creating a Key Vault)."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to all CMK resources."
  type        = map(string)
  default     = {}
}
