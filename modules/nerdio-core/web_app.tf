resource "azurerm_service_plan" "this" {
  name                = local.names.plan
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Windows"
  sku_name            = var.app_service_plan_sku
  tags                = local.paas_tags
}

locals {
  # The settings Nerdio's template and install script write. Names and values follow
  # MB-External/NME-Terraform, which runs the same install end to end in Terraform. The SQL server
  # ID is built from its name because the server depends on the web app (its admin group holds
  # the app's identity).
  app_settings = {
    "AzureAd:Instance"                                            = local.cloud_endpoints.login_endpoint
    "Deployment:AzureType"                                        = local.cloud_endpoints.azure_type
    "Deployment:Region"                                           = var.location
    "Deployment:ResourceGroupName"                                = var.resource_group_name
    "Deployment:WebAppName"                                       = local.names.web_app
    "Deployment:AzureTagPrefix"                                   = var.azure_tag_prefix
    "Deployment:KeyVaultName"                                     = local.names.key_vault
    "Deployment:SubscriptionId"                                   = data.azurerm_client_config.current.subscription_id
    "Deployment:SubscriptionDisplayName"                          = data.azurerm_subscription.current.display_name
    "Deployment:TenantId"                                         = data.azurerm_client_config.current.tenant_id
    "Deployment:AutomationAccountName"                            = local.names.automation
    "Deployment:AutomationAccountAzInstalled"                     = "True"
    "Deployment:AutomationEnabled"                                = "True"
    "Deployment:UpdaterRunbookRunAs"                              = local.names.updater_runbook
    "Deployment:LogAnalyticsWorkspace"                            = azurerm_log_analytics_workspace.avd.id
    "Deployment:ScriptedActionAccount"                            = azurerm_automation_account.scripted_actions.id
    "Deployment:SqlServerId"                                      = "${data.azurerm_subscription.current.id}/resourceGroups/${var.resource_group_name}/providers/Microsoft.Sql/servers/${local.names.sql_server}"
    "ApplicationInsights:ConnectionString"                        = azurerm_application_insights.this.connection_string
    "ApplicationInsights:InstrumentationKey"                      = azurerm_application_insights.this.instrumentation_key
    "DataProtection:Storage:Type"                                 = "AzureBlobStorage"
    "DataProtection:Protect:KeyIdentifier"                        = "${local.names.key_vault_uri}/keys/${local.names.data_protection}"
    "ConnectionStrings:DefaultConnection"                         = "Server=tcp:${local.names.sql_server_fqdn},1433;Initial Catalog=${local.names.database};Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;Authentication=Active Directory Default;"
    "RoleAuthorization:Enabled"                                   = "True"
    "Features:CumulativeRbac"                                     = "True"
    "AzureAD:ClientId"                                            = var.entra_app.client_id
    "AzureAD:TenantId"                                            = data.azurerm_client_config.current.tenant_id
    "AzureAD:ClientCertificates:0:SourceType"                     = "KeyVault"
    "AzureAD:ClientCertificates:0:KeyVaultUrl"                    = local.names.key_vault_uri
    "AzureAD:ClientCertificates:0:KeyVaultCertificateName"        = local.names.app_cert
    "AzureAD:DefaultGraphScopes"                                  = "User.Read|User.ReadBasic.All|User.Read.All|GroupMember.Read.All|Application.Read.All|Organization.Read.All"
    "WVD:AadTenantId"                                             = data.azurerm_client_config.current.tenant_id
    "WVD:SubscriptionId"                                          = data.azurerm_client_config.current.subscription_id
    "Billing:Mode"                                                = "MAU"
    "Artifacts:Mode"                                              = "Local"
    "Deployment:FallbackOptions:DefaultLocalAdmin:DisableAccount" = "True"
    "Deployment:FallbackOptions:DefaultLocalAdmin:RandomPassword" = "True"
  }
}

resource "azurerm_windows_web_app" "this" {
  name                          = local.names.web_app
  location                      = var.location
  resource_group_name           = var.resource_group_name
  service_plan_id               = azurerm_service_plan.this.id
  https_only                    = true
  client_affinity_enabled       = true
  public_network_access_enabled = var.web_app_public_network_access_enabled
  app_settings                  = local.app_settings
  tags                          = local.paas_tags

  # Code is deployed with Entra tokens (see install.tf), so basic auth stays off.
  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on           = true
    http2_enabled       = true
    ftps_state          = "Disabled"
    minimum_tls_version = "1.2"
    use_32_bit_worker   = false

    application_stack {
      current_stack  = "dotnet"
      dotnet_version = "v10.0"
    }
  }

  lifecycle {
    # Nerdio adds its own settings at runtime, and modules/nerdio-hardening adds VNet integration.
    ignore_changes = [app_settings, virtual_network_subnet_id, site_config[0].application_stack]
  }
}

# Contributor on its own resource group and on the groups it manages; Reader and Backup Reader
# on the subscription, which Nerdio uses for discovery and backup reporting.
locals {
  nerdio_rbac = merge(
    { for k, id in merge({ nerdio = "${data.azurerm_subscription.current.id}/resourceGroups/${var.resource_group_name}" }, var.managed_resource_group_ids) : "contributor-${k}" => { scope = id, role = "Contributor" } },
    {
      reader        = { scope = data.azurerm_subscription.current.id, role = "Reader" }
      backup-reader = { scope = data.azurerm_subscription.current.id, role = "Backup Reader" }
    },
  )
}

resource "azurerm_role_assignment" "nerdio_app" {
  for_each             = local.nerdio_rbac
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = var.entra_app.service_principal_object_id
}

# Health check at plan and apply. Fails until the install job (install.tf) finishes.
check "nerdio_health" {
  data "http" "ping" {
    url = "https://${local.names.default_hostname}/public/health/ping"
    # Without a timeout, a half-deleted app can hold a plan at "Still reading" indefinitely.
    request_timeout_ms = 15000
  }

  assert {
    condition     = data.http.ping.status_code == 200
    error_message = "Nerdio Manager isn't answering yet. The install job takes about 10 minutes after the first apply; see the ${local.names.automation} Automation account's jobs."
  }
}
