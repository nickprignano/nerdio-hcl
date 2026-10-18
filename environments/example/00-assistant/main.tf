data "azuread_group" "admins" {
  display_name     = var.admin_group
  security_enabled = true
}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

module "assistant" {
  source = "../../../modules/assistant"

  name                  = var.name
  location              = var.location
  resource_group_name   = azurerm_resource_group.this.name
  tenant_id             = var.tenant_id
  tags                  = var.tags
  image                 = var.image
  admin_group_object_id = data.azuread_group.admins.object_id
  model_provider        = var.model_provider
  foundry               = var.model_provider == "foundry" ? var.foundry : null
  claude_api            = var.claude_api
  kit_repo_url          = var.kit_repo_url
  pipeline              = var.pipeline
}
