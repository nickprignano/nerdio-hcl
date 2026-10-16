---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0013. Unlicensed code is reference only

## Context and Problem Statement

Nerdio's `NME-Terraform-Provider` and `NMW` repositories and the community project
`MB-External/NME-Terraform` have no license (checked 2026-10-16; provider at commit `65e547f`).
Without one, nobody else has the right to copy, modify or redistribute their code. Terraform's
own providers (azurerm, azuread, azapi) are MPL-2.0; Terraform and Packer are BSL 1.1. How may
the kit use these repositories?

## Considered Options

- Copy or adapt their code where useful
- Use them for facts only and write our own code

## Decision Outcome

Chosen option: "Facts only", because without a license we have no right to copy their code.

- Use unlicensed repositories for facts only: setting names, API endpoints, behavior. Write our
  own code from those facts and note the source in the knowledge base.
- Never copy, adapt, fork, re-host, vendor or redistribute their code or binaries. The kit
  downloads `nerdio/nme` from Nerdio's GitHub release at install time, and the Nerdio app package
  from Nerdio's service.
- Running Nerdio's published provider release as Nerdio intends is fine. Check the Nerdio partner
  agreement before anything beyond that.
- Ask Nerdio for a license (draft ask prepared, not yet sent) and track it in
  [upstream-contributions.md](../nerdio/upstream-contributions.md). Build our own provider only if
  Nerdio won't license theirs.
- Track `MB-External/NME-Terraform` as prior art ([community-projects.md](../nerdio/community-projects.md))
  and keep building our own in parallel.

### Consequences

- Good, because the kit stays clear of copyright problems when it goes public.
- Bad, because there can be no upstream PRs or hosted provider mirrors until Nerdio licenses the
  provider.
- Neutral, because our repo should pick its own license before going public (Apache-2.0
  recommended; not chosen yet).

## More Information

Not legal advice; revisit if Nerdio publishes terms.
