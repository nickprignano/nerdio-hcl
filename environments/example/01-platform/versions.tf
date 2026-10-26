terraform {
  required_version = ">= 1.11"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.11"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Copy backend.tf.example to backend.tf (or use HCP Terraform) before a real deployment.
}

provider "azurerm" {
  features {}
  environment     = var.cloud
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
  # Register only the providers Nerdio Manager and the kit need. The provider does this when it
  # starts and skips any already registered, so subscriptions that already have them (most do)
  # work too. A resource per provider failed there with "already exists".
  resource_provider_registrations = "none"
  resource_providers_to_register = [
    "Microsoft.Automation",
    "Microsoft.Compute",
    "Microsoft.DesktopVirtualization",
    "Microsoft.Insights",
    "Microsoft.KeyVault",
    "Microsoft.Network",
    "Microsoft.OperationalInsights",
    "Microsoft.RecoveryServices",
    "Microsoft.Sql",
    "Microsoft.Storage",
    "Microsoft.Web",
  ]
}

provider "azuread" {
  environment = var.cloud
  tenant_id   = var.tenant_id
}

provider "azapi" {
  environment     = var.cloud
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}
