module "foundation" {
  source          = "../../../modules/foundation"
  prefix          = var.prefix
  location        = var.location
  tags            = var.tags
  resource_groups = var.resource_groups
}

module "network" {
  source              = "../../../modules/network"
  prefix              = var.prefix
  location            = var.location
  resource_group_name = module.foundation.resource_group_names["network"]
  tags                = var.tags
  address_space       = var.network.address_space
  subnets             = var.network.subnets
  dns_servers         = var.network.dns_servers
  hub_vnet_id         = var.network.hub_vnet_id
  use_remote_gateways = var.network.use_remote_gateways
  create_nat_gateway  = var.network.create_nat_gateway
}

module "fslogix" {
  source = "../../../modules/fslogix-storage"
  count  = var.fslogix == null ? 0 : 1

  name                       = var.fslogix.storage_account_name
  location                   = var.location
  resource_group_name        = module.foundation.resource_group_names["storage"]
  tags                       = var.tags
  share_quota_gb             = var.fslogix.share_quota_gb
  identity_source            = var.fslogix.identity_source
  private_endpoint_subnet_id = module.network.subnet_ids["private_endpoints"]
  private_dns_zone_id        = module.network.private_dns_zone_ids["file"]
  user_group_object_ids      = var.fslogix.user_group_object_ids
  admin_group_object_ids     = var.fslogix.admin_group_object_ids
}

module "image_gallery" {
  source = "../../../modules/image-gallery"
  count  = var.image_gallery == null ? 0 : 1

  gallery_name              = var.image_gallery.name
  location                  = var.location
  resource_group_name       = module.foundation.resource_group_names["hostpools"]
  build_resource_group_name = var.image_gallery.build_resource_group_name
  packer_principal_id       = var.image_gallery.packer_principal_id
  tags                      = var.tags
}

module "nerdio_manager" {
  source              = "../../../modules/nerdio-manager"
  resource_group_name = module.foundation.resource_group_names["nerdio"]
  template_file       = var.nerdio_template_file
  parameters          = var.nerdio_template_parameters
  tags                = var.tags
}

module "nerdio_identity" {
  source = "../../../modules/nerdio-identity"
  count  = var.create_entra_app ? 1 : 0

  display_name           = var.entra_app.display_name
  app_service_hostname   = module.nerdio_manager.app_service_hostname
  owner_object_ids       = var.entra_app.owner_object_ids
  wvd_admin_object_ids   = var.entra_app.wvd_admin_object_ids
  grant_admin_consent    = var.entra_app.grant_admin_consent
  enable_mail_send       = var.entra_app.enable_mail_send
  create_rest_api_client = var.entra_app.create_rest_api_client
}

module "nerdio_hardening" {
  source = "../../../modules/nerdio-hardening"
  count  = var.enable_hardening ? 1 : 0

  location                   = var.location
  resource_group_name        = module.foundation.resource_group_names["nerdio"]
  tags                       = var.tags
  app_service_id             = module.nerdio_manager.app_service_id
  app_integration_subnet_id  = module.network.subnet_ids["app_integration"]
  private_endpoint_subnet_id = module.network.subnet_ids["private_endpoints"]
  private_dns_zone_ids       = module.network.private_dns_zone_ids
  sql_server_ids             = module.nerdio_manager.sql_server_ids
  key_vault_ids              = module.nerdio_manager.key_vault_ids
  private_app_service        = var.hardening.private_app_service
  disable_public_access      = var.hardening.disable_public_access
}
