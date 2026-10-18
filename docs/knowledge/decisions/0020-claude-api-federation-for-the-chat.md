---
status: accepted
date: 2026-10-18
decision-makers: [maintainers]
---

# 0020. The setup chat can use the Claude API, signed in by workload identity federation

## Context and Problem Statement

[0014](0014-self-hosted-setup-chatbot.md) backs the setup chat with Claude on Microsoft Foundry.
Foundry needs quota that Microsoft grants per request, and a new tenant can wait on that, which
blocks the chat-first setup ([0017](0017-chatbot-first-deployment.md)). The Claude API has no
such wait, but its usual credential is a long-lived API key, which 0014 and the secrets rules
([0015](0015-secrets-key-vault-default-openbao-optional.md)) avoid. How does the chat use the Claude API without a
stored secret?

## Considered Options

- The Claude API with workload identity federation from the app's managed identity
- The Claude API with an API key kept in Key Vault and referenced by the Container App
- Wait for Foundry quota

## Decision Outcome

Chosen option: "The Claude API with workload identity federation", because it needs no secret
at all, and the trust can be narrowed to one identity.

- `model_provider` in `modules/assistant` picks `claude-api` or `foundry`. `claude-api` is the
  default and the main path; Foundry stays one flag away for tenants that have quota.
- Terraform creates an Entra audience app (v2.0 tokens, no permissions, no secret). The app asks
  Entra for a token for it with its managed identity, and the Anthropic SDK exchanges that for a
  10-minute Claude API token.
- On the Claude side, `./nerdio assistant --connect-claude` creates a workspace, an issuer for the
  tenant, a developer service account and a rule that matches the identity's exact object ID,
  the tenant and the audience, with the `workspace:inference` scope. An Anthropic organization
  admin runs it once with their own short-lived login, or uses the Console (`--console`).
- No API key variable reaches the app; the client removes any it finds, because one would
  silently outrank federation.

### Consequences

- Good, because no key exists to leak, rotate or hand over, and revoking is archiving one rule.
- Good, because the chat no longer waits on Foundry quota.
- Bad, because billing moves to an Anthropic organization, outside the Azure subscription.
- Bad, because the issuer must accept Entra tokens up to 24 hours old (Azure's managed identity
  token lifetime), so a leaked Entra token for the audience could be exchanged for that long; the
  exact object ID match limits it to the chat's own identity.
- Neutral, because the Anthropic side is created by a script calling the Admin API, not
  Terraform: there's no Terraform provider for it in the kit's toolset yet.

## More Information

Anthropic's docs: Workload Identity Federation, its Microsoft Entra ID guide and the WIF Admin
API.

Update, 2026-10-18: Microsoft denied the kit's Foundry quota requests for the first trial tenant,
so the Claude API is the main path, not a fallback, and the module's default changed to match.
Revisit if Foundry quota becomes routine to get, or if an Anthropic Terraform provider covers
federation.
