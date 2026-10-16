# 0010. Roadmap horizon: what's locked, for how long, and when to review

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

The [roadmap](../stack-options.md) mixes durable principles with plans that depend on things the
kit doesn't control. Nerdio's Terraform provider is a `v0.0.1-preview.1` GitHub pre-release with
no license, so any release could close a gap or open a new one. Nothing has run in a real tenant
yet either, and the first sandbox run may reshuffle the plan. Locking everything for a year would
freeze guesses; locking nothing would let the direction drift.

## Decision

Lock the roadmap at three horizons.

**Locked for 12 months (until 2027-10):**
- Maximum safe automation: automate everything that can and should be automated, behind a
  turnkey copy-paste, button or chat experience.
- HCL first: Terraform and Packer own desired state.
- The kit works from Azure Cloud Shell on a tablet, with no local install required.
- Prefer Azure, GitHub, HashiCorp/HCL and open-source tooling ([0009](0009-prefer-azure-github-hashicorp-oss.md)).
- The no-leak rule: nothing that identifies a real tenant, person, employer or customer goes in
  the public repo (see [../README.md](../README.md#keep-it-public-safe)).
- Build what we can, and hand Nerdio the rest as tracked asks
  ([../nerdio/upstream-contributions.md](../nerdio/upstream-contributions.md)).
- The second brain: this living knowledge base, the weekly source digest and the prior-art check
  ([../curation.md](../curation.md)).

**Locked for this quarter (until 2026-12-31):** the build order. First the single-apply Terraform
install, then the chat-led setup, then hardening.

**Kept open:** anything that depends on Nerdio, including provider resources, API gaps, the
install path and the wizard steps, plus anything the first live sandbox run contradicts.

**Review:** every quarter, and also whenever the weekly digest flags a `nerdio/nme` release.

## Consequences

- A change to a 12-month principle needs a new decision record that supersedes this one.
- The build order can change at a quarterly review without a new record; note the new order in
  the roadmap and in this record's review log.
- A Nerdio release triggers a review of the "kept open" items, not of the principles.

## Review log

| Date | Trigger | Outcome |
|---|---|---|
| 2026-10-16 | Recorded | Initial horizons set. |
