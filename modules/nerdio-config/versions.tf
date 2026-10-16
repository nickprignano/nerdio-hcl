terraform {
  required_version = ">= 1.9"
  required_providers {
    # Installed from Nerdio's GitHub release via dev_overrides (scripts/install-nme-provider.sh),
    # so no version constraint applies until it is published to the Registry.
    nme = {
      source = "nerdio/nme"
    }
  }
}
