locals {
  control_plane_rgs = {
    for k, v in var.resource_groups : k => v if contains(["nerdio", "monitoring"], k)
  }
  control_plane_existing_rgs = toset([
    for k in var.existing_resource_groups : k if contains(["nerdio", "monitoring"], k)
  ])
  # The region in var.regions that hosts Nerdio control-plane VNet integration and platform Private DNS zones.
  control_plane_region_key = contains(keys(var.regions), var.control_plane_location) ? var.control_plane_location : sort(keys(var.regions))[0]
  hub_owns_dns             = length(var.existing_private_dns_zone_ids) > 0
  multi_region             = length(var.regions) > 1
}

module "foundation" {
  source                   = "../../../modules/foundation"
  prefix                   = var.prefix
  location                 = var.control_plane_location
  tags                     = var.tags
  resource_groups          = local.control_plane_rgs
  existing_resource_groups = local.control_plane_existing_rgs
}

module "spoke_foundation" {
  source   = "../../../modules/foundation"
  for_each = var.regions

  prefix                   = local.multi_region ? "${var.prefix}-${each.key}" : var.prefix
  location                 = coalesce(each.value.location, each.key)
  tags                     = var.tags
  create_log_analytics     = false
  resource_groups          = each.value.resource_groups
  existing_resource_groups = each.value.existing_resource_groups
}

module "network" {
  source   = "../../../modules/network"
  for_each = var.regions

  prefix                               = local.multi_region ? "${var.prefix}-${each.key}" : var.prefix
  location                             = coalesce(each.value.location, each.key)
  resource_group_name                  = module.spoke_foundation[each.key].resource_group_names["network"]
  tags                                 = var.tags
  address_space                        = each.value.network.address_space
  subnets                              = each.value.network.subnets
  dns_servers                          = each.value.network.dns_servers
  connectivity_mode                    = each.value.network.connectivity_mode
  hub_vnet_id                          = each.value.network.hub_vnet_id
  use_remote_gateways                  = each.value.network.use_remote_gateways
  virtual_hub_id                       = each.value.network.virtual_hub_id
  vwan_internet_security_enabled       = each.value.network.vwan_internet_security_enabled
  firewall_next_hop_ip                 = each.value.network.firewall_next_hop_ip
  bypass_avd_control_plane_on_internet = each.value.network.bypass_avd_control_plane_on_internet
  create_nat_gateway                   = each.value.network.create_nat_gateway
  cloud                                = var.cloud

  create_private_dns_zones        = !local.hub_owns_dns && each.key == local.control_plane_region_key
  extra_private_dns_zones         = toset(concat(tolist(var.extra_private_dns_zones), (var.enable_hardening || var.automation_workers != null) ? ["automation"] : []))
  existing_private_dns_zone_ids   = local.hub_owns_dns ? var.existing_private_dns_zone_ids : {}
  link_existing_private_dns_zones = local.hub_owns_dns
}

locals {
  platform_private_dns_zone_ids = module.network[local.control_plane_region_key].private_dns_zone_ids
  # Link additional regional VNets to the platform Private DNS zones created in control_plane_region_key.
  secondary_region_dns_links = !local.hub_owns_dns ? merge([
    for reg_key, reg in var.regions : {
      for zone_key, zone_id in local.platform_private_dns_zone_ids : "${reg_key}:${zone_key}" => {
        zone_id   = zone_id
        vnet_id   = module.network[reg_key].vnet_id
        vnet_name = module.network[reg_key].vnet_name
      }
    } if reg_key != local.control_plane_region_key
  ]...) : {}
}

resource "azurerm_private_dns_zone_virtual_network_link" "secondary_regions" {
  for_each            = local.secondary_region_dns_links
  name                = "link-${each.value.vnet_name}"
  private_dns_zone_id = each.value.zone_id
  virtual_network_id  = each.value.vnet_id
  tags                = var.tags
}

module "fslogix" {
  source   = "../../../modules/fslogix-storage"
  for_each = { for k, r in var.regions : k => r if r.fslogix != null }

