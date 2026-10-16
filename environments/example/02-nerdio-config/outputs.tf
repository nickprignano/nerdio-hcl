output "workspace_id" {
  description = "AVD workspace ID."
  value       = module.nerdio_config.workspace_id
}

output "host_pool_ids" {
  description = "Host pool IDs keyed by name."
  value       = module.nerdio_config.host_pool_ids
}
