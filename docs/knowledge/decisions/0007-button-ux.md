---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0007. GitHub Actions forms are the button experience

## Context and Problem Statement

The kit should be turnkey: copy-paste, a button, or chat. A button needs a form for inputs and
somewhere to run Terraform and Packer. What provides it?

## Considered Options

- GitHub Actions `workflow_dispatch` forms
- HCP Terraform no-code modules

## Decision Outcome

Chosen option: "`workflow_dispatch` forms", because they're free, take typed inputs, and run the
same engine as the copy-paste and chat paths. HCP Terraform no-code modules are an optional
alternative; which paid tier includes them wasn't verified. Chat is the primary front door
([0008](0008-chat-front-door.md)); forms remain the button path.

### Consequences

- Good, because users fork the repo, add secrets and run workflows from the Actions tab; no paid
  service is needed.
- Bad, because workflows must keep secrets in GitHub environments and keep artifacts private
  (no-leak rule).
- Details: [../stack-options.md](../stack-options.md#the-experience).