  name                       = each.value.fslogix.storage_account_name
  location                   = coalesce(each.value.location, each.key)
  resource_group_name        = module.spoke_foundation[each.key].resource_group_names["storage"]
  tags                       = var.tags
  share_quota_gb             = each.value.fslogix.share_quota_gb
  app_attach_share_quota_gb  = each.value.fslogix.app_attach_share_quota_gb
  identity_source            = each.value.fslogix.identity_source
  active_directory           = each.value.fslogix.active_directory
  private_endpoint_subnet_id = module.network[each.key].subnet_ids["private_endpoints"]
  private_dns_zone_id        = local.platform_private_dns_zone_ids["file"]
  user_group_object_ids      = each.value.fslogix.user_group_object_ids
  admin_group_object_ids     = each.value.fslogix.admin_group_object_ids
  cloud                      = var.cloud
}

module "anf" {
  source   = "../../../modules/anf-storage"
  for_each = { for k, r in var.regions : k => r if r.anf != null }

  prefix                   = var.prefix
  location                 = coalesce(each.value.location, each.key)
  resource_group_name      = module.spoke_foundation[each.key].resource_group_names["storage"]
  vnet_name                = module.network[each.key].vnet_name
  vnet_resource_group_name = module.spoke_foundation[each.key].resource_group_names["network"]
  subnet_cidr              = each.value.anf.subnet_cidr
  service_level            = each.value.anf.service_level
  pool_size_in_tb          = each.value.anf.pool_size_in_tb
  volume_quota_in_gb       = each.value.anf.volume_quota_in_gb
  volume_path              = each.value.anf.volume_path
  tags                     = var.tags
}

module "image_gallery" {
  source = "../../../modules/image-gallery"
  count  = var.image_gallery == null ? 0 : 1

  gallery_name              = var.image_gallery.name
  location                  = var.control_plane_location
  resource_group_name       = module.spoke_foundation[local.control_plane_region_key].resource_group_names["hostpools"]
  build_resource_group_name = var.image_gallery.build_resource_group_name
  packer_principal_id       = var.image_gallery.packer_principal_id
  tags                      = var.tags
}

locals {
  all_managed_spoke_rg_ids = merge([
    for reg_key, sf in module.spoke_foundation : {
      for role, id in sf.resource_group_ids : "${reg_key}-${role}" => id if contains(["hostpools", "network", "storage"], role)
    }
  ]...)
}

module "nerdio_core" {
  source = "../../../modules/nerdio-core"
  count  = var.nerdio_install == "terraform" ? 1 : 0

  resource_group_name      = module.foundation.resource_group_names["nerdio"]
  location                 = var.control_plane_location
  dr_location              = var.control_plane_dr_location
  tags                     = var.tags
  name_suffix              = var.nerdio_core.name_suffix
  app_service_plan_sku     = var.nerdio_core.app_service_plan_sku
  database_sku             = var.nerdio_core.database_sku
  package_version          = var.nerdio_core.package_version
  purge_protection_enabled = var.nerdio_core.purge_protection_enabled
  enable_staging_slot      = var.nerdio_core.enable_staging_slot
  autoscale                = var.nerdio_core.autoscale
  grant_admin_consent      = var.entra_app.grant_admin_consent
  deployer_object_id       = var.deployer_object_id
  cloud                    = var.cloud

  entra_app = {
    application_id              = module.nerdio_identity[0].application_id
    client_id                   = module.nerdio_identity[0].client_id
    service_principal_object_id = module.nerdio_identity[0].service_principal_object_id
  }
  managed_resource_group_ids = local.all_managed_spoke_rg_ids
  assign_builtin_rbac        = var.nerdio_rbac == null

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
  nerdio_hostname               = var.nerdio_install == "terraform" ? module.nerdio_core[0].app_service_hostname : module.nerdio_manager[0].app_service_hostname
  nerdio_app_service_id         = one(concat(module.nerdio_core[*].app_service_id, module.nerdio_manager[*].app_service_id))
  nerdio_sql_server_ids         = merge(concat(module.nerdio_core[*].sql_server_ids, module.nerdio_manager[*].sql_server_ids)...)
  nerdio_key_vault_ids          = merge(concat(module.nerdio_core[*].key_vault_ids, module.nerdio_manager[*].key_vault_ids)...)
  nerdio_storage_account_ids    = merge(concat(module.nerdio_core[*].storage_account_ids, module.nerdio_manager[*].storage_account_ids)...)
  nerdio_automation_account_ids = merge(concat(module.nerdio_core[*].automation_account_ids, module.nerdio_manager[*].automation_account_ids)...)
}

