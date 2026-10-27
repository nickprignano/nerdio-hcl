output "wufb_ring_policy_id" {
  description = "Intune Windows Update for Business ring ID for AVD session hosts."
  value       = msgraph_resource.wufb_ring.id
}

output "defender_exclusions_policy_id" {
  description = "Intune Settings Catalog policy ID for AVD Defender exclusions."
  value       = msgraph_resource.avd_defender_exclusions.id
}

output "conditional_access_policy_id" {
  description = "Entra Conditional Access policy ID for AVD/W365 when enabled, else null."
  value       = try(msgraph_resource.avd_conditional_access[0].id, null)
}
