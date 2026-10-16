# Security baselines and hardening

Security building blocks for a Nerdio + AVD deployment, and the patterns for recording accepted
risks. The chat assistant's `security-review`, `encryption` and `endpoint-mgmt` skills draw on this
page (see [../chat-assistant.md](../chat-assistant.md#6-security-review-and-hardening)).

## What Nerdio already publishes

All in [Get-Nerdio/NMW](https://github.com/Get-Nerdio/NMW):

- **`intune-policies/`:** ready-made Intune policy sets: security baselines, attack surface
  reduction (ASR), compliance, Conditional Access, Defender and firewall. *Unverified:* whether the
  JSON can be applied as-is through the msgraph or microsoft365 Terraform providers.
- **`azure-custom-roles/nme-custom-role.json`:** a least-privilege Azure custom role for Nerdio,
  an alternative to subscription Owner for day-to-day operation. *Unverified:* whether it covers the
  initial install.
- **`scripted-actions/windows-scripts`:** Windows scripted actions for screen capture protection,
  RDP Shortpath and clipboard redirection, among others.

## Kit hardening

- Private App Service, SQL and Key Vault through the kit's second apply; see
  [../nerdio/platform.md](../nerdio/platform.md#hardening-private-endpoints).
- The golden image is Gen2 with Trusted Launch; see [../packer/avd-image.md](../packer/avd-image.md).

## Accepted risks

When a review finding is accepted instead of fixed, record it as a decision in the environment's
own (private) decision log: the finding, why it's accepted, and when to revisit it. Only general
patterns belong here, never a specific environment's findings.

_Last reviewed: 2026-10-16_
