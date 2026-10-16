---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0005. Packer builds the golden image

## Context and Problem Statement

Session hosts need a golden image. Image builds benefit from being code-reviewed and repeatable.
What builds it?

## Considered Options

- Packer, publishing to an Azure Compute Gallery
- Nerdio's own image management, building from a VM

## Decision Outcome

Chosen option: "Packer", because the project uses the HashiCorp stack where it fits. Packer builds
a Windows 11 multi-session + Microsoft 365 image (Gen2, Trusted Launch) and publishes it to an
Azure Compute Gallery that Terraform creates. Nerdio imports images from that gallery.

### Consequences

- Good, because image changes go through pull requests and CI (`packer validate`).
- Neutral, because Nerdio's own image management features are used only for rollout, not building.
- Details: [../packer/avd-image.md](../packer/avd-image.md).
