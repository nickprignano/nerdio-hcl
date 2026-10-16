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
    azapi = {
      source  = "Azure/azapi"
      version = ">= 2.0"
    }
    http = {
      source  = "hashicorp/http"
      version = ">= 3.4"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.11"
    }
  }
}
