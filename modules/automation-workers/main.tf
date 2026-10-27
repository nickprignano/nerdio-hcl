# Dedicated Hybrid Runbook Worker VM Scale Set inside the AVD spoke VNet so Nerdio Manager
# scripted actions and custom runbooks run inside the private network without public endpoints.

resource "random_password" "local_admin" {
  length           = 24
  special          = true
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 2
  override_special = "!@#$%&*-_=+"
}

resource "azurerm_automation_hybrid_runbook_worker_group" "this" {
  name                    = var.worker_group_name
  resource_group_name     = var.automation_resource_group_name
  automation_account_name = var.automation_account_name
}

resource "azurerm_windows_virtual_machine_scale_set" "this" {
  name                 = "vmss-${var.prefix}-hrw"
  location             = var.location
  resource_group_name  = var.resource_group_name
  sku                  = var.vm_size
  instances            = var.instances
  admin_username       = "hrwadmin"
  admin_password       = random_password.local_admin.result
  computer_name_prefix = substr(replace("hrw${var.prefix}", "-", ""), 0, 9)
  upgrade_mode         = "Automatic"
  secure_boot_enabled  = true
  vtpm_enabled         = true
  overprovision        = false
  tags                 = var.tags

  identity {
    type = "SystemAssigned"
  }

  source_image_reference {
    publisher = "MicrosoftWindowsServer"
    offer     = "WindowsServer"
    sku       = "2022-datacenter-g2"
    version   = "latest"
  }

  os_disk {
    caching              = "ReadOnly"
    storage_account_type = "StandardSSD_LRS"

    dynamic "diff_disk_settings" {
      for_each = var.ephemeral_os_disk ? [1] : []
      content {
        option    = "Local"
        placement = "CacheDisk"
      }
    }
  }

  network_interface {
    name                          = "nic-hrw"
    primary                       = true
    enable_accelerated_networking = true

    ip_configuration {
      name      = "ipconfig1"
      primary   = true
      subnet_id = var.subnet_id
    }
  }

  extension {
    name                       = "HybridWorkerExtension"
    publisher                  = "Microsoft.Azure.Automation.HybridWorker"
    type                       = "HybridWorkerForWindows"
    type_handler_version       = "1.1"
    auto_upgrade_minor_version = true
    settings = jsonencode({
      AutomationAccountURL = "${var.automation_account_id}/hybridRunbookWorkerGroups/${azurerm_automation_hybrid_runbook_worker_group.this.name}"
    })
  }
}

resource "azurerm_role_assignment" "worker_automation" {
  scope                = var.automation_account_id
  role_definition_name = "Automation Operator"
  principal_id         = azurerm_windows_virtual_machine_scale_set.this.identity[0].principal_id
}
