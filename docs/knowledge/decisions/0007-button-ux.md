# 0007. GitHub Actions forms are the button experience

- **Status:** Accepted (chat is the primary front door per [0008](0008-chat-front-door.md); forms remain the button path)
- **Date:** 2026-10-16

## Context

The kit should be turnkey: copy-paste, a button, or chat. A button needs a form for inputs and
somewhere to run Terraform and Packer. HCP Terraform no-code modules offer that, but which tier
includes them wasn't verified.

## Decision

`workflow_dispatch` forms in GitHub Actions are the button experience. They're free, take typed
inputs, and run the same engine as the copy-paste and chat paths. HCP Terraform no-code modules
are an optional alternative.

## Consequences

- Users fork the repo, add secrets and run workflows from the Actions tab; no paid service needed.
- Workflows must keep secrets in GitHub environments and keep artifacts private (no-leak rule).
- Details: [../stack-options.md](../stack-options.md#the-experience).
