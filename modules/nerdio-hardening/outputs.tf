output "private_endpoint_ids" {
  description = "Private endpoint IDs keyed by target."
  value = merge(
    { for k, pe in azurerm_private_endpoint.sql : "sql-${k}" => pe.id },
    { for k, pe in azurerm_private_endpoint.vault : "kv-${k}" => pe.id },
    { for pe in azurerm_private_endpoint.web : "web" => pe.id },
  )
}
