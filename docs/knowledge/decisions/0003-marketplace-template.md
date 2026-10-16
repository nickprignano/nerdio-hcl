# 0003. Deploy Nerdio Manager from the exported Marketplace template

- **Status:** Superseded by [0011](0011-terraform-native-install.md) as the default. Still supported
  with `nerdio_install = "marketplace"`.
- **Date:** 2026-10-16

## Context

Nerdio supports installing Nerdio Manager from the Azure Marketplace. It does not publish a
stable template URL. Some community projects rebuild the App Service, SQL and Key Vault by hand
instead, using an app package from Nerdio support.

## Decision

Export the Marketplace template from the portal, pin it in `templates/nerdio-manager/`, and
deploy it with `azurerm_resource_group_template_deployment`, ignoring template changes after
install. Private endpoints and VNet integration are added as separate resources in a second apply.

## Consequences

- Stays on Nerdio's supported install path.
- Each new Nerdio version needs a fresh export for new environments; existing ones are updated
  by Nerdio itself.
- The install script and setup wizard remain manual steps.
