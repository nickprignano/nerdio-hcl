output "vmss_id" {
  description = "Hybrid Runbook Worker VM Scale Set resource ID."
  value       = azurerm_windows_virtual_machine_scale_set.this.id
}

output "worker_group_name" {
  description = "Hybrid Runbook Worker Group name in the Automation Account."
  value       = azurerm_automation_hybrid_runbook_worker_group.this.name
}

output "principal_id" {
  description = "System-assigned managed identity principal ID of the Hybrid Runbook Worker VMSS."
  value       = azurerm_windows_virtual_machine_scale_set.this.identity[0].principal_id
}
