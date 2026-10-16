---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0002. Nerdio owns AVD objects

## Context and Problem Statement

AVD host pools, app groups and scaling can be managed directly with azurerm, but Nerdio also
manages them: it auto-scales, rolls out images and edits host pool settings at runtime. Which
tool should own them?

## Considered Options

- Nerdio owns them; the kit declares them through `nerdio/nme`
- azurerm owns them alongside Nerdio

## Decision Outcome

Chosen option: "Nerdio owns them", because two owners would fight over the same objects. The kit
never creates AVD host pools, app groups or scaling plans with azurerm; it declares them through
`nerdio/nme`, which goes through Nerdio's API. Refined by [0001](0001-build-on-nerdio-provider.md).

### Consequences

- Good, because there are no drift fights between Terraform and Nerdio's auto-scale or image rollout.
- Bad, because anything the Nerdio provider can't express is configured in the Nerdio console.
