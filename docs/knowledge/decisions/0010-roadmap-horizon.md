---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0010. Roadmap horizon: 90-day build windows, 12-month direction

## Context and Problem Statement

The [roadmap](../stack-options.md) mixes durable principles with plans that depend on things the
kit doesn't control. Nerdio's Terraform provider is a `v0.0.1-preview.1` GitHub pre-release with
no license, so any release could close a gap or open a new one. Nothing has run in a real tenant
yet either, and the first sandbox run may reshuffle the plan. Building needs a committed plan, but
locking a year ahead would stop good ideas from being added later. What is committed, and for how
long?

## Considered Options

- Lock the build order in 90-day windows; keep the 12-month roadmap directional
- Lock the principles for 12 months and the build order for a quarter
- Lock nothing

## Decision Outcome

Chosen option: "90-day windows, 12-month direction", because it commits enough to build without
closing the door on additions.

**Locked, 90 days at a time:** the build order. Each window commits to a short list of work and
isn't reshuffled mid-window. The first window runs from 2026-10-16 to 2027-01-14 and follows the
roadmap's build order: the single-apply Terraform install first, then the chat-led setup, then
hardening.

**Directional, not locked (12 months):** the longer roadmap and the principles behind it. They
guide each window's choices and stay open to additions:

- Maximum safe automation, behind a turnkey copy-paste, button or chat experience.
- HCL first: Terraform and Packer own desired state.
- The kit works from Azure Cloud Shell on a tablet, with no local install required.
- Prefer Azure, GitHub, HashiCorp/HCL and open-source tooling ([0009](0009-prefer-azure-github-hashicorp-oss.md)).
- The no-leak rule (see [../README.md](../README.md#keep-it-public-safe)).
- Build what we can, and hand Nerdio the rest as tracked asks
  ([../nerdio/upstream-contributions.md](../nerdio/upstream-contributions.md)).
- The second brain: this living knowledge base, the weekly source digest, the prior-art check and
  the feedback loop ([../curation.md](../curation.md)).

**Kept open:** anything that depends on Nerdio, including provider resources, API gaps, the
install path and the wizard steps, plus anything the first live sandbox run contradicts.

**Review:** at the end of each 90-day window, to set the next window's build list, and whenever
the weekly digest flags a `nerdio/nme` release.

### Consequences

- Good, because new ideas can join the roadmap at any time; they get scheduled into a window at
  its review.
- Neutral, because changing a principle doesn't need a superseding record, but a reversal of a
  recorded decision (such as 0009) still does.
- Neutral, because a Nerdio release triggers a review of the "kept open" items, not of the current
  window.

## More Information

| Date | Trigger | Outcome |
|---|---|---|
| 2026-10-16 | Recorded | First 90-day window starts: install, then chat setup, then hardening. |
