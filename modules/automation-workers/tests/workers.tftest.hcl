mock_provider "azurerm" {}
mock_provider "random" {}

variables {
  prefix                         = "contoso-nme"
  location                       = "eastus2"
  resource_group_name            = "rg-contoso-nerdio"
  subnet_id                      = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-net/providers/Microsoft.Network/virtualNetworks/vnet-avd/subnets/snet-session-hosts"
  automation_account_id          = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-contoso-nerdio/providers/Microsoft.Automation/automationAccounts/nmw-app-scripted-actions-01"
  automation_resource_group_name = "rg-contoso-nerdio"
  automation_account_name        = "nmw-app-scripted-actions-01"
  instances                      = 2
}

run "creates_hybrid_worker_vmss_and_group" {
  command = plan

  assert {
    condition     = azurerm_automation_hybrid_runbook_worker_group.this.name == "nerdio-hybrid-workers"
    error_message = "Should create the Hybrid Runbook Worker Group."
  }

  assert {
    condition     = azurerm_windows_virtual_machine_scale_set.this.instances == 2 && azurerm_windows_virtual_machine_scale_set.this.secure_boot_enabled && azurerm_windows_virtual_machine_scale_set.this.vtpm_enabled
    error_message = "Hybrid Runbook Worker VMSS should use TrustedLaunch and 2 instances."
  }
}
