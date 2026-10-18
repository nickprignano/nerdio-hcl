# --- Claude API through workload identity federation --------------------------------------
#
# With model_provider = "claude-api" the chat calls the Claude API directly instead of Foundry.
# No API key exists: the app asks Entra for a token for its own managed identity, and the Claude
# API trades it for a short-lived access token (docs/assistant.md#claude-api). The Claude side (an
# issuer for this tenant, a service account and a rule that accepts only this app's identity) is
# made once by `./nerdio assistant --connect-claude`, which reads the claude_federation output.

locals {
  use_claude_api = var.model_provider == "claude-api"
  # The token's aud claim is the audience app's client ID (v2.0 tokens); the app asks for api://<id>.
  claude_audience = local.use_claude_api ? azuread_application.claude_audience[0].client_id : null
  claude_api_env = local.use_claude_api ? {
    for k, v in {
      NERDIO_MODEL                 = var.claude_api.model
      NERDIO_CLAUDE_TOKEN_RESOURCE = "api://${local.claude_audience}"
      ANTHROPIC_ORGANIZATION_ID    = var.claude_api.organization_id
      ANTHROPIC_FEDERATION_RULE_ID = var.claude_api.federation_rule_id
      ANTHROPIC_SERVICE_ACCOUNT_ID = var.claude_api.service_account_id
      ANTHROPIC_WORKSPACE_ID       = var.claude_api.workspace_id
    } : k => v if v != null
  } : {}
}

# Entra only issues a token for an audience that exists in the tenant. This app has no secret, no
# permissions and no redirect URIs: it is only a name the chat's identity can ask a token for.
resource "azuread_application" "claude_audience" {
  count            = local.use_claude_api ? 1 : 0
  display_name     = "${var.name} Claude API audience"
  sign_in_audience = "AzureADMyOrg"

  api {
    # v2.0 tokens carry iss https://login.microsoftonline.com/<tenant>/v2.0 and aud = the client ID.
    requested_access_token_version = 2
  }
}

resource "azuread_application_identifier_uri" "claude_audience" {
  count          = local.use_claude_api ? 1 : 0
  application_id = azuread_application.claude_audience[0].id
  identifier_uri = "api://${azuread_application.claude_audience[0].client_id}"
}

resource "azuread_service_principal" "claude_audience" {
  count     = local.use_claude_api ? 1 : 0
  client_id = azuread_application.claude_audience[0].client_id
}
