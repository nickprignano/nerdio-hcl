terraform {
  required_version = ">= 1.9"
  required_providers {
    # Installed from Nerdio's GitHub release (scripts/install-nme-provider.sh); the root module
    # pins the version.
    nme = {
      source = "nerdio/nme"
    }
  }
}
