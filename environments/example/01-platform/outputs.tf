output "nerdio_url" {
  description = "Nerdio Manager console. Open it for the setup wizard (and, for the marketplace install, the install step first). Null before a portal Marketplace deployment exists in the resource group."
  value       = local.nerdio_hostname != null ? "https://${local.nerdio_hostname}" : null
}

output "avd_vnet_names" {
  description = "AVD spoke VNet names keyed by region."
  value       = { for k, n in module.network : k => n.vnet_name }
}

output "resource_group_names" {
  description = "Control-plane resource group names (nerdio, monitoring)."
  value       = module.foundation.resource_group_names
}

output "regional_resource_group_names" {
  description = "Spoke resource group names keyed by region (network, hostpools, storage)."
  value       = { for k, sf in module.spoke_foundation : k => sf.resource_group_names }
}

output "fslogix_share_uncs" {
  description = "FSLogix profile share UNC paths keyed by region."
  value = {
    for k, r in var.regions : k => coalesce(
      try(module.fslogix[k].profile_share_unc, null),
      try(module.anf[k].profile_share_unc, null)
    ) if try(module.fslogix[k].profile_share_unc, null) != null || try(module.anf[k].profile_share_unc, null) != null
  }
}

output "entra_app_client_id" {
  description = "Nerdio Entra app ID (also the App ID for the marketplace install's \"Use existing AD app\" option)."
  value       = try(module.nerdio_identity[0].client_id, null)
}

output "entra_app_service_principal_id" {
  description = "Service Principal ID for Nerdio's \"Use existing AD app\" option."
  value       = try(module.nerdio_identity[0].service_principal_object_id, null)
}

output "entra_app_client_secret" {
  description = "App Secret for Nerdio's \"Use existing AD app\" option. Read with terraform output -raw."
  value       = try(module.nerdio_identity[0].client_secret, null)
  sensitive   = true
}

output "packer_gallery" {
  description = "Values for the Packer gallery variable and Compute Gallery image definition IDs."
  value = try({
    resource_group       = module.spoke_foundation[local.control_plane_region_key].resource_group_names["hostpools"]
    name                 = module.image_gallery[0].gallery_name
    image_definition     = keys(module.image_gallery[0].image_definition_ids)[0]
    image_definition_ids = module.image_gallery[0].image_definition_ids
    build_rg             = module.image_gallery[0].build_resource_group_name
    replica_regions      = sort(keys(var.regions))
  }, null)
}

output "nerdio_config_inputs" {
  description = <<-EOT
    Inputs for 02-nerdio-config, keyed by its variable names. Write them out with
    terraform output -json nerdio_config_inputs > ../02-nerdio-config/platform.auto.tfvars.json
  EOT
  value = {
    nme_base_url           = local.nerdio_hostname != null ? "https://${local.nerdio_hostname}" : null
    nme_tenant_id          = var.tenant_id
    nme_client_id          = try(module.nerdio_identity[0].rest_api_client_id, null)
    nme_scope              = try("api://${module.nerdio_identity[0].client_id}/.default", null)
    subscription_id        = var.subscription_id
    control_plane_location = var.control_plane_location
    regions = {
      for k, r in var.regions : k => {
        location                      = coalesce(r.location, k)
        subscription_id               = coalesce(r.subscription_id, var.subscription_id)
        hostpools_resource_group_name = module.spoke_foundation[k].resource_group_names["hostpools"]
        network = {
          resource_group_name = module.spoke_foundation[k].resource_group_names["network"]
          vnet_name           = module.network[k].vnet_name
          subnet_name         = module.network[k].session_host_subnet_name
        }
        fslogix_profile_share_unc = try(coalesce(
          try(module.fslogix[k].profile_share_unc, null),
          try(module.anf[k].profile_share_unc, null)
        ), null)
        app_attach_share_unc   = try(module.fslogix[k].app_attach_share_unc, null)
        disk_encryption_set_id = try(module.cmk_encryption[0].disk_encryption_set_ids[k], null)
      }
    }
    gallery_image_definition_ids = try(module.image_gallery[0].image_definition_ids, {})
    # How stage 2 gets the REST client secret (decision 0015). None of these are secrets.
    nme_secret_source = local.nme_secret_store
    nme_key_vault = try({
      id          = module.nerdio_secrets[0].key_vault_id
      secret_name = module.nerdio_secrets[0].secret_name
    }, null)
    openbao = try({
      address = module.openbao[0].address
      role    = module.openbao[0].secret_role
      scope   = module.openbao[0].login_scope
    }, null)
  }
}

