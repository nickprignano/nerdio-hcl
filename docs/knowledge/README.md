# Knowledge base

What we've learned building a HashiCorp-stack (Terraform + Packer) deployment kit for
**Nerdio Manager for Enterprise** on Azure Virtual Desktop. It covers research findings, gotchas
and the decisions behind the kit, and it is meant to be read and added to by anyone using the kit.

This is a living document set. When something new is learned, add it to the topic page it
belongs to instead of starting a new file.

## Index

| Page | What's in it |
|---|---|
| [nerdio/platform.md](nerdio/platform.md) | What the Marketplace deployment creates, the install step, setup wizard, roles and hardening |
| [nerdio/entra-app.md](nerdio/entra-app.md) | The `nerdio-nmw-app` registration, permissions, app roles and the REST API client |
| [nerdio/terraform-provider.md](nerdio/terraform-provider.md) | Nerdio's own `nerdio/nme` provider: auth, resources, coverage gaps, how to build it |
| [nerdio/upstream-contributions.md](nerdio/upstream-contributions.md) | Gaps, bugs and doc fixes we could contribute to Nerdio's provider, with evidence |
| [nerdio/community-projects.md](nerdio/community-projects.md) | Other Nerdio + Terraform projects worth knowing about |
| [terraform/azurerm-5.md](terraform/azurerm-5.md) | azurerm 5.x and azuread 3.x changes we hit, with fixes |
| [terraform/restricted-networks.md](terraform/restricted-networks.md) | Running Terraform and Packer where the registry is blocked |
| [terraform/testing-and-ci.md](terraform/testing-and-ci.md) | `terraform test`, tflint and the CI workflow |
| [packer/avd-image.md](packer/avd-image.md) | Building a Windows 11 multi-session image for Nerdio |
| [stack-options.md](stack-options.md) | Roadmap to a zero-touch deployment: which manual steps can go, which HashiCorp/IBM/Microsoft tools fit, and what Nerdio would need to change |
| [decisions/](decisions/README.md) | Short decision records: what was decided and why |
| [curation.md](curation.md) | The weekly source digest and the prior-art check that keep this KB current |

## Before you build something

Run the prior-art check first (`python3 scripts/kb/prior_art.py "<topic>"`, see
[curation.md](curation.md#prior-art-check-kb-prior-art)). It searches this KB and GitHub, so
you don't spend time on problems someone has already solved.

## How to add to it

- **A fact or gotcha:** add a bullet to the matching topic page. Say what happened, the fix, and
  the versions it applies to. Mark anything you haven't confirmed as *unverified*.
- **A decision:** copy [decisions/template.md](decisions/template.md) to the next number and
  add it to the list in [decisions/README.md](decisions/README.md). If a decision is reversed,
  write a new record and mark the old one *Superseded*.
- **A new topic:** only when it doesn't fit an existing page. Add a row to the index above.
- Every page ends with a *Last reviewed* line. Update it when you change or re-check the page.

## Keep it public-safe

This repo is intended to be shared with the community, so nothing here may identify a real
environment. Before committing, check that your change has none of the following:

- Tenant IDs, subscription IDs, object or client IDs of your own apps, or resource IDs
- Domain names, UPNs, email addresses, internal hostnames or URLs
- IP ranges or CIDRs from a real network (use RFC 5737 / documentation ranges or `10.x` examples)
- Secrets, keys, SAS tokens, connection strings or state file excerpts
- Employer, customer or tenant names

Use placeholders such as `<tenant-id>`, `<subscription-id>`, `<app-name>` and `contoso.com`.
Write lessons as general advice ("in a sandbox tenant"), not as a story about a specific one.
Published Microsoft or Nerdio identifiers (for example the documented Nerdio app role IDs)
are fine, because they are the same in every tenant.
