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

module "nerdio_core" {
  source = "../../../modules/nerdio-core"
  count  = var.nerdio_install == "terraform" ? 1 : 0

  resource_group_name  = module.foundation.resource_group_names["nerdio"]
  location             = var.location
  tags                 = var.tags
  name_suffix          = var.nerdio_core.name_suffix
  app_service_plan_sku = var.nerdio_core.app_service_plan_sku
  database_sku         = var.nerdio_core.database_sku
  package_version      = var.nerdio_core.package_version
  grant_admin_consent  = var.entra_app.grant_admin_consent

  entra_app = {
    application_id              = module.nerdio_identity[0].application_id
    client_id                   = module.nerdio_identity[0].client_id
    service_principal_object_id = module.nerdio_identity[0].service_principal_object_id
  }
  managed_resource_group_ids = {
    for k, id in module.foundation.resource_group_ids : k => id if contains(["hostpools", "network", "storage"], k)
  }

  public_network_access_enabled         = !(var.enable_hardening && var.hardening.disable_public_access)
  web_app_public_network_access_enabled = !(var.enable_hardening && var.hardening.disable_public_access && var.hardening.private_app_service)
}

module "nerdio_manager" {
  source = "../../../modules/nerdio-manager"
  count  = var.nerdio_install == "marketplace" ? 1 : 0

  resource_group_name = module.foundation.resource_group_names["nerdio"]
  template_file       = var.nerdio_template_file
  parameters          = var.nerdio_template_parameters
  tags                = var.tags
}

# One of the two install modules exists. Separate locals keep the Entra app (which needs only the
# hostname) from depending on the resources that need the Entra app.
locals {
  nerdio_hostname       = var.nerdio_install == "terraform" ? module.nerdio_core[0].app_service_hostname : module.nerdio_manager[0].app_service_hostname
  nerdio_app_service_id = one(concat(module.nerdio_core[*].app_service_id, module.nerdio_manager[*].app_service_id))
  nerdio_sql_server_ids = merge(concat(module.nerdio_core[*].sql_server_ids, module.nerdio_manager[*].sql_server_ids)...)
  nerdio_key_vault_ids  = merge(concat(module.nerdio_core[*].key_vault_ids, module.nerdio_manager[*].key_vault_ids)...)
}

module "nerdio_identity" {
  source = "../../../modules/nerdio-identity"
  count  = var.create_entra_app ? 1 : 0

  display_name           = var.entra_app.display_name
  app_service_hostname   = local.nerdio_hostname
  owner_object_ids       = var.entra_app.owner_object_ids
  wvd_admin_object_ids   = var.entra_app.wvd_admin_object_ids
  grant_admin_consent    = var.entra_app.grant_admin_consent
  enable_mail_send       = var.entra_app.enable_mail_send
  create_rest_api_client = var.entra_app.create_rest_api_client
  # The terraform install signs the app in with Key Vault certificates.
  create_client_secret = var.nerdio_install == "marketplace"
  # With OpenBao, short-lived secrets replace the long-lived one, and OpenBao's identity owns
  # the app so it needs only Application.ReadWrite.OwnedBy.
  create_rest_api_client_secret          = local.nme_secret_store != "openbao"
  rest_api_client_extra_owner_object_ids = azurerm_user_assigned_identity.openbao[*].principal_id
}

# Hand-off of the Nerdio REST API client secret to stage 2 (decision 0015). Names are short and
# stable per subscription and prefix, because Key Vault names are global.
locals {
  compact_prefix   = substr(replace(lower(var.prefix), "/[^a-z0-9]/", ""), 0, 12)
  secret_suffix    = substr(sha1("${var.subscription_id}/${var.prefix}"), 0, 6)
  has_rest_client  = var.create_entra_app && var.entra_app.create_rest_api_client
  nme_secret_store = local.has_rest_client ? var.nme_secret_store : "output"
}

module "nerdio_secrets" {
  source = "../../../modules/nerdio-secrets"
  count  = local.nme_secret_store == "key_vault" ? 1 : 0

  key_vault_name         = coalesce(var.nme_secret.key_vault_name, "kvnme${local.compact_prefix}${local.secret_suffix}")
  location               = var.location
  resource_group_name    = module.foundation.resource_group_names["nerdio"]
  tags                   = var.tags
  secret_value           = module.nerdio_identity[0].rest_api_client_secret
  secret_version         = module.nerdio_identity[0].rest_api_client_secret_version
  secret_expiration_date = module.nerdio_identity[0].rest_api_client_secret_end_date
  reader_object_ids      = var.nme_secret.reader_object_ids
  github_oidc            = var.nme_secret.github_oidc
}

# Created here rather than in the module, because it must own the REST API client app before the
# module configures OpenBao to manage that app.
resource "azurerm_user_assigned_identity" "openbao" {
  count               = local.nme_secret_store == "openbao" ? 1 : 0
  name                = "id-${local.openbao_name}"
  location            = var.location
  resource_group_name = module.foundation.resource_group_names["nerdio"]
  tags                = var.tags
}

locals {
  openbao_name = try(coalesce(var.openbao.name, "${substr(replace(lower(var.prefix), "/[^a-z0-9-]/", ""), 0, 28)}-bao-${local.secret_suffix}"), null)
}

module "openbao" {
  source = "../../../modules/openbao"
  count  = local.nme_secret_store == "openbao" ? 1 : 0

  name                = local.openbao_name
  key_vault_name      = coalesce(var.openbao.key_vault_name, "kvbao${local.compact_prefix}${local.secret_suffix}")
  location            = var.location
  resource_group_name = module.foundation.resource_group_names["nerdio"]
  tags                = var.tags
  subscription_id     = var.subscription_id
  virtual_network = {
    name                = module.network.vnet_name
    resource_group_name = module.foundation.resource_group_names["network"]
  }
  subnet_cidr                       = var.openbao.subnet_cidr
  allowed_source_addresses          = var.openbao.allowed_source_addresses
  rest_client_application_object_id = module.nerdio_identity[0].rest_api_client_object_id
  identity = {
    id           = azurerm_user_assigned_identity.openbao[0].id
    principal_id = azurerm_user_assigned_identity.openbao[0].principal_id
    client_id    = azurerm_user_assigned_identity.openbao[0].client_id
  }
  login_object_ids = var.openbao.login_object_ids
  github_oidc      = var.nme_secret.github_oidc
  credential_ttl   = var.openbao.credential_ttl
  vm_size          = var.openbao.vm_size
}

module "nerdio_hardening" {
  source = "../../../modules/nerdio-hardening"
  count  = var.enable_hardening ? 1 : 0

  location                   = var.location
  resource_group_name        = module.foundation.resource_group_names["nerdio"]
  tags                       = var.tags
  app_service_id             = local.nerdio_app_service_id
  app_integration_subnet_id  = module.network.subnet_ids["app_integration"]
  private_endpoint_subnet_id = module.network.subnet_ids["private_endpoints"]
  private_dns_zone_ids       = module.network.private_dns_zone_ids
  sql_server_ids             = local.nerdio_sql_server_ids
  key_vault_ids              = local.nerdio_key_vault_ids
  private_app_service        = var.hardening.private_app_service
  disable_public_access      = var.hardening.disable_public_access
  # Terraform owns the core resources in the terraform install and sets public access itself.
  lockdown_with_cli = var.nerdio_install == "marketplace"
}