output "nme_client_secret" {
  description = "Only with nme_secret_store = \"output\": the REST API client secret for 02-nerdio-config. Export as NME_CLIENT_SECRET; never write it to a file."
  value       = local.nme_secret_store == "output" ? try(module.nerdio_identity[0].rest_api_client_secret, null) : null
  sensitive   = true
}

output "openbao_ca_cert" {
  description = "OpenBao's TLS certificate, which stage 2 trusts. Public. Write it to 02-nerdio-config/openbao-ca.pem."
  value       = try(module.openbao[0].ca_cert_pem, null)
}

output "github_oidc_client_id" {
  description = "Client ID for a GitHub Actions job to sign in with OIDC (azure/login), when nme_secret.github_oidc is set. Not a secret."
  value       = try(module.nerdio_secrets[0].github_client_id, null)
}

output "automation_workers" {
  description = "Hybrid Runbook Worker VM Scale Set details when automation_workers is set, else null."
  value = var.automation_workers != null ? {
    vmss_id           = module.automation_workers[0].vmss_id
    worker_group_name = module.automation_workers[0].worker_group_name
  } : null
}

output "avd_insights" {
  description = "AVD Insights Data Collection Rule, Action Group, and Budget IDs when avd_insights is set, else null."
  value = var.avd_insights != null ? {
    data_collection_rule_id = module.avd_insights[0].data_collection_rule_id
    action_group_id         = module.avd_insights[0].action_group_id
    budget_id               = module.avd_insights[0].budget_id
  } : null
}

output "azure_local" {
  description = "Azure Local logical network and gallery image IDs when azure_local is set, else null."
  value = var.azure_local != null ? {
    logical_network_id = module.azure_local[0].logical_network_id
    custom_location_id = module.azure_local[0].custom_location_id
    gallery_image_ids  = module.azure_local[0].gallery_image_ids
  } : null
}

output "windows_365" {
  description = "Windows 365 Cloud PC Azure Network Connection, Provisioning Policy and User Settings IDs when windows_365 is set, else null."
  value = var.windows_365 != null ? {
    azure_network_connection_id = module.windows_365[0].azure_network_connection_id
    provisioning_policy_id      = module.windows_365[0].provisioning_policy_id
    user_settings_id            = module.windows_365[0].user_settings_id
  } : null
}

output "intune_policies" {
  description = "Intune WUfB ring, Defender exclusions, and Conditional Access policy IDs when intune_policies is set, else null."
  value = var.intune_policies != null ? {
    wufb_ring_policy_id           = module.intune_policies[0].wufb_ring_policy_id
    defender_exclusions_policy_id = module.intune_policies[0].defender_exclusions_policy_id
    conditional_access_policy_id  = module.intune_policies[0].conditional_access_policy_id
  } : null
}

output "cmk_encryption" {
  description = "Customer-Managed Key Vault ID, key ID, and per-region Disk Encryption Set IDs when cmk_encryption is set, else null."
  value = var.cmk_encryption != null ? {
    key_vault_id            = module.cmk_encryption[0].key_vault_id
    key_vault_key_id        = module.cmk_encryption[0].key_vault_key_id
    disk_encryption_set_ids = module.cmk_encryption[0].disk_encryption_set_ids
  } : null
}

output "nerdio_rbac" {
  description = "Custom least-privilege Nerdio role definition ID when nerdio_rbac is set, else null."
  value = var.nerdio_rbac != null && local.manage_identity ? {
    role_definition_id  = module.nerdio_rbac[0].role_definition_id
    role_assignment_ids = module.nerdio_rbac[0].role_assignment_ids
  } : null
}

output "vnet_runner" {
  description = "Ephemeral VNet GitHub Actions runner Container Apps Environment, Job, and Identity IDs when vnet_runner is set, else null."
  value = var.vnet_runner != null ? {
    container_app_environment_id = module.vnet_runner[0].container_app_environment_id
    runner_job_id                = module.vnet_runner[0].runner_job_id
    runner_identity_principal_id = module.vnet_runner[0].runner_identity_principal_id
  } : null
}
