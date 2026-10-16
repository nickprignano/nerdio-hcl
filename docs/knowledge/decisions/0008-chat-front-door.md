---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
review: Partly superseded by 0014 (how the chat is built and hosted).
---

# 0008. Chat is the guided front door; the engine stays deterministic

## Context and Problem Statement

The kit is meant to be turnkey for community users. A guided chat can walk someone through
discovery, preparation, configuration, bootstrap, deployment, the wizard steps, verification and
handover. But AI output isn't deterministic, costs tokens, and not everyone will want it. What
role does chat play?

## Considered Options

- Chat as the primary front door over a deterministic engine
- Chat as the engine (the assistant runs ad-hoc commands)
- No chat; CLI and forms only

## Decision Outcome

Chosen option: "Chat as the primary front door over a deterministic engine". Chat (built from
`CLAUDE.md`, repo skills and MCP) drives the same engine as the `./nerdio init` CLI wizard and the
GitHub Actions forms, through one shared parameter schema. The engine itself (Terraform, Packer,
scripts, workflows) stays deterministic and fully usable without AI.

Guardrails: no secrets in chat; a plan and an explicit yes before any apply; every change goes
through a PR; tokens are spent only in the chat layer.

### Consequences

- Good, because there's one schema to maintain and three front doors that can't drift apart.
- Good, because users without an AI assistant lose convenience, not capability.
- Details: [../stack-options.md](../stack-options.md#guided-setup-by-chat-white-glove) and
  [../chat-assistant.md](../chat-assistant.md).

## More Information

Partly superseded by [0014](0014-self-hosted-setup-chatbot.md): the chat is a standalone chatbot
hosted in the user's tenant using Claude on Microsoft Foundry, not something built from
`CLAUDE.md`, repo skills and MCP. The front-door role and the deterministic engine stand.
