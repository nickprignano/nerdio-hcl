terraform {
  required_version = ">= 1.9"
  required_providers {
    restapi = {
      source  = "Mastercard/restapi"
      version = "~> 2.0"
    }
  }
}
