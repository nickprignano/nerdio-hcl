# Decision records

Short records of choices that shape the kit. One file per decision, numbered in order. Copy
[template.md](template.md) to add one. A reversed decision gets a new record, and the old one is
marked *Superseded by NNNN*.

<!-- BEGIN GENERATED: decision-index (from front matter; run scripts/kb/build.py) -->
| # | Decision | Status |
|---|---|---|
| [0001](0001-build-on-nerdio-provider.md) | Build the kit on Nerdio's own Terraform provider | Accepted |
| [0002](0002-nerdio-owns-avd-objects.md) | Nerdio owns AVD objects | Accepted |
| [0003](0003-marketplace-template.md) | Deploy Nerdio Manager from the exported Marketplace template | Superseded by 0011 |
| [0004](0004-tenant-agnostic-inputs.md) | Tenant and subscription are inputs, never hardcoded | Accepted |
| [0005](0005-packer-for-images.md) | Packer builds the golden image | Accepted |
| [0006](0006-no-ansible.md) | No Ansible | Superseded by 0028 |
| [0007](0007-button-ux.md) | GitHub Actions forms are the button experience | Accepted |
| [0008](0008-chat-front-door.md) | Chat is the guided front door; the engine stays deterministic | Accepted |
| [0009](0009-prefer-azure-github-hashicorp-oss.md) | Prefer Azure, GitHub, HashiCorp and open-source tooling | Accepted |
| [0010](0010-roadmap-horizon.md) | Roadmap horizon: 90-day build windows, 12-month direction | Accepted |
| [0011](0011-terraform-native-install.md) | Install Nerdio Manager in Terraform; HCL first | Accepted |
| [0012](0012-cloud-shell-baseline.md) | Everything runs from Cloud Shell in a browser | Accepted |
| [0013](0013-unlicensed-code-reference-only.md) | Unlicensed code is reference only | Accepted |
| [0014](0014-self-hosted-setup-chatbot.md) | The setup chat is a self-hosted chatbot using Claude on Microsoft Foundry | Accepted |
| [0015](0015-secrets-key-vault-default-openbao-optional.md) | Secrets: Key Vault by default; OpenBao as the optional Vault-style module | Accepted |
| [0016](0016-gated-deploy-pipeline.md) | Deploy through GitHub Actions with OIDC and a reviewer gate; chat drives the pipeline | Accepted |
| [0017](0017-chatbot-first-deployment.md) | Every Azure deployment is chatbot-first | Accepted |
| [0018](0018-apache-2-license.md) | License the kit under Apache-2.0 | Accepted |
| [0019](0019-least-privilege-explicit-access.md) | Least privilege, with every access need written down | Accepted |
| [0020](0020-claude-api-federation-for-the-chat.md) | The setup chat can use the Claude API, signed in by workload identity federation | Accepted |
| [0021](0021-knowledge-base-family.md) | This KB is aware of sibling knowledge bases, while staying separate and self-contained | Accepted |
| [0022](0022-family-model-selection-convention.md) | Follow the family's model-selection convention, as one of its pilot projects | Proposed |
| [0023](0023-ai-brain-is-the-family-format-source.md) | The AI hub owns the family's KB format, and this kit follows it as a member | Rejected |
| [0026](0026-read-only-readiness-engine.md) | Readiness checks are read-only, cover the whole lifecycle, and complement Nerdio's deployability test | Accepted |
| [0027](0027-github-settings-in-terraform.md) | The repository's own GitHub settings are Terraform with no saved state, planned daily and applied only by the owner | Proposed |
| [0028](0028-targeted-ansible-for-images-and-hybrid.md) | Targeted Ansible for image provisioning, hybrid AD DS storage joins and static host day-2 configuration | Accepted |
<!-- END GENERATED: decision-index -->
