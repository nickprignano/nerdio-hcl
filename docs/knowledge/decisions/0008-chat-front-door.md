# 0008. Chat is the guided front door; the engine stays deterministic

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

The kit is meant to be turnkey for community users. A guided chat can walk someone through
discovery, preparation, configuration, bootstrap, deployment, the wizard steps, verification and
handover. But AI output isn't deterministic, costs tokens, and not everyone will want it.

## Decision

Chat (built from `CLAUDE.md`, repo skills and MCP) is the primary, white-glove front door. It
drives the same engine as the `./nerdio init` CLI wizard and the GitHub Actions forms, through one
shared parameter schema. The engine itself (Terraform, Packer, scripts, workflows) stays
deterministic and fully usable without AI.

Guardrails: no secrets in chat; a plan and an explicit yes before any apply; every change goes
through a PR; tokens are spent only in the chat layer.

## Consequences

- One schema to maintain, three front doors that can't drift apart.
- Users without an AI assistant lose convenience, not capability.
- Details: [../stack-options.md](../stack-options.md#guided-setup-by-chat-white-glove).
