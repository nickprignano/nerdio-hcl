locals {
  image_version = var.image_version != "" ? var.image_version : formatdate("YYYY.MMDD.hhmm", timestamp())
}

source "azure-arm" "avd" {
  subscription_id    = var.subscription_id
  tenant_id          = var.tenant_id
  use_azure_cli_auth = var.use_azure_cli_auth

  build_resource_group_name = var.build_resource_group
  vm_size                   = var.vm_size

  virtual_network_name                   = try(var.build_subnet.vnet, null)
  virtual_network_subnet_name            = try(var.build_subnet.subnet, null)
  virtual_network_resource_group_name    = try(var.build_subnet.resource_group, null)
  private_virtual_network_with_public_ip = false

  os_type         = "Windows"
  image_publisher = var.source_image.publisher
  image_offer     = var.source_image.offer
  image_sku       = var.source_image.sku
  image_version   = var.source_image.version

  # Match the gallery image definition: Gen2 with Trusted Launch.
  secure_boot_enabled = true
  vtpm_enabled        = true
  security_type       = "TrustedLaunch"

  communicator   = "winrm"
  winrm_use_ssl  = true
  winrm_insecure = true
  winrm_timeout  = "15m"
  winrm_username = "packer"

  shared_image_gallery_destination {
    subscription         = var.subscription_id
    resource_group       = var.gallery.resource_group
    gallery_name         = var.gallery.name
    image_name           = var.gallery.image_definition
    image_version        = local.image_version
    replication_regions  = var.gallery.replica_regions
    storage_account_type = "Standard_ZRS"
  }

  azure_tags = merge(var.tags, { "built-by" = "packer" })
}

build {
  name    = "avd-win11"
  sources = ["source.azure-arm.avd"]

  provisioner "powershell" {
    script = "${path.root}/scripts/01-base.ps1"
    env = {
      TIMEZONE = var.timezone
    }
  }

  provisioner "windows-restart" {
    restart_timeout = "30m"
  }

  provisioner "powershell" {
    script            = "${path.root}/scripts/02-windows-update.ps1"
    elevated_user     = build.User
    elevated_password = build.Password
    valid_exit_codes  = [0, 3010]
    env = {
      RUN_WINDOWS_UPDATE = var.run_windows_update ? "True" : "False"
    }
  }

  provisioner "windows-restart" {
    restart_timeout = "30m"
  }

  provisioner "powershell" {
    script = "${path.root}/scripts/03-vdot.ps1"
    env = {
      RUN_VDOT = var.run_vdot ? "True" : "False"
    }
  }

  provisioner "windows-restart" {
    restart_timeout = "30m"
  }

  provisioner "powershell" {
    script = "${path.root}/scripts/99-sysprep.ps1"
  }
}
