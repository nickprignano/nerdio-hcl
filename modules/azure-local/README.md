# `modules/azure-local`

Prepares an Azure Local (formerly Azure Stack HCI) cluster's ARM resources so Nerdio Manager for
Enterprise can deploy and auto-scale hybrid on-premises AVD session hosts:

- **`Microsoft.AzureStackHCI/logicalNetworks`**: Creates the Arc-enabled logical network on the
  cluster's Custom Location (`extendedLocation`), binding the Hyper-V virtual switch, VLAN, DNS
  servers, and DHCP/static subnet configuration.
- **RBAC (`Azure Stack HCI VM Contributor`)**: Grants Nerdio Manager's service principal permission
  to provision Arc-enabled session host VMs in the hybrid resource group.
