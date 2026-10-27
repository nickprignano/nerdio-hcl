# Azure Local (formerly Azure Stack HCI) logical network and RBAC for Nerdio Manager hybrid AVD host pools.

resource "azapi_resource" "logical_network" {
  type      = "Microsoft.AzureStackHCI/logicalNetworks@2024-01-01"
  name      = "lnet-${var.name_prefix}-avd"
  location  = var.location
  parent_id = var.resource_group_id
  tags      = var.tags

  body = {
    extendedLocation = {
      type = "CustomLocation"
      name = var.custom_location_id
    }
    properties = {
      vmSwitchName = var.vm_switch_name
      dhcpOptions = {
        dnsServers = var.dns_servers
      }
      subnets = [
        {
          name = "snet-avd-local"
          properties = {
            ipAllocationMethod = var.address_prefix == null ? "Dynamic" : "Static"
            addressPrefix      = var.address_prefix
            vlan               = var.vlan_id
            routes = var.default_gateway == null ? [] : [
              {
                name = "default"
                properties = {
                  addressPrefix    = "0.0.0.0/0"
                  nextHopIpAddress = var.default_gateway
                }
              }
            ]
          }
        }
      ]
    }
  }
}

resource "azurerm_role_assignment" "nerdio_hci_vm_contributor" {
  scope                = var.resource_group_id
  role_definition_name = "Azure Stack HCI VM Contributor"
  principal_id         = var.nerdio_service_principal_object_id
}

resource "azurerm_role_assignment" "nerdio_arc_machine_admin" {
  scope                = var.resource_group_id
  role_definition_name = "Azure Connected Machine Resource Administrator"
  principal_id         = var.nerdio_service_principal_object_id
}

resource "azapi_resource" "gallery_image" {
  for_each  = var.gallery_images
  type      = "Microsoft.AzureStackHCI/galleryImages@2024-01-01"
  name      = each.key
  location  = var.location
  parent_id = var.resource_group_id
  tags      = var.tags

  body = {
    extendedLocation = {
      type = "CustomLocation"
      name = var.custom_location_id
    }
    properties = {
      containerId                  = each.value.container_id
      osType                       = each.value.os_type
      hyperVGeneration             = each.value.hyper_v_generation
      cloudInitDataSource          = each.value.cloud_init_data_src
      vmImageRepositoryCredentials = null
      imagePath                    = each.value.image_version_id
    }
  }
}