module "nerdio_identity" {
  source = "../../../modules/nerdio-identity"
  count  = local.manage_identity ? 1 : 0

  display_name           = var.entra_app.display_name
  create_nerdio_app      = var.create_entra_app
  existing_client_id     = var.entra_app.existing_client_id
  app_service_hostname   = local.nerdio_hostname
  owner_object_ids       = var.entra_app.owner_object_ids
  deployer_object_id     = var.deployer_object_id
  wvd_admin_object_ids   = var.entra_app.wvd_admin_object_ids
  grant_admin_consent    = var.entra_app.grant_admin_consent
  enable_mail_send       = var.entra_app.enable_mail_send
  create_rest_api_client = var.entra_app.create_rest_api_client
  # The terraform install signs the app in with Key Vault certificates.
  create_client_secret = var.nerdio_install == "marketplace" && var.create_entra_app
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
  manage_identity  = var.create_entra_app || var.entra_app.existing_client_id != null
  has_rest_client  = local.manage_identity && var.entra_app.create_rest_api_client
  nme_secret_store = local.has_rest_client ? var.nme_secret_store : "output"
}

module "nerdio_secrets" {
  source = "../../../modules/nerdio-secrets"
  count  = local.nme_secret_store == "key_vault" ? 1 : 0

  key_vault_name         = coalesce(var.nme_secret.key_vault_name, "kvnme${local.compact_prefix}${local.secret_suffix}")
  location               = var.control_plane_location
  resource_group_name    = module.foundation.resource_group_names["nerdio"]
  tags                   = var.tags
  secret_value           = module.nerdio_identity[0].rest_api_client_secret
  secret_version         = module.nerdio_identity[0].rest_api_client_secret_version
  secret_expiration_date = module.nerdio_identity[0].rest_api_client_secret_end_date
  reader_object_ids      = var.nme_secret.reader_object_ids
  github_oidc            = var.nme_secret.github_oidc
  deployer_object_id     = var.deployer_object_id
}

