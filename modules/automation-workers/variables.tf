variable "prefix" {
  description = "Short naming prefix."
  type        = string
}

variable "location" {
  description = "Azure region for the Hybrid Runbook Worker VMSS."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group where the Hybrid Runbook Worker VMSS is created."
  type        = string
}

variable "subnet_id" {
  description = "VNet subnet ID where the Hybrid Runbook Worker VMSS NICs are placed."
  type        = string
}

variable "automation_account_id" {
  description = "Resource ID of the Nerdio Automation Account (typically the scripted-actions Automation Account)."
  type        = string
}

variable "automation_resource_group_name" {
  description = "Resource group name of the Nerdio Automation Account."
  type        = string
}

variable "automation_account_name" {
  description = "Name of the Nerdio Automation Account."
  type        = string
}

variable "worker_group_name" {
  description = "Name of the Hybrid Runbook Worker Group registered in the Automation Account."
  type        = string
  default     = "nerdio-hybrid-workers"
}

variable "vm_size" {
  description = "VM SKU for the Hybrid Runbook Worker VM Scale Set."
  type        = string
  default     = "Standard_D2s_v5"
}

variable "instances" {
  description = "Number of Hybrid Runbook Worker instances in the scale set."
  type        = number
  default     = 2
  validation {
    condition     = var.instances >= 1 && var.instances <= 20
    error_message = "instances must be between 1 and 20."
  }
}

variable "ephemeral_os_disk" {
  description = "Use ephemeral OS disks stored on local cache/temp storage."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to all Hybrid Runbook Worker resources."
  type        = map(string)
  default     = {}
}
