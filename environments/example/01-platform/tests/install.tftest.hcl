# Plan-only test with mocked providers: both install paths and multi-region spokes wire up without a tenant.

mock_provider "azurerm" {
  mock_data "azurerm_subscription" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000"
      display_name = "Example subscription"
    }
  }
  mock_data "azurerm_client_config" {
    defaults = {
      subscription_id = "00000000-0000-0000-0000-000000000000"
      tenant_id       = "11111111-1111-1111-1111-111111111111"
      object_id       = "22222222-2222-2222-2222-222222222222"
    }
  }
}

mock_provider "azuread" {
  mock_data "azuread_client_config" {
    defaults = {
      object_id = "22222222-2222-2222-2222-222222222222"
    }
  }
  mock_data "azuread_application_published_app_ids" {
    defaults = {
      result = {
        MicrosoftGraph         = "00000003-0000-0000-c000-000000000000"
        AzureServiceManagement = "797f4846-ba00-4fd7-ba43-dac1f8f63013"
      }
    }
  }
  # Every Graph scope and role the kit looks up, on whichever service principal is read.
  mock_data "azuread_service_principal" {
    defaults = {
      object_id = "66666666-6666-6666-6666-666666666666"
      oauth2_permission_scope_ids = {
        "User.Read"                       = "aaaaaaaa-0000-0000-0000-000000000000"
        "User.ReadBasic.All"              = "aaaaaaaa-0000-0000-0000-000000000001"
        "User.Read.All"                   = "aaaaaaaa-0000-0000-0000-000000000002"
        "Group.Read.All"                  = "aaaaaaaa-0000-0000-0000-000000000003"
        "GroupMember.Read.All"            = "aaaaaaaa-0000-0000-0000-000000000004"
        "Application.Read.All"            = "aaaaaaaa-0000-0000-0000-000000000005"
        "Application.ReadWrite.All"       = "aaaaaaaa-0000-0000-0000-000000000006"
        "Organization.Read.All"           = "aaaaaaaa-0000-0000-0000-000000000007"
        "AppRoleAssignment.ReadWrite.All" = "aaaaaaaa-0000-0000-0000-000000000008"
        "Directory.Read.All"              = "aaaaaaaa-0000-0000-0000-000000000009"
        "offline_access"                  = "aaaaaaaa-0000-0000-0000-000000000010"
        "openid"                          = "aaaaaaaa-0000-0000-0000-000000000011"
        "profile"                         = "aaaaaaaa-0000-0000-0000-000000000012"
        "Mail.Send"                       = "aaaaaaaa-0000-0000-0000-000000000013"
        "user_impersonation"              = "aaaaaaaa-0000-0000-0000-000000000014"
      }
      app_role_ids = {
        "Group.Read.All"                = "bbbbbbbb-0000-0000-0000-000000000000"
        "GroupMember.Read.All"          = "bbbbbbbb-0000-0000-0000-000000000001"
        "Organization.Read.All"         = "bbbbbbbb-0000-0000-0000-000000000002"
        "User.Read.All"                 = "bbbbbbbb-0000-0000-0000-000000000003"
        "Application.Read.All"          = "bbbbbbbb-0000-0000-0000-000000000004"
        "Application.ReadWrite.OwnedBy" = "bbbbbbbb-0000-0000-0000-000000000005"
      }
    }
  }
}

mock_provider "azapi" {}
mock_provider "time" {}
mock_provider "random" {}
mock_provider "tls" {}
mock_provider "msgraph" {}

mock_provider "http" {
  mock_data "http" {
    defaults = {
      status_code = 200
    }
  }
}

variables {
  tenant_id              = "11111111-1111-1111-1111-111111111111"
  subscription_id        = "00000000-0000-0000-0000-000000000000"
  prefix                 = "example-nme"
  control_plane_location = "eastus2"
  resource_groups = {
    nerdio     = "rg-example-nerdio"
    monitoring = "rg-example-monitoring"
  }
  regions = {
    eastus2 = {
      resource_groups = {
        network   = "rg-example-network"
        hostpools = "rg-example-hostpools"
        storage   = "rg-example-storage"
      }
      network = {
        address_space = ["10.50.0.0/20"]
        subnets = {
          session_hosts     = "10.50.0.0/22"
          private_endpoints = "10.50.4.0/27"
          app_integration   = "10.50.4.32/27"
        }
      }
    }
  }
}

run "terraform_install" {
  command = plan

  assert {
    condition     = length(module.nerdio_core) == 1 && length(module.nerdio_manager) == 0
    error_message = "The default install should be the Terraform one."
  }

  assert {
    condition     = startswith(output.nerdio_url, "https://nmw-app-")
    error_message = "nerdio_url should point at the Terraform-built web app."
  }
}

run "multi_region_spokes_link_to_platform_dns" {
  command = plan

  variables {
    regions = {
      eastus2 = {
        resource_groups = {
          network   = "rg-example-eastus2-network"
          hostpools = "rg-example-eastus2-hostpools"
          storage   = "rg-example-eastus2-storage"
        }
        network = {
          address_space = ["10.50.0.0/20"]
          subnets = {
            session_hosts     = "10.50.0.0/22"
            private_endpoints = "10.50.4.0/27"
            app_integration   = "10.50.4.32/27"
          }
        }
      }
      westeurope = {
        resource_groups = {
          network   = "rg-example-westeurope-network"
          hostpools = "rg-example-westeurope-hostpools"
          storage   = "rg-example-westeurope-storage"
        }
        network = {
          address_space = ["10.50.16.0/20"]
          subnets = {
            session_hosts     = "10.50.16.0/22"
            private_endpoints = "10.50.20.0/27"
            app_integration   = "10.50.20.32/27"
          }
        }
      }
    }
  }

  assert {
    condition     = length(module.network) == 2 && length(azurerm_private_dns_zone_virtual_network_link.secondary_regions) == 5
    error_message = "Both regions should have spoke VNets, and secondary region should link to the 5 platform Private DNS zones."
  }
}

