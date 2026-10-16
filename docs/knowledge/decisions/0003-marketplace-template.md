---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
review: The roadmap proposes deploying Nerdio's pinned Get-Nerdio/NMW mainTemplate.json instead of a portal export.
---

# 0003. Deploy Nerdio Manager from the exported Marketplace template

## Context and Problem Statement

Nerdio supports installing Nerdio Manager from the Azure Marketplace, but it does not publish a
stable template URL. How should Terraform install Nerdio Manager?

## Considered Options

- Export the Marketplace template from the portal and deploy it with Terraform
- Rebuild the App Service, SQL and Key Vault by hand with an app package from Nerdio support, as
  some community projects do
- Deploy Nerdio's `Get-Nerdio/NMW` `templates/mainTemplate.json`, pinned to a commit

## Decision Outcome

Chosen option: "Export the Marketplace template", because it stays on Nerdio's supported install
path. The export is pinned in `templates/nerdio-manager/` and deployed with
`azurerm_resource_group_template_deployment`, ignoring template changes after install. Private
endpoints and VNet integration are added as separate resources in a second apply.

### Consequences

- Good, because it stays on Nerdio's supported install path.
- Bad, because each new Nerdio version needs a fresh export for new environments; existing ones
  are updated by Nerdio itself.
- Bad, because the install script and setup wizard remain manual steps.

## More Information

Under review: the [roadmap](../stack-options.md) proposes the pinned `Get-Nerdio/NMW` template instead.
