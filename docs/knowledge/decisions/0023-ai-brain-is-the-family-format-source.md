---
status: proposed
date: 2026-10-18
decision-makers: [maintainers]
---

# 0023. The AI hub owns the family's KB format, and this kit follows it as a member

## Context and Problem Statement

[0021](0021-knowledge-base-family.md) made this kit the reference implementation of the shared
KB format, so every format change had to start here. The maintainer now drives the second-brain
kit itself (format, prompts, cross-KB wiring) from the AI project, whose KB already collects the
siblings' signals. Where should the format be owned?

## Considered Options

- Keep this kit as the format's reference implementation
- Make the AI hub the format's source of truth, with this kit as a member

## Decision Outcome

Chosen option: "The AI hub owns the format", because format work now happens there and one
owner is easier to follow than two.

- In [family.yaml](../family.yaml), this kit's role is `member`. The AI hub's role is `reference`,
  which is how ai-brain's family scripts find the hub, and it owns "the family's shared KB format
  and conventions".
- A format change starts as a "Family format" decision in the hub. This kit adopts it by PR once
  the hub has accepted it, and bumps `format_version` to match.
- Besides the two sources every sibling gets, this KB watches the hub's `docs/knowledge/schema`,
  `scripts/kb` and `.github/workflows`, so a format change shows up in the weekly digest.
- The projects stay fully separate but aware. AVD is watched read-only, for the digest and
  the prior-art check: no shared work, no content copied between repos, and nothing from its
  project work lands here.
- This kit keeps owning its own topics (Nerdio Manager, the nerdio/nme provider, its Terraform
  and Packer) and its own decisions about how it uses AI.

### Consequences

- Good, because the format has one owner, in the project where it's developed.
- Good, because format changes are visible here before the adopting PR arrives.
- Bad, because this kit can't change the shared format on its own; it proposes changes to the hub.

## More Information

Also recorded in ai-brain decision 0007, "ai-brain owns the format", accepted on 2026-10-18 in
[ai-brain's decisions](https://github.com/nickprignano/ai-brain/tree/main/docs/knowledge/decisions).
