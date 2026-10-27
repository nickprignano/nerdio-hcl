# High-IOPS Azure NetApp Files (ANF) SMB volume for FSLogix profile containers.

resource "azurerm_subnet" "anf" {
  name                 = "snet-anf-volumes"
  resource_group_name  = var.vnet_resource_group_name
  virtual_network_name = var.vnet_name
  address_prefixes     = [var.subnet_cidr]

  delegation {
    name = "netapp"
    service_delegation {
      name = "Microsoft.Netapp/volumes"
      actions = [
        "Microsoft.Network/networkinterfaces/*",
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

resource "azurerm_netapp_account" "this" {
  name                = "anf-${var.prefix}-${var.location}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_netapp_pool" "this" {
  name                = "pool-${var.prefix}"
  account_name        = azurerm_netapp_account.this.name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_level       = var.service_level
  size_in_tb          = var.pool_size_in_tb
  tags                = var.tags
}

resource "azurerm_netapp_volume" "profiles" {
  name                = "vol-${var.prefix}-profiles"
  location            = var.location
  resource_group_name = var.resource_group_name
  account_name        = azurerm_netapp_account.this.name
  pool_name           = azurerm_netapp_pool.this.name
  volume_path         = var.volume_path
  service_level       = var.service_level
  subnet_id           = azurerm_subnet.anf.id
  protocols           = ["CIFS"]
  storage_quota_in_gb = var.volume_quota_in_gb
  tags                = var.tags
}
