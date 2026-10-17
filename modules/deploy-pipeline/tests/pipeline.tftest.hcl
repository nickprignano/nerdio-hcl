# Offline plan tests with mocked providers: terraform init -backend=false && terraform test

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000000"
      object_id = "11111111-1111-1111-1111-111111111111"
    }
  }
}

mock_provider "azuread" {
  mock_data "azuread_service_principal" {
    defaults = {
      object_id = "22222222-2222-2222-2222-222222222222"
      app_role_ids = {
        "Directory.Read.All"                     = "33333333-3333-3333-3333-333333333331"
        "Application.ReadWrite.All"              = "33333333-3333-3333-3333-333333333332"
        "AppRoleAssignment.ReadWrite.All"        = "33333333-3333-3333-3333-333333333333"
        "DelegatedPermissionGrant.ReadWrite.All" = "33333333-3333-3333-3333-333333333334"
        "Group.ReadWrite.All"                    = "33333333-3333-3333-3333-333333333335"
      }
    }
  }
}

mock_provider "github" {
  mock_data "github_user" {
    defaults = {
      id = "1000"
    }
  }
}

variables {
  name            = "nme-sbx"
  location        = "centralus"
  tenant_id       = "00000000-0000-0000-0000-000000000000"
  subscription_id = "00000000-0000-0000-0000-000000000000"
  github = {
    owner      = "contoso"
    repository = "nerdio-hcl"
    reviewers  = ["contoso-admin"]
  }
}

run "gate_and_identities" {
  command = plan

  assert {
    condition     = azurerm_federated_identity_credential.this["plan"].subject == "repo:contoso/nerdio-hcl:environment:sandbox-plan"
    error_message = "The plan identity must trust only the plan environment."
  }
  assert {
    condition     = azurerm_federated_identity_credential.this["apply"].subject == "repo:contoso/nerdio-hcl:environment:sandbox-apply"
    error_message = "The apply identity must trust only the gated apply environment."
  }
  assert {
    condition     = length(github_repository_environment.apply.reviewers) == 1 && !github_repository_environment.apply.can_admins_bypass
    error_message = "Apply must need a reviewer, with no admin bypass."
  }
  assert {
    condition     = length(github_repository_environment.plan.reviewers) == 0
    error_message = "Plan runs shouldn't wait for approval."
  }
  assert {
    condition     = alltrue([for p in github_repository_environment_deployment_policy.this : p.branch_pattern == "main"])
    error_message = "Only main may use either environment."
  }
  assert {
    condition     = azurerm_role_assignment.plan.role_definition_name == "Reader"
    error_message = "The plan identity must stay read-only on the subscription."
  }
  assert {
    condition     = length(azuread_app_role_assignment.graph) == 6 && [for k, v in azuread_app_role_assignment.graph : k if startswith(k, "plan/")] == ["plan/Directory.Read.All"]
    error_message = "The plan identity gets only Directory.Read.All; apply gets the five stage 1 roles."
  }
  assert {
    condition     = !azurerm_storage_account.state.shared_access_key_enabled
    error_message = "State storage must not allow key access."
  }
  assert {
    condition     = length(azurerm_storage_account.state.name) <= 24
    error_message = "Storage account names are at most 24 characters."
  }
  assert {
    condition     = keys(azurerm_storage_container.this) == ["answers", "plans", "tfstate"]
    error_message = "Expected the answers, plans and tfstate containers."
  }
}

run "needs_a_reviewer" {
  command = plan

  variables {
    github = {
      owner      = "contoso"
      repository = "nerdio-hcl"
      reviewers  = []
    }
  }

  expect_failures = [var.github]
}

run "role_admin_is_constrained" {
  command = plan

  assert {
    condition     = azurerm_role_assignment.apply["Role Based Access Control Administrator"].condition_version == "2.0" && strcontains(azurerm_role_assignment.apply["Role Based Access Control Administrator"].condition, "roleAssignments/write")
    error_message = "The apply identity's RBAC administrator role must carry the constrained-delegation condition."
  }
  assert {
    condition     = azurerm_role_assignment.apply["Contributor"].condition == null
    error_message = "Only the role-assignment administrator role needs a condition."
  }
}

run "assignable_roles_never_include_owner" {
  command = plan

  variables {
    apply_assignable_roles = ["Contributor", "Owner"]
  }

  expect_failures = [var.apply_assignable_roles]
}
