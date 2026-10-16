terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
    # Container Apps sign-in (authConfigs) isn't in azurerm yet, so it goes through Microsoft's azapi.
    azapi = {
      source  = "Azure/azapi"
      version = ">= 2.0"
    }
  }
}
