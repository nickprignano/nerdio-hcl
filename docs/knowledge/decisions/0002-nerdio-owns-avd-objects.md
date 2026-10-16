# 0002. Nerdio owns AVD objects

- **Status:** Accepted (refined by [0001](0001-build-on-nerdio-provider.md))
- **Date:** 2026-10-16

## Context

AVD host pools, app groups and scaling can be managed directly with azurerm, but Nerdio also
manages them: it auto-scales, rolls out images and edits host pool settings at runtime.

## Decision

The kit never creates AVD host pools, app groups or scaling plans with azurerm. Nerdio owns
them; the kit declares them through `nerdio/nme`, which goes through Nerdio's API.

## Consequences

- No drift fights between Terraform and Nerdio's auto-scale or image rollout.
- Anything the Nerdio provider can't express is configured in the Nerdio console.
