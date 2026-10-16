---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0014. The setup chat is a self-hosted chatbot using Claude on Microsoft Foundry

## Context and Problem Statement

[0008](0008-chat-front-door.md) made chat the guided front door and said it would be built from
`CLAUDE.md`, repo skills and MCP, which assumes the user runs an AI coding assistant. Many
community users won't have one, and the chat should follow the same rules as the rest of the kit:
Azure-native ([0009](0009-prefer-azure-github-hashicorp-oss.md)), deployable from Cloud Shell, no
long-lived secrets. Where does the chat run, and which model backs it?

## Considered Options

- A standalone chatbot the user deploys into their own Azure tenant, using Claude on Microsoft Foundry
- A Claude Code skill in the repo (the user brings their own AI assistant)
- A standalone chatbot using an Anthropic API key
- A standalone chatbot using an open-weights model

## Decision Outcome

Chosen option: "A standalone chatbot in the user's tenant, using Claude on Microsoft Foundry",
because it needs nothing beyond the Azure tenant being deployed into, model use is billed through
the user's Azure subscription, and a managed identity removes the need for any API key.

- A web app on Azure Container Apps that scales to zero, deployed by Terraform from Cloud Shell
  with `./nerdio assistant`.
- Entra sign-in limited to an admin group, with no client secret.
- The app calls Claude on Foundry with a managed identity; key-based access is off on the Foundry
  resource.
- The `./nerdio` engine is the bot's only tool surface. The bot never changes anything in the
  tenant; it hands the user Cloud Shell commands to run instead.
- The server is stateless: no stored conversations.

This replaces the "built from `CLAUDE.md`, repo skills and MCP" part of 0008. The rest of 0008
stands: chat is the guided front door, and the engine stays deterministic and usable without AI.

### Consequences

- Good, because a community user needs only their Azure tenant; there's no separate AI account,
  API key or local tool to install.
- Good, because nothing in the conversation can change the tenant, and no IDs or secrets pass
  through chat.
- Bad, because the user hosts and pays for the app and model use (small, since it scales to zero
  and bills per token).
- Bad, because it depends on Claude being available in Microsoft Foundry for the user's
  subscription and region.
- Neutral, because three things are *unverified* until a live run: that Terraform can create the
  Claude deployment (`azurerm_cognitive_deployment` with model format `Anthropic`), that the
  Cognitive Services User role is enough for the managed identity, and that sign-in works with ID
  tokens only.

## More Information

Design: `docs/assistant.md` (pull request #5).
