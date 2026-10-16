module "nerdio_config" {
  source = "../../../modules/nerdio-config"

  subscription_id               = var.subscription_id
  location                      = var.location
  hostpools_resource_group_name = var.hostpools_resource_group_name
  network                       = var.network
  workspace                     = var.workspace
  ad_config_friendly_name       = var.ad_config_friendly_name
  auto_scale                    = var.auto_scale
  host_pools                    = var.host_pools

  fslogix = var.fslogix_profile_share_unc == null ? null : {
    profile_share_unc = var.fslogix_profile_share_unc
    entra_id_kerberos = var.fslogix_entra_kerberos
  }
}
