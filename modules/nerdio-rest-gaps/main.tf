# Bridges Nerdio Manager REST API v1 endpoints not yet covered by the official nerdio/nme provider.
# Each resource here should be migrated to nerdio/nme once upstream adds a native resource.

resource "restapi_object" "host_pool_assignment" {
  for_each = var.host_pool_assignments

  path         = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/assign"
  create_path  = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/assign"
  read_path    = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}"
  update_path  = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/assign"
  destroy_path = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/unassign"

  create_method  = "POST"
  update_method  = "POST"
  destroy_method = "POST"
  object_id      = each.key

  data = jsonencode({
    users     = each.value.users
    groups    = each.value.groups
    appGroups = each.value.app_groups
  })
}

resource "restapi_object" "host_pool_rdp" {
  for_each = var.host_pool_rdp

  path         = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/rdp"
  create_path  = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/rdp"
  read_path    = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/rdp"
  update_path  = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/rdp"
  destroy_path = "/api/v1/arm/hostpool/${var.subscription_id}/${coalesce(each.value.resource_group, var.hostpools_resource_group_name)}/${each.key}/rdp"

  create_method  = "PATCH"
  update_method  = "PATCH"
  destroy_method = "PATCH"
  object_id      = each.key

  data = jsonencode({
    configurationName = each.value.configuration_name
    rdpProperties     = each.value.rdp_properties
    shortPath = each.value.short_path == null ? null : {
      managedPrivateUdp = each.value.short_path.managed_private_udp
      directUdp         = each.value.short_path.direct_udp
      publicUdp         = each.value.short_path.public_udp
      relayUdp          = each.value.short_path.relay_udp
    }
  })
}

resource "restapi_object" "uam_app_group" {
  for_each = var.uam_app_groups

  path         = "/api/v1/app-management/app-group"
  create_path  = "/api/v1/app-management/app-group"
  read_path    = "/api/v1/app-management/app-group"
  update_path  = "/api/v1/app-management/app-group/{id}"
  destroy_path = "/api/v1/app-management/app-group/{id}"

  create_method = "POST"
  update_method = "PATCH"
  id_attribute  = "payload/id"

  data = jsonencode({
    name = each.value.name
    items = [
      for item in each.value.items : {
        repoId        = item.repo_id
        externalId    = item.external_id
        version       = item.version
        cachedName    = item.cached_name
        reboot        = item.reboot
        onUpgradeFail = item.on_upgrade_fail
      }
    ]
  })
}

resource "restapi_object" "azure_files_link" {
  for_each = { for k, v in var.azure_files_autoscale : k => v if v.link_share }

  path         = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/link"
  create_path  = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/link"
  read_path    = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/auto-scale"
  update_path  = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/link"
  destroy_path = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/link"

  create_method  = "POST"
  update_method  = "POST"
  destroy_method = "DELETE"
  object_id      = each.key
  data           = "{}"
}

resource "restapi_object" "azure_files_autoscale" {
  for_each = var.azure_files_autoscale

  path         = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/auto-scale"
  create_path  = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/auto-scale"
  read_path    = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/auto-scale"
  update_path  = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/auto-scale"
  destroy_path = "/api/v1/storage/azure-files/${var.subscription_id}/${each.value.resource_group}/${each.value.account_name}/${each.value.share_name}/auto-scale"

  create_method  = "PUT"
  update_method  = "PUT"
  destroy_method = "PATCH"
  object_id      = each.key

  data = jsonencode({
    isEnabled = each.value.is_enabled
    unit      = each.value.unit
    basic = {
      minQuotaBuffer  = each.value.min_quota_buffer
      maxQuotaBuffer  = each.value.max_quota_buffer
      maxQuotaLimitGb = each.value.max_quota_limit_gb
    }
    scaling = {
      trigger              = each.value.scaling.trigger
      scaleOutBy           = each.value.scaling.scale_out_by
      scaleOutHighLatency  = each.value.scaling.scale_out_high_lat
      scaleOutInterval     = each.value.scaling.scale_out_interval
      scaleInBy            = each.value.scaling.scale_in_by
      scaleInLowLatency    = each.value.scaling.scale_in_low_lat
      scaleInInterval      = each.value.scaling.scale_in_interval
      transactionThreshold = each.value.scaling.transaction_threshold
    }
    preStage = {
      isEnabled   = false
      workDays    = [1, 2, 3, 4, 5]
      timezoneId  = "Central Standard Time"
      quotaBuffer = 50
    }
  })

  depends_on = [restapi_object.azure_files_link]
}

resource "restapi_object" "app_attach_package" {
  for_each = var.app_attach_packages

  path          = "/api/v1/msix-app-attach/package"
  create_path   = "/api/v1/msix-app-attach/package"
  read_path     = "/api/v1/msix-app-attach/package/{id}"
  update_path   = "/api/v1/msix-app-attach/package/{id}"
  destroy_path  = "/api/v1/msix-app-attach/package/{id}"
  create_method = "POST"
  update_method = "PATCH"
  id_attribute  = "payload/id"

  data = jsonencode({
    name          = each.value.name
    imagePath     = each.value.image_path
    packageName   = each.value.package_name
    version       = each.value.version
    certificateId = each.value.certificate_id
    hostPools     = each.value.host_pool_names
  })
}

resource "restapi_object" "desktop_image" {
  for_each = var.desktop_images

  path          = "/api/v1/desktop-image"
  create_path   = "/api/v1/desktop-image"
  read_path     = "/api/v1/desktop-image/{id}"
  update_path   = "/api/v1/desktop-image/{id}"
  destroy_path  = "/api/v1/desktop-image/{id}"
  create_method = "POST"
  update_method = "PUT"
  id_attribute  = "payload/id"

  data = jsonencode({
    name                = each.value.name
    subscriptionId      = var.subscription_id
    resourceGroup       = each.value.resource_group
    sourceImage         = each.value.source_image
    vmSize              = each.value.vm_size
    storageType         = each.value.storage_type
    galleryResourceId   = each.value.gallery_resource_id
    replicaRegions      = each.value.replica_regions
    scriptedActionIds   = each.value.scripted_action_ids
    scheduleCron        = each.value.schedule_cron
    stagedHostPoolNames = each.value.staged_host_pool_keys
  })
}
