locals {
  default_region_key = sort(keys(var.regions))[0]
  has_fslogix_shares = (
    anytrue([for k, r in var.regions : r.fslogix_profile_share_unc != null && r.fslogix_profile_share_unc != ""]) ||
    length(var.fslogix_options.locations) > 0
  )
}

module "nerdio_config" {
  source = "../../../modules/nerdio-config"

  subscription_id              = var.subscription_id
  regions                      = var.regions
  workspaces                   = var.workspaces
  ad_config_friendly_name      = var.ad_config_friendly_name
  gallery_image_definition_ids = var.gallery_image_definition_ids
  auto_scale                   = var.auto_scale
  host_pools                   = var.host_pools
  static_host_pools            = var.static_host_pools
  rdp_profiles                 = var.rdp_profiles
  default_rdp_profile_key      = var.default_rdp_profile_key
  vm_deployment_profiles       = var.vm_deployment_profiles
  scripted_actions             = var.scripted_actions
  scripted_action_groups       = var.scripted_action_groups
  scripted_action_profiles     = var.scripted_action_profiles
  workspace_user_assignments   = var.workspace_user_assignments

  fslogix = !local.has_fslogix_shares ? null : {
    name                     = var.fslogix_options.name
    locations                = var.fslogix_options.locations
    office_share_unc         = var.fslogix_options.office_share_unc
    entra_id_kerberos        = var.fslogix_entra_kerberos
    cloud_cache              = var.fslogix_options.cloud_cache
    page_blobs               = var.fslogix_options.page_blobs
    profile_options          = var.fslogix_options.profile_options
    office_options           = var.fslogix_options.office_options
    exclusion_mode           = var.fslogix_options.exclusion_mode
    excluded_domain_accounts = var.fslogix_options.excluded_domain_accounts
    set_as_default           = var.fslogix_options.set_as_default
    redirections_xml         = var.fslogix_options.redirections_xml
  }
}

locals {
  has_rest_gaps = (
    length(var.rest_gaps.host_pool_assignments) > 0 ||
    length(var.rest_gaps.host_pool_rdp) > 0 ||
    length(var.rest_gaps.uam_app_groups) > 0 ||
    length(var.rest_gaps.azure_files_autoscale) > 0 ||
    length(var.rest_gaps.app_attach_packages) > 0 ||
    length(var.rest_gaps.desktop_images) > 0 ||
    length(var.rest_gaps.remote_apps) > 0 ||
    length(var.rest_gaps.uam_repositories) > 0 ||
    length(var.rest_gaps.host_pool_reimage_schedules) > 0
  )
}

module "nerdio_rest_gaps" {
  source = "../../../modules/nerdio-rest-gaps"
  count  = local.has_rest_gaps ? 1 : 0

  subscription_id               = var.subscription_id
  hostpools_resource_group_name = var.regions[local.default_region_key].hostpools_resource_group_name
  host_pool_assignments         = var.rest_gaps.host_pool_assignments
  host_pool_rdp                 = var.rest_gaps.host_pool_rdp
  uam_app_groups                = var.rest_gaps.uam_app_groups
  azure_files_autoscale         = var.rest_gaps.azure_files_autoscale
  app_attach_packages           = var.rest_gaps.app_attach_packages
  desktop_images                = var.rest_gaps.desktop_images
  remote_apps                   = var.rest_gaps.remote_apps
  uam_repositories              = var.rest_gaps.uam_repositories
  host_pool_reimage_schedules   = var.rest_gaps.host_pool_reimage_schedules

  depends_on = [module.nerdio_config]
}
