# 0005. Packer builds the golden image

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

Nerdio can build images itself from a VM, but the project aims to use the HashiCorp stack where
it fits, and image builds benefit from being code-reviewed and repeatable.

## Decision

Packer builds a Windows 11 multi-session + Microsoft 365 image (Gen2, Trusted Launch) and
publishes it to an Azure Compute Gallery that Terraform creates. Nerdio imports images from that
gallery.

## Consequences

- Image changes go through pull requests and CI (`packer validate`).
- Nerdio's own image management features are used only for rollout, not building.
- Details: [../packer/avd-image.md](../packer/avd-image.md).
