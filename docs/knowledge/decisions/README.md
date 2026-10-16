# Decision records

Short records of choices that shape the kit. One file per decision, numbered in order. Copy
[template.md](template.md) to add one. A reversed decision gets a new record, and the old one is
marked *Superseded by NNNN*.

| # | Decision | Status |
|---|---|---|
| [0001](0001-build-on-nerdio-provider.md) | Build the kit on Nerdio's own Terraform provider | Accepted |
| [0002](0002-nerdio-owns-avd-objects.md) | Nerdio owns AVD objects; Terraform configures them only through Nerdio | Accepted |
| [0003](0003-marketplace-template.md) | Deploy Nerdio Manager from the exported Marketplace template | Accepted, under review |
| [0004](0004-tenant-agnostic-inputs.md) | Tenant and subscription are inputs, never hardcoded | Accepted |
| [0005](0005-packer-for-images.md) | Packer builds the golden image | Accepted |
| [0006](0006-no-ansible.md) | No Ansible; Terraform owns desired state, Nerdio owns runtime work | Accepted |
| [0007](0007-button-ux.md) | GitHub Actions `workflow_dispatch` forms are the button experience; HCP no-code optional | Accepted |
| [0008](0008-chat-front-door.md) | Chat is the guided front door; the engine stays deterministic and usable without AI | Accepted |