# Created here rather than in the module, because it must own the REST API client app before the
# module configures OpenBao to manage that app.
resource "azurerm_user_assigned_identity" "openbao" {
  count               = local.nme_secret_store == "openbao" ? 1 : 0
  name                = "id-${local.openbao_name}"
  location            = var.control_plane_location
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
  location            = var.control_plane_location
  resource_group_name = module.foundation.resource_group_names["nerdio"]
  tags                = var.tags
  subscription_id     = var.subscription_id
  virtual_network = {
    name                = module.network[local.control_plane_region_key].vnet_name
    resource_group_name = module.spoke_foundation[local.control_plane_region_key].resource_group_names["network"]
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

  location                   = coalesce(var.regions[local.control_plane_region_key].location, local.control_plane_region_key)
  resource_group_name        = module.foundation.resource_group_names["nerdio"]
  tags                       = var.tags
  app_service_id             = local.nerdio_app_service_id
  app_integration_subnet_id  = module.network[local.control_plane_region_key].subnet_ids["app_integration"]
  private_endpoint_subnet_id = module.network[local.control_plane_region_key].subnet_ids["private_endpoints"]
  private_dns_zone_ids       = local.platform_private_dns_zone_ids
  sql_server_ids             = local.nerdio_sql_server_ids
  key_vault_ids              = local.nerdio_key_vault_ids
  storage_account_ids        = local.nerdio_storage_account_ids
  automation_account_ids     = local.nerdio_automation_account_ids
  private_app_service        = var.hardening.private_app_service
  disable_public_access      = var.hardening.disable_public_access
  # Terraform owns the core resources in the terraform install and sets public access itself.
  lockdown_with_cli = var.nerdio_install == "marketplace"
}

locals {
  scripted_actions_automation_key = try([
    for k in sort(keys(local.nerdio_automation_account_ids)) : k if strcontains(k, "scripted-actions")
  ][0], try(sort(keys(local.nerdio_automation_account_ids))[0], null))
}

module "automation_workers" {
  source = "../../../modules/automation-workers"
  count  = var.automation_workers != null ? 1 : 0

  prefix                         = var.prefix
  location                       = coalesce(var.regions[local.control_plane_region_key].location, local.control_plane_region_key)
  resource_group_name            = module.spoke_foundation[local.control_plane_region_key].resource_group_names["hostpools"]
  subnet_id                      = module.network[local.control_plane_region_key].subnet_ids["session_hosts"]
  automation_account_id          = local.nerdio_automation_account_ids[local.scripted_actions_automation_key]
  automation_resource_group_name = module.foundation.resource_group_names["nerdio"]
  automation_account_name        = local.scripted_actions_automation_key
  worker_group_name              = var.automation_workers.worker_group_name
  vm_size                        = var.automation_workers.vm_size
  instances                      = var.automation_workers.instances
  ephemeral_os_disk              = var.automation_workers.ephemeral_os_disk
  tags                           = var.tags
}

module "avd_insights" {
  source = "../../../modules/avd-insights"
  count  = var.avd_insights != null ? 1 : 0

  prefix                     = var.prefix
  location                   = var.control_plane_location
  resource_group_name        = module.foundation.resource_group_names["monitoring"]
  resource_group_id          = module.foundation.resource_group_ids["monitoring"]
  log_analytics_workspace_id = module.foundation.log_analytics_workspace_id
  alert_email_receivers      = var.avd_insights.alert_email_receivers
  monthly_budget_amount      = var.avd_insights.monthly_budget_amount
  budget_start_date          = var.avd_insights.budget_start_date
  tags                       = var.tags
}

module "azure_local" {
  source = "../../../modules/azure-local"
  count  = var.azure_local != null ? 1 : 0

  name_prefix                        = var.prefix
  location                           = coalesce(var.azure_local.location, var.control_plane_location)
  resource_group_id                  = var.azure_local.resource_group_id
  custom_location_id                 = var.azure_local.custom_location_id
  vm_switch_name                     = var.azure_local.vm_switch_name
  vlan_id                            = var.azure_local.vlan_id
  address_prefix                     = var.azure_local.address_prefix
  default_gateway                    = var.azure_local.default_gateway
  dns_servers                        = var.azure_local.dns_servers
  nerdio_service_principal_object_id = module.nerdio_identity[0].service_principal_object_id
  gallery_images                     = var.azure_local.gallery_images
  tags                               = var.tags
}

locals {
  w365_region_key = var.windows_365 != null ? coalesce(var.windows_365.region_key, local.control_plane_region_key) : local.control_plane_region_key
}

module "windows_365" {
  source = "../../../modules/windows-365"
  count  = var.windows_365 != null ? 1 : 0

  name_prefix                   = var.prefix
  subscription_id               = coalesce(var.regions[local.w365_region_key].subscription_id, var.subscription_id)
  resource_group_id             = module.spoke_foundation[local.w365_region_key].resource_group_ids["hostpools"]
  virtual_network_id            = module.network[local.w365_region_key].vnet_id
  subnet_id                     = module.network[local.w365_region_key].subnet_ids["session_hosts"]
  join_type                     = var.windows_365.join_type
  image_id                      = var.windows_365.image_id
  image_type                    = var.windows_365.image_type
  enable_single_sign_on         = var.windows_365.enable_single_sign_on
  local_admin_enabled           = var.windows_365.local_admin_enabled
  restore_point_frequency_hours = var.windows_365.restore_point_frequency_hours
  assigned_group_object_ids     = var.windows_365.assigned_group_object_ids
}

module "intune_policies" {
  source = "../../../modules/intune-policies"
  count  = var.intune_policies != null ? 1 : 0

  name_prefix                  = var.prefix
  fslogix_vhd_locations        = var.intune_policies.fslogix_vhd_locations
  defender_excluded_extensions = var.intune_policies.defender_excluded_extensions
  wufb_feature_deferral_days   = var.intune_policies.wufb_feature_deferral_days
  wufb_quality_deferral_days   = var.intune_policies.wufb_quality_deferral_days
  assigned_device_group_ids    = var.intune_policies.assigned_device_group_ids
  conditional_access           = var.intune_policies.conditional_access
}

module "cmk_encryption" {
  source = "../../../modules/cmk-encryption"
  count  = var.cmk_encryption != null ? 1 : 0

  prefix                 = var.prefix
  control_plane_location = var.control_plane_location
  resource_group_name    = module.foundation.resource_group_names["nerdio"]
  existing_key_vault_id  = var.cmk_encryption.existing_key_vault_id
  key_vault_name         = var.cmk_encryption.key_vault_name
  key_name               = var.cmk_encryption.key_name
  key_size               = var.cmk_encryption.key_size
  rotation_period        = var.cmk_encryption.rotation_period
  regions = {
    for k, r in var.regions : k => {
      location            = coalesce(r.location, k)
      resource_group_name = module.spoke_foundation[k].resource_group_names["hostpools"]
    }
  }
  deployer_object_id = var.deployer_object_id
  tags               = var.tags
}

module "nerdio_rbac" {
  source = "../../../modules/nerdio-rbac"
  count  = var.nerdio_rbac != null && local.manage_identity ? 1 : 0

  prefix                             = var.prefix
  subscription_id                    = var.subscription_id
  nerdio_service_principal_object_id = module.nerdio_identity[0].service_principal_object_id
  managed_resource_group_ids = merge(
    { nerdio = module.foundation.resource_group_ids["nerdio"] },
    local.all_managed_spoke_rg_ids
  )
  extra_actions = var.nerdio_rbac.extra_actions
}

locals {
  default_runner_kv_id = try(
    coalesce(
      var.vnet_runner.key_vault_id,
      try(module.nerdio_secrets[0].key_vault_id, null),
      try(values(local.nerdio_key_vault_ids)[0], null)
    ),
    null
  )
}

module "vnet_runner" {
  source = "../../../modules/vnet-runner"
  count  = var.vnet_runner != null ? 1 : 0

  name_prefix                    = var.prefix
  location                       = coalesce(var.regions[local.control_plane_region_key].location, local.control_plane_region_key)
  resource_group_name            = module.spoke_foundation[local.control_plane_region_key].resource_group_names["network"]
  infrastructure_subnet_id       = module.network[local.control_plane_region_key].subnet_ids["vnet_runner"]
  log_analytics_workspace_id     = module.foundation.log_analytics_workspace_id
  github_repo_url                = var.vnet_runner.github_repo_url
  key_vault_id                   = local.default_runner_kv_id
  github_pat_key_vault_secret_id = var.vnet_runner.github_pat_key_vault_secret_id
  github_app                     = var.vnet_runner.github_app
  runner_image                   = var.vnet_runner.runner_image
  runner_labels                  = var.vnet_runner.runner_labels
  max_executions                 = var.vnet_runner.max_executions
  tags                           = var.tags
}

# ---------------------------------------------------------------------------------------------
# CanNotDelete management locks for stateful production resources

locals {
  locked_resources = !var.enable_resource_locks ? {} : merge(
    { for k, id in local.nerdio_sql_server_ids : "sql-${k}" => id },
    { for k, id in local.nerdio_key_vault_ids : "kv-${k}" => id },
    local.nme_secret_store == "key_vault" ? { "kv-nme-secrets" = module.nerdio_secrets[0].key_vault_id } : {},
    var.cmk_encryption != null ? { "kv-cmk" = module.cmk_encryption[0].key_vault_id } : {},
    { for k, m in module.fslogix : "fslogix-${k}" => m.storage_account_id },
    { for k, m in module.anf : "anf-${k}" => m.volume_id }
  )
}

resource "azurerm_management_lock" "stateful" {
  for_each   = local.locked_resources
  name       = "lock-${var.prefix}-${each.key}"
  scope      = each.value
  lock_level = "CanNotDelete"
  notes      = "Managed by Terraform (enable_resource_locks = true): protects stateful AVD and Nerdio data from accidental deletion."
}
