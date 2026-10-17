---
status: accepted
date: 2026-10-17
decision-makers: [maintainers]
---

# 0019. Least privilege, with every access need written down

## Context and Problem Statement

The kit grants a lot of access: a person bootstraps it with Owner and Entra admin roles, and the
pipeline's apply identity can change the subscription and Entra. That passes in a personal
sandbox but not in tenants with strict access rules, such as regulated organizations, sovereign
clouds or on-premises-connected estates, where every grant needs a reason and privileged roles
are held only through PIM. How do we keep the kit turnkey without assuming broad access?

## Considered Options

- Least privilege by default, every right listed with its reason, and switches to narrow further
- Broad defaults, with hardening left to each tenant
- A separate "strict" variant of the kit

## Decision Outcome

Chosen option: "Least privilege by default", because strict tenants are the case to design for,
and one kit with documented switches stays maintainable where a second variant wouldn't.

- [docs/access.md](../../access.md) lists every right a person or identity needs, its scope,
  when it's needed and why. A right not on that page is a bug.
- Rights that can be constrained are. The apply identity's Role Based Access Control
  Administrator role carries a condition that limits it to the roles the kit assigns, so it can't
  grant Owner or widen its own access.
- Strict tenants narrow further with supported switches (`access` in the pipeline stage,
  `grant_admin_consent = false`), never by forking the kit.
- People's privileged roles are needed only for one-time steps, and the docs say so, so they
  can be activated through PIM for the step.

### Consequences

- Good, because a reviewer can approve the kit from one page, and the defaults survive scrutiny.
- Good, because a compromised approved run still can't grant Owner.
- Bad, because a new role assignment in the kit also means updating `apply_assignable_roles`
  and the access page; the pipeline's apply fails until it's added.
- Neutral, because sovereign-cloud and on-premises support stay out of scope until their gaps
  are listed in the chatbot-first inventory.

## More Information

Revisit when the kit runs in a sovereign cloud, or when Nerdio documents narrower permissions for
its Entra app.
