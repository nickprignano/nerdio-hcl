variable "resource_group_name" {
  description = "Empty resource group that receives the Nerdio Manager core resources."
  type        = string
}

variable "deployment_name" {
  description = "ARM deployment name."
  type        = string
  default     = "nerdio-manager"
}

variable "template_file" {
  description = <<-EOT
    Path to the Nerdio Manager ARM template exported from the Azure Marketplace
    ("Download a template for automation" on the Review + create tab). Nerdio
    doesn't publish a stable template URL, so the kit pins whatever you export.
  EOT
  type        = string
}

variable "parameters" {
  description = "Template parameter values, keyed by parameter name (the exported parameters.json, minus the $schema wrapper)."
  type        = any
  default     = {}
}

variable "tags" {
  description = "Tags on the ARM deployment object."
  type        = map(string)
  default     = {}
}
