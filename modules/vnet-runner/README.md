# `modules/vnet-runner`

Provisions an ephemeral, scale-to-zero GitHub Actions self-hosted runner inside the AVD virtual
network using an Azure Container Apps Job (`azurerm_container_app_job` with the `github-runner`
KEDA scaler).

## When to use this module

When `enable_hardening = true`, Nerdio Manager's App Service, Key Vault, SQL Server, and storage
accounts disable public network access and use Private Endpoints inside the VNet. GitHub-hosted
runners (`ubuntu-latest`) cannot reach private endpoints directly. Deploying `modules/vnet-runner`
into a subnet of the AVD VNet gives the pipeline private network reachability while scaling to `0`
when no workflow job is queued.
