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
    Optional path to a Nerdio Manager ARM template exported from the Azure Marketplace
    ("Download a template for automation" on the Review + create tab). Leave null (the default)
    when deploying Nerdio Manager directly from the Azure portal Marketplace; this module then
    discovers the Marketplace resources in resource_group_name without deploying an ARM template.
  EOT
  type    = string
  default = null
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
