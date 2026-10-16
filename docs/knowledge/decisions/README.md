# Decision records

Short records of choices that shape the kit. One file per decision, numbered in order. Copy
[template.md](template.md) to add one. A reversed decision gets a new record, and the old one is
marked *Superseded by NNNN*.

<!-- BEGIN GENERATED: decision-index (from front matter; run scripts/kb/build.py) -->
| # | Decision | Status |
|---|---|---|
| [0001](0001-build-on-nerdio-provider.md) | Build the kit on Nerdio's own Terraform provider | Accepted |
| [0002](0002-nerdio-owns-avd-objects.md) | Nerdio owns AVD objects | Accepted |
| [0003](0003-marketplace-template.md) | Deploy Nerdio Manager from the exported Marketplace template | Accepted |
| [0004](0004-tenant-agnostic-inputs.md) | Tenant and subscription are inputs, never hardcoded | Accepted |
| [0005](0005-packer-for-images.md) | Packer builds the golden image | Accepted |
| [0006](0006-no-ansible.md) | No Ansible | Accepted |
| [0007](0007-button-ux.md) | GitHub Actions forms are the button experience | Accepted |
| [0008](0008-chat-front-door.md) | Chat is the guided front door; the engine stays deterministic | Accepted |
| [0009](0009-prefer-azure-github-hashicorp-oss.md) | Prefer Azure, GitHub, HashiCorp and open-source tooling | Accepted |
| [0010](0010-roadmap-horizon.md) | Roadmap horizon: 90-day build windows, 12-month direction | Accepted |
| [0014](0014-self-hosted-setup-chatbot.md) | The setup chat is a self-hosted chatbot using Claude on Microsoft Foundry | Accepted |
<!-- END GENERATED: decision-index -->
