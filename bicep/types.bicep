// Shared types. Each one mirrors a Terraform variable in environments/example/01-platform, so the
// same answers file (setup.auto.tfvars.json, rendered by ./nerdio init from schema/parameters.json)
// feeds both engines. Keep these in step with variables.tf.

@export()
@description('Spoke resource group names for one region (Terraform: regions.*.resource_groups).')
type regionResourceGroupsType = {
  network: string
  hostpools: string
  storage: string
}

@export()
@description('Spoke subnets for one region (Terraform: regions.*.network.subnets).')
type subnetsType = {
  session_hosts: string
  private_endpoints: string
  app_integration: string
  vnet_runner: string?
}

@export()
@description('Spoke network for one region (Terraform: regions.*.network).')
type networkType = {
  address_space: string[]
  subnets: subnetsType
  dns_servers: string[]?
  connectivity_mode: ('standalone' | 'hub_peering' | 'vwan')?
  hub_vnet_id: string?
  use_remote_gateways: bool?
  virtual_hub_id: string?
  vwan_internet_security_enabled: bool?
  firewall_next_hop_ip: string?
  bypass_avd_control_plane_on_internet: bool?
  create_nat_gateway: bool?
}

@export()
@description('AD DS settings for Azure Files identity-based access (Terraform: regions.*.fslogix.active_directory).')
type activeDirectoryType = {
  domain_name: string
  domain_guid: string
  domain_sid: string?
  forest_name: string?
  netbios_domain_name: string?
  storage_sid: string?
}

@export()
@description('FSLogix profile storage for one region (Terraform: regions.*.fslogix).')
type fslogixType = {
  storage_account_name: string
  share_quota_gb: int?
  app_attach_share_quota_gb: int?
  identity_source: ('AADKERB' | 'AADDS' | 'AD')?
  user_group_object_ids: string[]?
  admin_group_object_ids: string[]?
  active_directory: activeDirectoryType?
}

@export()
@description('One AVD workload region (Terraform: regions.*). Azure NetApp Files (anf) is not ported yet.')
type regionType = {
  location: string?
  subscription_id: string?
  resource_groups: regionResourceGroupsType
  existing_resource_groups: string[]?
  network: networkType
  fslogix: fslogixType?
  anf: object?
}

@export()
@description('Azure Compute Gallery for Packer images (Terraform: image_gallery).')
type imageGalleryType = {
  name: string
  build_resource_group_name: string
  packer_principal_id: string?
}
