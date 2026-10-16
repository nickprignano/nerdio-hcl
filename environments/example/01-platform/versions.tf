terraform {
  required_version = ">= 1.9"

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
  }

  # Copy backend.tf.example to backend.tf (or use HCP Terraform) before a real deployment.
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
  # The kit registers the resource providers it needs explicitly.
  resource_provider_registrations = "none"
}

provider "azuread" {
  tenant_id = var.tenant_id
}
