mock_provider "azurerm" {}

variables {
  prefix                             = "contoso-nme"
  subscription_id                    = "00000000-0000-0000-0000-000000000000"
  nerdio_service_principal_object_id = "11111111-1111-1111-1111-111111111111"
  managed_resource_group_ids = {
    nerdio            = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-contoso-nerdio"
    eastus2-hostpools = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-contoso-eastus2-hostpools"
    eastus2-network   = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-contoso-eastus2-network"
  }
}

run "creates_least_privilege_custom_role_and_assignments" {
  command = plan

  assert {
    condition     = contains(azurerm_role_definition.nerdio_operator.permissions[0].not_actions, "Microsoft.Authorization/*/Write")
    error_message = "Custom role must explicitly block Microsoft.Authorization/*/Write."
  }

  assert {
    condition     = length(azurerm_role_assignment.managed_rgs) == 3
    error_message = "Custom role should be assigned to all 3 managed resource groups."
  }
}
