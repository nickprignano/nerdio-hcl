variable "prefix" {
  description = "Short naming prefix for the custom Azure role definition."
  type        = string
}

variable "subscription_id" {
  description = "Primary Azure subscription ID where the custom role is defined."
  type        = string
}

variable "nerdio_service_principal_object_id" {
  description = "Object ID of Nerdio Manager's service principal."
  type        = string
}

variable "managed_resource_group_ids" {
  description = "Resource group ARM IDs managed by Nerdio Manager (nerdio, hostpools, network, storage), keyed by logical name."
  type        = map(string)
}

variable "extra_actions" {
  description = "Optional extra Azure RBAC data/control actions to add to the custom role."
  type        = list(string)
  default     = []
}