run "terraform_install_needs_entra_app" {
  command = plan

  variables {
    create_entra_app = false
  }

  expect_failures = [var.nerdio_install]
}

run "marketplace_portal_install_needs_no_template_file" {
  command = plan

  variables {
    nerdio_install   = "marketplace"
    create_entra_app = false
  }

  assert {
    condition     = length(module.nerdio_manager) == 1 && length(module.nerdio_core) == 0
    error_message = "Marketplace install should use modules/nerdio-manager without needing a template file."
  }

  assert {
    condition     = length(module.nerdio_identity) == 0 && length(module.nerdio_secrets) == 0
    error_message = "Without create_entra_app or existing_client_id, identity and secrets hand-off are skipped until Nerdio's install script runs."
  }
}

run "marketplace_existing_rg_and_rest_client_hand_off" {
  command = plan

  variables {
    nerdio_install           = "marketplace"
    create_entra_app         = false
    existing_resource_groups = ["nerdio"]
    entra_app = {
      existing_client_id = "33333333-3333-3333-3333-333333333333"
    }
  }

  assert {
    condition     = length(module.nerdio_identity) == 1 && length(module.nerdio_secrets) == 1
    error_message = "With existing_client_id set, a Marketplace install should still build the REST API client app and Key Vault secret hand-off for stage 2."
  }

  assert {
    condition     = output.nerdio_config_inputs.nme_scope == "api://33333333-3333-3333-3333-333333333333/.default"
    error_message = "nme_scope should use the existing Nerdio Entra app's client ID."
  }
}

# Decision 0015: the REST client secret goes to Key Vault by default, never to an output.
run "secret_hand_off_defaults_to_key_vault" {
  command = plan

  assert {
    condition     = length(module.nerdio_secrets) == 1 && length(module.openbao) == 0
    error_message = "The default hand-off should be the Key Vault one, with no OpenBao."
  }
  assert {
    condition     = output.nme_client_secret == null
    error_message = "The secret should only be an output with nme_secret_store = \"output\"."
  }
}

run "openbao_needs_its_settings" {
  command = plan

  variables {
    nme_secret_store = "openbao"
  }

  expect_failures = [var.nme_secret_store]
}

run "openbao_replaces_the_long_lived_secret" {
  command = plan

  variables {
    nme_secret_store = "openbao"
    openbao = {
      subnet_cidr              = "10.50.4.64/28"
      allowed_source_addresses = ["Internet"]
    }
  }

  assert {
    condition     = length(module.openbao) == 1 && length(module.nerdio_secrets) == 0
    error_message = "The openbao hand-off should build OpenBao and skip the Key Vault hand-off."
  }
  assert {
    condition     = length(azurerm_user_assigned_identity.openbao) == 1 && output.nme_client_secret == null
    error_message = "OpenBao should get its own identity, and no long-lived secret should be output."
  }
}

run "enterprise_opt_in_modules_wire_up" {
  command = plan

  variables {
    avd_insights = {
      alert_email_receivers = ["avd-ops@contoso.com"]
      monthly_budget_amount = 2500
    }
    cmk_encryption = {
      rotation_period = "P1Y"
    }
    nerdio_rbac = {}
    intune_policies = {
      assigned_device_group_ids = ["44444444-4444-4444-4444-444444444444"]
      conditional_access = {
        enabled = true
      }
    }
    windows_365 = {
      join_type = "azureADJoin"
    }
    azure_local = {
      resource_group_id  = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-example-azlocal"
      custom_location_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-example-azlocal/providers/Microsoft.ExtendedLocation/customLocations/cl-01"
      vm_switch_name     = "ConvergedSwitch"
    }
    regions = {
      eastus2 = {
        resource_groups = {
          network   = "rg-example-network"
          hostpools = "rg-example-hostpools"
          storage   = "rg-example-storage"
        }
        network = {
          address_space = ["10.50.0.0/20"]
          subnets = {
            session_hosts     = "10.50.0.0/22"
            private_endpoints = "10.50.4.0/27"
            app_integration   = "10.50.4.32/27"
            vnet_runner       = "10.50.4.96/27"
          }
        }
      }
    }
    vnet_runner = {
      github_repo_url = "https://github.com/contoso/nerdio-hcl"
      github_app = {
        application_id                  = "123456"
        installation_id                 = "789012"
        private_key_key_vault_secret_id = "https://kv-test.vault.azure.net/secrets/gh-app-key"
      }
    }
    enable_resource_locks = true
  }

  assert {
    condition     = length(module.avd_insights) == 1 && length(module.cmk_encryption) == 1 && length(module.nerdio_rbac) == 1 && length(module.intune_policies) == 1 && length(module.windows_365) == 1 && length(module.azure_local) == 1 && length(module.vnet_runner) == 1
    error_message = "All seven opt-in enterprise landing zone modules should instantiate when configured."
  }

  assert {
    condition     = length(azurerm_management_lock.stateful) >= 3
    error_message = "Expected CanNotDelete management locks on Nerdio resource group, secrets Key Vault, and CMK Key Vault."
  }
}
